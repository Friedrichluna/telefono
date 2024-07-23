#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import fcntl
import os
import random

import linkat

from .CONSTANTS import RECORD_DIR
from .CONSTANTS import RECORD_PREFIX
from .CONSTANTS import RECORD_SUFFIX

from .CONSTANTS import RECORD_LIST_FILE
from .CONSTANTS import BACKUP_EXT


class NumberType:
	UNASSIGNED = 0
	RECORDING = 1

class Number ():
	def __init__ (self, records, number:str, type:NumberType):

		self.__records = records
		self.__number = number
		self.__type = type

		self.__description = str ()
		self.__exists = False
		return

	def __getattribute__ (self, name):
		if 'number' == name:
			return self.__number

		if 'description' == name:
			return self.__description

		if 'exists' == name:
			if NumberType.RECORDING == self.__type:
				return self.__exists

			return False

		if 'filename' == name:
			if NumberType.RECORDING == self.__type:
				filename = ""
				filename += RECORD_DIR
				filename += "/"
				filename += RECORD_PREFIX
				filename += str(self.__number)
				filename += RECORD_SUFFIX
				return filename

			return str ()

		return super ().__getattribute__ (name)

	def __setattr__ (self, name, value):
		if 'number' == name:
			raise AttributeError ("read-only attribute")

		if 'description' == name:
			if not isinstance (value, str):
				raise TypeError (
				    "description must be str not %r" %
				    type (value))

			self.__description = value
			self.__records.sync_data ()
			return

		if 'exists' == name:
			if not isinstance (value, bool):
				raise TypeError (
				    "exists must be bool not %r" %
				    type (value))

			if NumberType.UNASSIGNED == self.__type and value:
				self.__type = NumberType.RECORDING

			if NumberType.RECORDING == self.__type:
				self.__exists = value
			return

		if 'filename' == name:
			raise AttributeError ("read-only attribute")

		return super ().__setattr__ (name, value)

	def is_assignable (self) -> bool:

		if NumberType.UNASSIGNED == self.__type:
			return True

		return False


class Records ():
	def __init__ (self, filename:str=RECORD_LIST_FILE):
		self.__data = list ()
		self.__prevent_sync = False

		self.__filename = filename

		# previously crashed while writing
		# restore backup
		if not os.path.exists (self.__filename) \
		and os.path.exists (self.__filename + BACKUP_EXT):
			print ("restoring backup file")
			os.rename (self.__filename + BACKUP_EXT,
			           self.__filename)

		# load file
		if os.path.exists (self.__filename):
			with open (self.__filename, "rt") as f:
				self.__load (f)
		else:
			os.mknod (self.__filename)

		return None

	def __find (self, number:str) -> (int, bool):
		for index in range (len (self.__data)):
			if number == self.__data[index].number:
				return index, True
			if number < self.__data[index].number:
				return index, False
		return None, False

	def __get (self, number:str) -> Number:
		index, exists = self.__find (number)

		if None is index:
			index = len (self.__data)

		if not exists:
			record = Number (records=self,
			                 number=number,
			                 type=NumberType.UNASSIGNED)
			self.__data.insert (index, record)
			return record

		return self.__data[index]

	def __set (self, number:Number):
		index, exists = self.__find (number.number)

		if None is index:
			self.__data.append (number)
			return

		if not exists:
			self.__data.insert (index, number)
			return

		self.__data[index] = number
		return

	def __del (self, number:str) -> Number:
		index, exists = self.__find (number)

		if not exists:
			return None

		number = self.__data[index]
		self.__data.__delitem__ (index)
		return number

	def __contains__ (self, number:str):
		index, exists = self.__find (number)

		if not exists:
			return False

		return self.__data[index].exists

	def __getitem__ (self, key:int):
		return self.__get (str (key))

	def __delitem__ (self, key:int):
		self.__del (str (key))
		self.sync_data ()
		return


	def __iter__ (self):
		l = list (self.numbers ())
		l.sort ()
		return iter (l)

	def __len__ (self):
		length = 0
		for number in self.__data:
			if number.exists:
				length += 1
		return length


	def numbers (self):
		for number in self.__data:
			if number.exists:
				yield number.number

	def pop (self, number):
		ret = self.__del (str (number))
		self.sync_data ()
		return ret

	def __load (self, _file):
		fcntl.flock(_file, fcntl.LOCK_SH)

		self.__prevent_sync = True

		for lineno, line in enumerate (_file.readlines ()):

			# ignore commented lines
			index = line.find ("#")
			if (-1 != index):
				line = line[:index]

			# ignore empty lines
			if not line:
				continue

			index = line.find (":")
			if (-1 == index):
				print ("ignoring malformed line %d"
				       % (lineno+1))
				continue

			number = line[:index]
			name = line[index+1:]

			number = number.strip ()
			name = name.strip ()

			try:
				number = int (number)
			except ValueError:
				print ("Key is not a number!",
				       "Ignoring line")
				continue

			# ignore empty names
			if not name:
				continue

			self[number].description = name

		self.__prevent_sync = False

		fcntl.flock(_file, fcntl.LOCK_UN)
		return

	def __store (self, _file):
		fcntl.flock(_file, fcntl.LOCK_EX)

		_file.truncate ()

		numbers = [int (number.number) for number in self.__data]
		numbers.sort ()

		for number in numbers:
			name = self[number].description.strip ()

			# ignore empty names
			if not name:
				continue

			_file.write (str (number))
			_file.write (": ")
			_file.write (name)
			_file.write ("\n")

		_file.flush ()

		fcntl.flock(_file, fcntl.LOCK_UN)
		return

	def __invalidate_fs (self):
		for number in self.__data:
			number.exists = False
		return

	def sync_data (self):
		if self.__prevent_sync:
			return

		# create temporary file
		fd = os.open (os.path.dirname (self.__filename),
		              os.O_TMPFILE | os.O_WRONLY,
		              mode=0o600)

		# create backup file
		if os.path.exists (self.__filename):
			os.rename (self.__filename,
			           self.__filename + BACKUP_EXT)

		# store into temporary file
		f = os.fdopen (fd, "wt")
		self.__store (f)

		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % fd,
		                linkat.AT_FDCWD, self.__filename.encode(),
		                linkat.AT_SYMLINK_FOLLOW)

		f.close ()

		return

	def sync_fs (self, directory:str=RECORD_DIR):
		self.__invalidate_fs ()

		for file in os.listdir (directory):
			path = os.path.join (directory, file)

			if os.path.isfile (path) \
			and file.startswith (RECORD_PREFIX) \
			and file.endswith (RECORD_SUFFIX):
				file = file[len(RECORD_PREFIX) :]
				file = file[: -len(RECORD_SUFFIX)]
				number = int (file)

				self[number].exists = True
		return

	def get_random (self):
		if not self.__data:
			return None

		return random.choice (self.__data)

	def find_assignable (self):
		number = 0
		while not self[number].is_assignable ():
			number += 1

		return self[number]
