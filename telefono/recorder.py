#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import time

import linkat
import pyaudio
import wave

from .CONSTANTS import RECORD_DELAY
from .CONSTANTS import RECORD_TIME_MIN
from .CONSTANTS import RECORD_TIME_MAX


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


def record (records, tts, PickUp, ButtonLeft, ButtonMiddle):
	record = records.add_next ()
	tts.say("Aufnahme Nr.: " + str(record.number) + " wird gestartet")

	aborted = False
	recordingTime = 0
	with Recorder (record.filename, led) as recorder:

		while recordingTime <= RECORD_TIME_MAX \
		and PickUp.is_pressed \
		and not ButtonLeft.is_released \
		and not aborted:
			time.sleep (RECORD_DELAY)
			recordingTime += 1

			if ButtonMiddle.is_released:
				aborted = True

		if recordingTime > RECORD_TIME_MIN and not aborted:
			recorder.save ()
			records.sync_fs ()

	if recordingTime > RECORD_TIME_MAX:
		tts.say("Aufnahme Nr.: " + str(record.number) + "wegen overtime beendet.")
	elif aborted:
		tts.say("Aufnahme Nr.: " + str(record.number) + " abgebrochen")
	elif recordingTime <= RECORD_TIME_MIN:
		tts.say ("Aufnahme zu kurz")
	else:
		print ("Aufnahme Nr.: " + str(record.number) + " beendet.")

	return
