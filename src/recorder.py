#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import fcntl
import logging
import os
import subprocess
import time

import linkat
import pyaudio

from .CONSTANTS import RECORD_DELAY
from .CONSTANTS import RECORD_TIME_MIN
from .CONSTANTS import RECORD_TIME_MAX
from .CONSTANTS import RECORD_ENCODE_CMD
from .CONSTANTS import RECORD_ENCODE_TIMEOUT
from .CONSTANTS import RECORD_PIPE_SIZE

from .audio import fd_path
from .network import sync_dir

class RECORDER_RESULT (enum.IntEnum):
	ERROR = 0
	ABORT = 1
	END = 2
	MIN_TIME = 3
	MAX_TIME = 4


CHANNELS = 2
RATE = 44100
FRAME_PER_BUFFER = 512

class Recorder ():
	def __init__ (self, subscriber, indicator,
	              channels=CHANNELS, rate=RATE,
	              frames_per_buffer=FRAME_PER_BUFFER):
		self.log = logging.getLogger ("Recorder(%s)"
		                              % subscriber.filename)

		self.__subscriber = subscriber
		self.indicator = indicator

		self.log.debug ("setting up PyAudio")
		self._pa = pyaudio.PyAudio ()

		# Use a stream with a callback in non-blocking mode
		self._stream = self._pa.open (format=pyaudio.paInt16,
		                              channels=channels,
		                              rate=rate,
		                              input=True,
		                              frames_per_buffer=frames_per_buffer,
		                              stream_callback=self.__on_data)

		self.log.debug ("setting up file")
		# create temporary file
		self.fd = os.open (os.path.dirname (subscriber.filename),
		                   os.O_TMPFILE | os.O_WRONLY,
		                   mode=0o600)

		self.file = os.fdopen (self.fd, "wb")

		# ffmpeg encodes the samples to mp3 while recording, so
		# nobody waits for it afterwards; it writes into the
		# temporary file (errors go to the journal)
		self.log.debug ("starting encoder")
		self.encoder = subprocess.Popen ((*RECORD_ENCODE_CMD (channels, rate),
		                                  fd_path (self.file)),
		                                 stdin=subprocess.PIPE,
		                                 stdout=subprocess.DEVNULL,
		                                 pass_fds=(self.fd, ))

		# the callback must not block while ffmpeg starts
		fcntl.fcntl (self.encoder.stdin, fcntl.F_SETPIPE_SZ,
		             RECORD_PIPE_SIZE)
		return

	def __on_data (self, in_data, frame_count, time_info, status):
		try:
			self.encoder.stdin.write (in_data)

		# ffmpeg is gone (BrokenPipeError) or already finished
		except (OSError, ValueError) as error:
			self.log.error ("encoder takes no more data: %s", error)
			return None, pyaudio.paAbort

		return None, pyaudio.paContinue

	# end of input, ffmpeg completes the mp3
	def __finish_encoder (self) -> bool:
		try:
			self.encoder.stdin.close ()

		except OSError as error:
			self.log.error ("encoder takes no more data: %s", error)

		try:
			returncode = self.encoder.wait (RECORD_ENCODE_TIMEOUT)

		except subprocess.TimeoutExpired:
			self.log.error ("encoder did not finish within %d s",
			                RECORD_ENCODE_TIMEOUT)
			self.__kill_encoder ()
			return False

		if 0 != returncode:
			self.log.error ("encoder failed (%d)", returncode)
			return False

		return True

	def __kill_encoder (self):
		if None is self.encoder.poll ():
			self.encoder.kill ()
			self.encoder.wait ()

		try:
			self.encoder.stdin.close ()

		# unwritten data in the buffer
		except OSError:
			pass

		return

	def save (self):
		self.log.debug ("saving recording file")

		# finish the file before it becomes visible: stop the
		# input so nothing is written after the fsync, let ffmpeg
		# finish the mp3 and make sure everything is on the
		# disk (power loss)
		self._stream.stop_stream ()
		if not self.__finish_encoder ():
			return False

		os.fsync (self.fd)

		# atomically link file
		filename = self.__subscriber.filename.encode()
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % self.fd,
		                linkat.AT_FDCWD, filename,
		                linkat.AT_SYMLINK_FOLLOW)

		# make the link durable
		sync_dir (os.path.dirname (self.__subscriber.filename))

		# register created file
		return self.__subscriber.register_file ()

	def __enter__ (self):
		self.log.info ("start recording")

		self.indicator.on ()
		self._stream.start_stream ()

		return self

	def __exit__ (self, exception, value, traceback):
		self.log.info ("stop recording")

		self._stream.stop_stream ()
		self.indicator.off ()

		self._stream.close ()
		self._pa.terminate ()

		# not saved (aborted, too short, error): discard it all
		self.__kill_encoder ()
		self.file.close ()
		return False


	def record (self, end, abort):
		timer = 0

		with self:
			while timer <= RECORD_TIME_MAX and not end ():
				# tick
				time.sleep (RECORD_DELAY)
				timer += 1

				if abort ():
					self.log.info ("recording aborted")
					return RECORDER_RESULT.ABORT

			if timer <= RECORD_TIME_MIN:
				self.log.info ("recording to short")
				return RECORDER_RESULT.MIN_TIME

			if not self.save ():
				self.log.info ("recording failed")
				return RECORDER_RESULT.ERROR

		if timer > RECORD_TIME_MAX:
			self.log.info ("reached maximal recording time %ds",
			               RECORD_TIME_MAX * RECORD_DELAY)
			return RECORDER_RESULT.MAX_TIME

		self.log.info ("finished recording")
		return RECORDER_RESULT.END
