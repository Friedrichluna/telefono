#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import fcntl
import logging
import os
import random

import linkat

from .CONSTANTS import RECORD_DIR
from .CONSTANTS import RECORD_PREFIX
from .CONSTANTS import RECORD_SUFFIX

from .CONSTANTS import RECORD_LIST_FILE
from .CONSTANTS import BACKUP_EXT

from .number import Number


class SubscriberType (enum.IntEnum):
	UNASSIGNED = 0
	UNUSED = 1
	RESERVED = 2
	RECORDING = 3
	LIST = 4
	CALLBACK = 5

class Subscriber ():
	def __init__ (self, network, number:Number, assignable:bool=True):
		self.log = logging.getLogger ("Subscriber(%s)" % number)

		self.__network = network
		self.__number = number

		if assignable:
			self.__type = SubscriberType.UNASSIGNED
		else:
			self.__type = SubscriberType.RESERVED

		self.__hidden = False

		return

	def __str__ (self):
		return "Subscriber(%s)" % self.__number

	def __repr__ (self):
		return "Subscriber(%s, %s)" % (self.__number, self.__type)

	def _validate_file (self):
		self.log.debug ("checking whether file '%s' exists",
		                self.__filename)

		if not self.__filename:
			return False

		if not os.path.isfile (self.__filename):
			self.log.warning ("file %s vanished",
			                  self.__filename)

			self.__filename = str ()
			return False

		return True

	def register_file (self):
		filename = ""
		filename += RECORD_DIR
		filename += "/"
		filename += RECORD_PREFIX
		filename += self.__number
		filename += RECORD_SUFFIX

		self.log.debug ("checking whether file '%s' exists",
		                filename)

		if os.path.isfile (filename):
			self.log.info ("file '%s' registered", filename)

			self.__filename = filename
			return True

		self.log.error ("file '%s' missing", filename)
		return False

	def __getattribute__ (self, name):
		if 'type' == name:
			return self.__type

		if 'number' == name:
			return self.__number

		if 'description' == name \
		and SubscriberType.UNASSIGNED != self.__type:
			return self.__description

		if 'exists' == name:
			if SubscriberType.RECORDING == self.__type:
				return self._validate_file ()

			return False

		if 'reserved' == name:
			if SubscriberType.RESERVED == self.__type:
				return True

			return False

		if 'hidden' == name:
			return self.__hidden

		if 'filename' == name \
		and SubscriberType.RECORDING == self.__type:
			if self.__filename:
				self.log.debug ("accessing filename")
				return self.__filename

			self.log.debug ("constructing filename")

			filename = ""
			filename += RECORD_DIR
			filename += "/"
			filename += RECORD_PREFIX
			filename += self.__number
			filename += RECORD_SUFFIX
			return filename

		if 'list' == name and SubscriberType.LIST == self.__type:
			# return immutable tuple
			return (*self.__list, )

		if 'callback' == name and SubscriberType.CALLBACK == self.__type:
			return self.__callback

		return super ().__getattribute__ (name)

	def __setattr__ (self, name, value):
		if 'type' == name:
			self.log.error ("attempting to change type")
			raise AttributeError ("read-only attribute")

		if 'number' == name:
			self.log.error ("attempting to change number")
			raise AttributeError ("read-only attribute")

		if 'description' == name:
			if not isinstance (value, str):
				raise TypeError (
				    "description must be str not %r" %
				    type (value))

			if SubscriberType.UNASSIGNED == self.__type:
				self.log.debug ("changed type "
				                "UNASSIGNED -> UNUSED")

				self.__type = SubscriberType.UNUSED
				self.__description = str ()

			self.log.debug ("set description to %r", value)

			if "" == value and "" == self.__description:
				return

			self.__description = value
			self.__network.sync_data ()
			return

		if 'exists' == name:
			self.log.error ("attempting to change exists")
			raise AttributeError ("read-only attribute")

		if 'reserved' == name \
		and SubscriberType.UNASSIGNED == self.__type:
			if not value:
				return

			self.log.debug ("changed type "
			                "UNASSIGNED -> RESERVED")

			self.__type = SubscriberType.RESERVED
			self.__description = str ()
			return

		if 'hidden' == name:
			if value:
				self.log.debug ("hiding number")
			else:
				self.log.debug ("unhiding number")

			self.__hidden = value
			return

		if 'filename' == name:
			if not isinstance (value, str):
				raise TypeError (
				    "filename must be str not %r" %
				    type (value))

			if SubscriberType.UNASSIGNED == self.__type:
				self.log.debug ("changed type "
				                "UNASSIGNED -> RECORDING")

				self.__type = SubscriberType.RECORDING
				self.__description = str ()
				self.__filename = str ()

			if SubscriberType.RECORDING == self.__type:
				self.log.debug ("set filename to %r", value)
				self.__filename = value
				self._validate_file ()
				return

		if 'list' == name and SubscriberType.UNASSIGNED == self.__type:
			self.log.debug ("changed type UNASSIGNED -> LIST")

			self.__type = SubscriberType.LIST
			self.__description = str ()
			self.__list = list ()

		if 'list' == name and SubscriberType.LIST == self.__type:
			for subscriber in value:
				if not isinstance (subscriber, Subscriber):
					number = Number (subscriber)
					subscriber = self.__network[number]

				if SubscriberType.RECORDING != subscriber.__type:
					raise ValueError ("unsupported subscriber")

				if subscriber in self.__list:
					self.log.debug ("skipping duplicate"
					                " subscriber %r",
					                subscriber)
					return

				self.log.debug ("add number %r",
				                subscriber)
				self.__list.append (subscriber)

			return


		if 'callback' == name and SubscriberType.UNASSIGNED == self.__type:
			self.log.debug ("changed type "
			                "UNASSIGNED -> CALLBACK")

			self.__type = SubscriberType.CALLBACK
			self.__description = str ()

		if 'callback' == name and SubscriberType.CALLBACK == self.__type:
			self.__callback = value
			self.log.debug ("add callback %r", value)
			return

		if 'callback' == name:
			raise AttributeError ()

		return super ().__setattr__ (name, value)

	def is_assignable (self) -> bool:

		if SubscriberType.UNASSIGNED == self.__type:
			return True

		return False

	def __route (self):
		if SubscriberType.UNASSIGNED == self.__type:
			return self

		if SubscriberType.RESERVED == self.__type:
			return self

		if SubscriberType.RECORDING == self.__type:
			return self

		if SubscriberType.LIST == self.__type:
			return random.choice (self.__list).__route ()

		if SubscriberType.CALLBACK == self.__type:
			return self

		raise NotImplementedError ("unknown subscriber type")

	def subroute (self, number:Number):
		subnumber = number.remove_base (self.__number)
		if not subnumber:
			# self isn't a base number
			self.log.debug ("%s isn't extending this number",
			                number)
			return None

		if SubscriberType.LIST == self.__type:
			if int (subnumber) >= len (self.__list):
				self.log.debug ("%s is no valid subscript",
				                number)
				return Subscriber (self.__network,
				                   number,
				                   assignable=False)

			self.log.debug ("selecting subnumber %s",
			                subnumber)
			return self.__list[int (subnumber)]

		# allow using subscripts for non-subscriptible numbers
		self.log.warn ("allow reusing possible prefix %s for %s",
		               self.__number, number)
		return None

	def __call (self, player, aloud, wind) -> bool:
		if SubscriberType.CALLBACK == self.__type:
			self.log.debug ("invoking callback with "
			                "player=%r, aloud=%r, wind=%r",
			                player, aloud, wind)

			return self.__callback (player, aloud, wind)

		if not self.exists:
			self.log.info ("number doesn't exist")
			player.play_sit_tone ()
			return False

		return player.play_file (self.filename, aloud, wind)

	def is_callable (self) -> bool:
		if SubscriberType.RECORDING == self.__type:
			return self.exists

		if SubscriberType.LIST == self.__type:
			for subscriber in self.__list:
				if subscriber.is_callable ():
					return True

			return False

		if SubscriberType.CALLBACK == self.__type:
			return True

		return False

	def outbound_call (self, player) -> bool:
		self.log.info ("outgoing call to %s", self.number)

		number = self.__route ()
		self.log.debug ("route call to %s", number.number)

		return number.__call (player, aloud=False, wind=True)

	def inbound_call (self, player, ring=True) -> bool:
		self.log.info ("incoming call from %s %s", self.number,
		               "" if ring else "(silent)")

		if ring and player.play_ring ():
			# never picked up
			return False

		number = self.__route ()
		self.log.debug ("route call to %s", number.number)

		return number.__call (player, aloud=(not ring), wind=False)

	def dial (self, number):
		return self.__network[self.__number + number]


class Network ():
	def __init__ (self, filename:str=RECORD_LIST_FILE):
		self.log = logging.getLogger ("Network")

		self.__subscribers = list ()
		self.__prevent_sync = False

		self.__filename = filename

		# previously crashed while writing
		# restore backup
		if not os.path.exists (self.__filename) \
		and os.path.exists (self.__filename + BACKUP_EXT):
			self.log.info ("restoring backup file")
			os.rename (self.__filename + BACKUP_EXT,
			           self.__filename)

		# load file
		if os.path.exists (self.__filename):
			self.log.info ("load recording metadata")
			with open (self.__filename, "rt") as f:
				self.__load (f)
		else:
			self.log.info ("create missing metadata file")
			os.mknod (self.__filename)

		return None

	def __find (self, number:Number) -> (int, bool):
		for index in range (len (self.__subscribers)):
			if number == self.__subscribers[index].number:
				return index, True
			if number < self.__subscribers[index].number:
				return index, False
		return len (self.__subscribers), False

	def __get (self, number:Number) -> Subscriber:
		index, exists = self.__find (number)

		if not exists:
			if 0 != index:
				# Because the subscriber list is sorted,
				# a potential base number will always
				# be the preceding one.
				base_number = self.__subscribers[index-1]

				subscriber = base_number.subroute (number)
				if None is not subscriber:
					return subscriber

			# assignable
			subscriber = Subscriber (self, number)
			self.__subscribers.insert (index, subscriber)

			self.log.debug ("creating %r on access",
			                subscriber)

			return subscriber

		return self.__subscribers[index]

	def __del (self, number:Number) -> Subscriber:
		index, exists = self.__find (number)

		if not exists:
			self.log.warning ("failed to deleting "
			                  "non-existing subscriber %s",
			                  number)
			return None

		subscriber = self.__subscribers[index]
		self.__subscribers.__delitem__ (index)

		self.log.debug ("deleting %r", subscriber)
		return subscriber

	def __contains__ (self, number:Number):
		index, exists = self.__find (Number (number))

		if not exists:
			return False

		return self.__subscribers[index].exists

	def __getitem__ (self, number:Number):
		return self.__get (Number (number))

	def __delitem__ (self, number:Number):
		ret = self.__del (Number (number))
		self.log.debug ("deleting %s", ret)
		self.sync_data ()
		return


	def __iter__ (self):
		l = list (self.numbers ())
		l.sort (key=int)
		return iter (l)

	def __len__ (self):
		length = 0
		for subscriber in self.__subscribers:
			if subscriber.exists:
				length += 1
		return length


	def numbers (self):
		for subscriber in self.__subscribers:
			if subscriber.exists and not subscriber.hidden:
				yield subscriber.number

	def pop (self, number:Number):
		ret = self.__del (Number (number))
		self.log.debug ("deleting %s", ret)
		self.sync_data ()
		return ret

	def __load (self, _file):
		self.log.debug ("reading metadata")

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
				self.log.warning ("ignoring malformed "
				                  "line %d" % (lineno+1))
				continue

			number = line[:index]
			name = line[index+1:]

			number = number.strip ()
			name = name.strip ()

			try:
				number = Number (number)
			except ValueError:
				self.log.error ("Key is not a number! "
				                "Ignoring line")
				continue

			# create subscriber
			self[number].filename = ""

			# ignore empty names
			if not name:
				continue

			self[number].description = name

		self.__prevent_sync = False

		fcntl.flock(_file, fcntl.LOCK_UN)
		return

	def __store (self, _file):
		self.log.debug ("writing metadata")

		fcntl.flock(_file, fcntl.LOCK_EX)

		_file.truncate ()

		# sort file numerically
		subscribers = self.__subscribers.copy ()
		subscribers.sort (key=lambda s: int (s.number))

		for subscriber in subscribers:
			# only recordings and described numbers belong
			# into the file, other types (unassigned, reserved,
			# lists, callbacks) are created at runtime
			if SubscriberType.RECORDING != subscriber.type \
			and SubscriberType.UNUSED != subscriber.type:
				continue

			name = subscriber.description.strip ()

			# ignore empty names
			if not name:
				continue

			_file.write (str (subscriber.number))
			_file.write (": ")
			_file.write (name)
			_file.write ("\n")

		_file.flush ()

		fcntl.flock(_file, fcntl.LOCK_UN)
		return


	def sync_data (self):
		if self.__prevent_sync:
			return

		self.log.info ("store recording metadata")

		# create temporary file
		self.log.debug ("create temporary file")
		fd = os.open (os.path.dirname (self.__filename),
		              os.O_TMPFILE | os.O_WRONLY,
		              mode=0o600)

		# create backup file
		if os.path.exists (self.__filename):
			self.log.debug ("rename existing file %s -> %s",
			                self.__filename,
			                self.__filename + BACKUP_EXT)
			os.rename (self.__filename,
			           self.__filename + BACKUP_EXT)

		# store into temporary file
		f = os.fdopen (fd, "wt")
		self.__store (f)

		self.log.debug ("saving file %s", self.__filename)

		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % fd,
		                linkat.AT_FDCWD, self.__filename.encode(),
		                linkat.AT_SYMLINK_FOLLOW)

		f.close ()

		return

	def sync_fs (self, directory:str=RECORD_DIR):
		self.log.info ("scan for existing recordings")

		for subscriber in self.__subscribers:
			if SubscriberType.RECORDING == subscriber.type:
				subscriber._validate_file ()

		for file in os.listdir (directory):
			path = os.path.join (directory, file)

			if os.path.isfile (path) \
			and file.startswith (RECORD_PREFIX) \
			and file.endswith (RECORD_SUFFIX):
				self.log.debug ("found %s", path)

				file = file[len(RECORD_PREFIX) :]
				file = file[: -len(RECORD_SUFFIX)]
				number = Number (file)

				subscriber = self[number]
				if not subscriber.exists:
					subscriber.filename = path

		return

	def compact (self):
		self.log.debug ("compact subscriber list")
		# remove useless entries
		for subscriber in self.__subscribers:
			if SubscriberType.UNASSIGNED == subscriber.__type:
				self.log.debug ("remove %r", subscriber)
				self.__subscribers.remove (subscriber)

		return

	def get_random (self):
		numbers = list (self.numbers ())
		if not numbers:
			return None

		subscriber = self[random.choice (numbers)]
		self.log.debug ("chose random %r", subscriber)

		return subscriber

	def find_assignable (self):
		self.log.debug ("find assignable number")
		number = 0
		subscriber = self[Number.from_int (number)]
		while not subscriber.is_assignable ():
			number += 1
			subscriber = self[Number.from_int (number)]

		self.log.debug ("found %d", number)

		# register subscriber
		subscriber.filename = ""
		return subscriber
