#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import logging
import os
import time

import linkat
import pyaudio
import wave

from .CONSTANTS import RECORD_DELAY
from .CONSTANTS import RECORD_TIME_MIN
from .CONSTANTS import RECORD_TIME_MAX

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

		self.wavefile = wave.open (os.fdopen (self.fd, "wb"), "w")
		self.wavefile.setnchannels (channels)
		self.wavefile.setsampwidth (self._pa.get_sample_size (pyaudio.paInt16))
		self.wavefile.setframerate (rate)
		return

	def __on_data (self, in_data, frame_count, time_info, status):
		self.wavefile.writeframes (in_data)
		return None, pyaudio.paContinue

	def save (self):
		self.log.debug ("saving recording file")

		# atomically link file
		filename = self.__subscriber.filename.encode()
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % self.fd,
		                linkat.AT_FDCWD, filename,
		                linkat.AT_SYMLINK_FOLLOW)

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
		self.wavefile.close ()
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
