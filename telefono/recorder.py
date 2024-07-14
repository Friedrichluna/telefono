#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os

import linkat
import pyaudio
import wave


CHANNELS = 2
RATE = 44100
FRAME_PER_BUFFER = 512

class Recorder ():
	def __init__ (self, fname, indicator,
	              channels=CHANNELS, rate=RATE,
	              frames_per_buffer=FRAME_PER_BUFFER):

		self.fname = fname
		self.indicator = indicator
		self._pa = pyaudio.PyAudio ()

		# Use a stream with a callback in non-blocking mode
		self._stream = self._pa.open (format=pyaudio.paInt16,
		                              channels=channels,
		                              rate=rate,
		                              input=True,
		                              frames_per_buffer=frames_per_buffer,
		                              stream_callback=self.__on_data)

		# create temporary file
		self.fd = os.open (os.path.dirname (self.fname),
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
		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % self.fd,
		                linkat.AT_FDCWD, self.fname.encode(),
		                linkat.AT_SYMLINK_FOLLOW)
		return

	def __enter__ (self):
		self.indicator.on ()
		self._stream.start_stream ()

		return self

	def __exit__ (self, exception, value, traceback):
		self._stream.stop_stream ()
		self.indicator.off ()

		self._stream.close ()
		self._pa.terminate ()
		self.wavefile.close ()
		return False
