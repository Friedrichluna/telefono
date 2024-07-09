#!/usr/bin/python3
# -*- coding: utf-8 -*-

import fcntl
import os

import linkat

try:
	from .CONSTANTS import RECORD_DIR
	from .CONSTANTS import RECORD_PREFIX
	from .CONSTANTS import RECORD_SUFFIX

	from .CONSTANTS import RECORD_LIST_FILE
	from .CONSTANTS import BACKUP_EXT

except:
	from CONSTANTS import RECORD_DIR
	from CONSTANTS import RECORD_PREFIX
	from CONSTANTS import RECORD_SUFFIX

	from CONSTANTS import RECORD_LIST_FILE
	from CONSTANTS import BACKUP_EXT


class Records ():
	def __init__ (self, filename:str=RECORD_LIST_FILE):
		self.__data = dict ()
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

	def __contains__ (self, key):
		return self.__data.get (key, (..., False))[1]

	def __getitem__ (self, key):
		return self.__data.__getitem__ (key)[0]

	def __setitem__ (self, key, value):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (value):
			raise TypeError (
			      "Invalid value %s, must be str not %s."
			      % (repr(value), type (value)))

		ret = self.__data.__setitem__ (key, (value, False))

		self.sync_data ()
		return ret

	def __delitem__ (self, key):
		ret = self.__data.__delitem__ (key)

		self.sync_data ()
		return ret


	def __iter__ (self):
		l = list(self.keys())
		l.sort()
		return iter(l)

	def __len__ (self):
		length = 0
		for key, (value, exists) in self.__data.items ():
			if exists:
				length += 1
		return length

	def __reversed__ (self):
		raise NotImplementedError


	def clear (self):
		ret = self.__data.clear ()

		self.sync_data ()
		return ret

	def copy (self):
		c = Records ()
		c.__data = self.__data.copy ()
		return c

	def get (self, key, default=""):
		return self.__data.get (key, (default, ))[0]

	def items (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield (key, value)

	def keys (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield key

	def pop (self, key, *args, **kwargs):
		ret = self.__data.pop (key, *args, **kwargs)[0]

		self.sync_data ()
		return ret

	def popitem (self):
		ret = self.__data.popitem ()[0]

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

		ret = self.__data.setdefault (key, (default, False))

		self.sync_data ()
		return ret

	def update (self, *args, **kwargs):
		raise NotImplementedError

	def values (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield value

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

		keys = self.__data.keys ()
		keys = list (keys)
		keys.sort ()

		for key in keys:
			name = self[key].strip ()

			# ignore empty names
			if not name:
				continue

			_file.write (str (key))
			_file.write (": ")
			_file.write (name)
			_file.write ("\n")

		_file.flush ()

		fcntl.flock(_file, fcntl.LOCK_UN)
		return

	def __invalidate_fs (self):
		for key, (value, exists) in self.__data.items ():
			self.__data[key] = (value, False)
		return

	def __validate (self, key):
		self.setdefault (key)
		self.__data[key] = (self.__data[key][0], True)
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
