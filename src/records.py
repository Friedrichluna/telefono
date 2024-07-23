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


class RecordType:
	RECORDING = 0

class Record ():
	def __init__ (self, number:int, description:str,
	              exists:bool=False,
	              type:RecordType=RecordType.RECORDING,
	              records=None):

		self.__records = records
		self.__number = number
		self.__description = description
		self.__exists = exists
		self.__type = type
		return

	def __getattribute__ (self, name):
		if 'number' == name:
			return self.__number

		if 'exists' == name:
			return self.__exists

		if 'description' == name:
			return self.__description

		if 'filename' == name:
			filename = ""
			filename += RECORD_DIR
			filename += "/"
			filename += RECORD_PREFIX
			filename += str(self.__number)
			filename += RECORD_SUFFIX
			return filename

		return super ().__getattribute__ (name)

	def __setattr__ (self, name, value):
		if 'number' == name:
			raise AttributeError ("read-only attribute")

		if 'exists' == name:
			self.__exists = value
			return

		if 'description' == name:
			self.__description = value
			if None is not self.__records:
				self.__records.sync_data ()
			return

		if 'filename' == name:
			raise AttributeError ("read-only attribute")

		return super ().__setattr__ (name, value)


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

	def __find (self, number):
		for index in range (len (self.__data)):
			if number == str (self.__data[index].number):
				return index, True
			if number < str (self.__data[index].number):
				return index, False
		return None, False

	def __get (self, number, default=None):
		index, exists = self.__find (number)

		if exists:
			return self.__data[index]

		return default

	def __set (self, number, record, keep=False):
		index, exists = self.__find (number)

		if None is index:
			self.__data.append (record)
			return

		if not exists:
			self.__data.insert (index, record)
			return

		if keep:
			return

		self.__data[index] = record
		return

	def __del (self, number):
		index, exists = self.__find (number)

		if not exists:
			return None

		record = self.__data[index]
		self.__data.__delitem__ (index)
		return record

	def __contains__ (self, key):
		record = self.__get (str (key))

		if None is record:
			return False

		return record.exists

	def __getitem__ (self, key):
		return self.__get (str (key))

	def __setitem__ (self, key, value):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (value):
			raise TypeError (
			      "Invalid value %s, must be str not %s."
			      % (repr(value), type (value)))

		self.__set (str (key), Record (key, value, records=self))
		self.sync_data ()
		return

	def __delitem__ (self, key):
		self.__del (str (key))
		self.sync_data ()
		return


	def __iter__ (self):
		l = list (self.keys ())
		l.sort ()
		return iter (l)

	def __len__ (self):
		length = 0
		for record in self.__data:
			if record.exists:
				length += 1
		return length

	def __reversed__ (self):
		raise NotImplementedError


	def clear (self):
		self.__data.clear ()
		self.sync_data ()
		return

	def copy (self):
		c = Records ()
		c.__data = self.__data.copy ()
		return c

	def get (self, key, default=None):
		return self.__get (str (key), default)

	def items (self):
		for record in self.__data:
			if record.exists:
				yield record

	def keys (self):
		for record in self.__data:
			if record.exists:
				yield record.number

	def pop (self, number):
		ret = self.__del (str (number))
		self.sync_data ()
		return ret

	def setdefault (self, key, default=""):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (default):
			raise TypeError (
			      "Invalid default %s, must be str not %s."
			      % (repr(default), type (default)))

		self.__set (str (key), Record (key, default, records=self),
		            keep=True)
		self.sync_data ()
		return self.__get (str (key))

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

			self[number] = name

		self.__prevent_sync = False

		fcntl.flock(_file, fcntl.LOCK_UN)
		return

	def __store (self, _file):
		fcntl.flock(_file, fcntl.LOCK_EX)

		_file.truncate ()

		numbers = [record.number for record in self.__data]
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
		for record in self.__data:
			record.exists = False
		return

	def __validate (self, number):
		self.setdefault (number)
		self.__get (str (number)).exists = True
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
				record = int (file)

				self.__validate (record)
		return

	def get_random (self):
		if not self.__data:
			return None

		return int (random.choice (self.__data).number)

	def add_next (self):
		number = 0
		while number in self:
			number += 1

		# generate new Record
		return self.setdefault (number)
