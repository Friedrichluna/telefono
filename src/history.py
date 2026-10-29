#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import threading
import time

from .CONSTANTS import HISTORY_FILE
from .CONSTANTS import HISTORY_MAX_SIZE
from .CONSTANTS import HISTORY_KEEP_SIZE


log = logging.getLogger ("History")


# what happened on the phone (handset, calls, recordings, webapp
# requests), shown on the webapp's status page: one JSON object per
# line, e.g. {"time":1730000000.0,"event":"call","number":"88",...};
# only the main process writes, the webapp reads the file itself (the
# main process does not answer it while the phone is used)
#
# SD card: an event is one write () at the end of the file, without
# fsync, so a power loss loses the last events (at most a torn last
# line, which the reader skips); above HISTORY_MAX_SIZE the oldest
# events are dropped (rewritten atomically, HISTORY_KEEP_SIZE are kept)
class History ():
	def __init__ (self, filename:str=HISTORY_FILE):
		self.filename = filename

		self.__fd = None
		self.__inode = None
		self.__size = 0

		# an error is only logged once (until it works again)
		self.__failed = False
		return

	# never raises: the phone works on without its history
	def add (self, event:str, **data):
		try:
			entry = {"time": round (time.time (), 1), "event": event}
			entry.update (data)

			# e.g. a Number is stored as its digits
			line = json.dumps (entry, ensure_ascii=False,
			                   separators=(",", ":"), default=str)

			self.__append ((line + "\n").encode ())

		except Exception as error:
			self.__close ()

			if not self.__failed:
				log.error ("history %s: %r, events are not stored"
				           " (only logged once)",
				           self.filename, error)
			self.__failed = True
			return

		if self.__failed:
			log.info ("history %s works again", self.filename)
			self.__failed = False

		return

	def __open (self):
		fd = os.open (self.filename,
		              os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC,
		              0o600)

		try:
			stat = os.fstat (fd)

			# the last line was torn (power loss): end it, so the
			# next event is a line of its own
			if stat.st_size and b"\n" != os.pread (fd, 1, stat.st_size - 1):
				os.write (fd, b"\n")

		except BaseException:
			os.close (fd)
			raise

		self.__fd = fd
		self.__inode = (stat.st_dev, stat.st_ino)
		self.__size = os.fstat (fd).st_size
		return

	def __close (self):
		if self.__fd is not None:
			fd, self.__fd = self.__fd, None
			try:
				os.close (fd)
			except OSError:
				pass

		return

	def __append (self, data:bytes):
		# opened again if the file was removed or replaced
		if self.__fd is not None:
			try:
				stat = os.stat (self.filename)
				if (stat.st_dev, stat.st_ino) != self.__inode:
					self.__close ()

			except FileNotFoundError:
				self.__close ()

		if self.__fd is None:
			self.__open ()

		os.write (self.__fd, data)
		self.__size += len (data)

		if self.__size > HISTORY_MAX_SIZE:
			self.__trim ()

		return

	# keeps the newest HISTORY_KEEP_SIZE bytes (whole lines): written
	# to a new file, which replaces the old one (a power loss leaves
	# the old or the new file, both complete)
	def __trim (self):
		size = os.fstat (self.__fd).st_size
		start = max (0, size - HISTORY_KEEP_SIZE)
		data = os.pread (self.__fd, size - start, start)

		# from the first complete line on
		if start:
			data = data[data.find (b"\n") + 1:]

		new = self.filename + ".new"
		fd = os.open (new, os.O_WRONLY | os.O_CREAT | os.O_TRUNC
		                   | os.O_CLOEXEC, 0o600)
		try:
			os.write (fd, data)
			os.fsync (fd)
		finally:
			os.close (fd)

		os.replace (new, self.filename)
		log.info ("history trimmed to %d bytes", len (data))

		self.__close ()
		self.__open ()
		return


# the events of the main process
history = History ()


# reads the history for the webapp: only what was added since the last
# call is read and parsed (the file is only appended to), the whole
# file again when it was replaced (trimmed); lines that are no JSON
# object (torn by a power loss) are skipped
class HistoryReader ():
	def __init__ (self, filename:str=HISTORY_FILE):
		self.filename = filename

		self.__lock = threading.Lock ()
		self.__inode = None
		self.__offset = 0
		self.__events = list ()
		return

	# all events, oldest first (a list the caller must not change);
	# raises OSError if the file can not be read (an empty list if it
	# does not exist yet)
	def read (self) -> list:
		with self.__lock:
			try:
				f = open (self.filename, "rb")

			except FileNotFoundError:
				self.__inode = None
				self.__events = list ()
				return self.__events

			with f:
				stat = os.fstat (f.fileno ())
				inode = (stat.st_dev, stat.st_ino)

				if inode != self.__inode or stat.st_size < self.__offset:
					self.__inode = inode
					self.__offset = 0
					self.__events = list ()

				f.seek (self.__offset)
				data = f.read ()

			# only complete lines, the rest is read again next time
			end = data.rfind (b"\n") + 1
			self.__offset += end

			events = list ()
			for line in data[:end].split (b"\n"):
				event = parse_event (line)
				if event is not None:
					events.append (event)

			# a new list, so callers can keep the old one
			if events:
				self.__events = self.__events + events

			return self.__events


def parse_event (line:bytes):
	try:
		event = json.loads (line)

	except ValueError:
		return None

	if not isinstance (event, dict) \
	or not isinstance (event.get ("time"), (int, float)) \
	or not isinstance (event.get ("event"), str):
		return None

	return event
