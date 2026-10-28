#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import fcntl
import logging
import os
import subprocess
import time

from .CONSTANTS import RING_FILE

from .CONSTANTS import SOX_DIAL
from .CONSTANTS import SOX_BUSY
from .CONSTANTS import SOX_RELEASE
from .CONSTANTS import SOX_DIAL_SECONDARY
from .CONSTANTS import SOX_SIT

from .CONSTANTS import SOX_NUMBER_1
from .CONSTANTS import SOX_NUMBER_2
from .CONSTANTS import SOX_NUMBER_3
from .CONSTANTS import SOX_NUMBER_4
from .CONSTANTS import SOX_NUMBER_5
from .CONSTANTS import SOX_NUMBER_6
from .CONSTANTS import SOX_NUMBER_7
from .CONSTANTS import SOX_NUMBER_8
from .CONSTANTS import SOX_NUMBER_9
from .CONSTANTS import SOX_NUMBER_S
from .CONSTANTS import SOX_NUMBER_0
from .CONSTANTS import SOX_NUMBER_R
from .CONSTANTS import SOX_NUMBER_A
from .CONSTANTS import SOX_NUMBER_B
from .CONSTANTS import SOX_NUMBER_C
from .CONSTANTS import SOX_NUMBER_D

from .CONSTANTS import FFPLAY_CMD
from .CONSTANTS import FFPLAY_START
from .CONSTANTS import FFPLAY_VOLUME
from .CONSTANTS import FFPLAY_POLL_DELAY
from .CONSTANTS import FFPLAY_STALL_TIMEOUT
from .CONSTANTS import FFPLAY_STALL_RETRIES
from .CONSTANTS import FFPLAY_KILL_TIMEOUT

from .CONSTANTS import FFPLAY_ENV

from .CONSTANTS import ESPEAK_CMD
from .CONSTANTS import ESPEAK_SPEED
from .CONSTANTS import ESPEAK_AMPLITUDE
from .CONSTANTS import ESPEAK_VOICE
from .CONSTANTS import ESPEAK_TEXT

from .CONSTANTS import TTS_SPEED
from .CONSTANTS import TTS_AMPLITUDE
from .CONSTANTS import TTS_VOICE

from .CONSTANTS import WIND_TIME

from .CONSTANTS import NO_NUMBER_DELAY
from .CONSTANTS import NO_NUMBER_TIMEOUT

from .CONSTANTS import BUSY_DELAY
from .CONSTANTS import BUSY_TIMEOUT

from .CONSTANTS import TONE_DELAY
from .CONSTANTS import RELEASE_DELAY
from .CONSTANTS import SAY_DELAY

from .CONSTANTS import TIME_FORMAT

from .recorder import RECORDER_RESULT


class Player ():
	def __init__ (self, hook, wind_back, wind_forward, speaker):
		self.log = logging.getLogger ("Player")

		self.__hook = hook
		self.__wind_back = wind_back
		self.__wind_forward = wind_forward
		self.__speaker = speaker
		self.__process = None

		return

	def __on_hook (self):
		return not self.__hook.is_pressed

	def __off_hook (self):
		return self.__hook.is_pressed

	def __never (self):
		return False

	def __back (self):
		return self.__wind_back.is_released

	def __forward (self):
		return self.__wind_forward.is_released

	def __ffplay (self, filename, start=0, volume=100):
		command = (*FFPLAY_CMD, filename,
		           *FFPLAY_START, str (start),
		           *FFPLAY_VOLUME, str (volume))

		self.log.debug ("invoking ffplay: %s", repr (command))

		process = subprocess.Popen (command,
		                            stderr=subprocess.PIPE,
		                            env=FFPLAY_ENV,
		                            text=False)

		# make fd non-blocking
		fd = process.stderr.fileno ()
		fcntl.fcntl (fd, fcntl.F_SETFL, os.O_NONBLOCK)

		return process

	def __stop_ffplay (self, process):
		# terminate ffplay, kill it if it doesn't exit and reap it
		process.terminate ()
		try:
			process.wait (FFPLAY_KILL_TIMEOUT)
		except subprocess.TimeoutExpired:
			self.log.warning ("ffplay didn't terminate, killing it")
			process.kill ()
			try:
				process.wait (FFPLAY_KILL_TIMEOUT)
			except subprocess.TimeoutExpired:
				self.log.error ("failed to kill ffplay (pid %d)",
				                process.pid)

		process.stderr.close ()
		return

	@staticmethod
	def __parse_ffplay_output (buffer) -> float:
		end = buffer.rfind (b" M-A:")
		if -1 == end:
			return None

		start = buffer.rfind (b" ", 0, end)
		if -1 == start:
			return None

		if b"nan" == buffer[start:end]:
			return None

		try:
			number = float (buffer[start:end])
		except ValueError:
			return None

		return number

	def __play (self, filename, abort, volume=100,
	            aloud=False, wind=False) -> bool:

		self.log.debug ("play file %s, abort=%s, "
		                "volume=%d, aloud=%s, wind=%s",
		                filename, repr (abort),
		                volume, repr (aloud), repr (wind))

		if not os.path.exists (filename):
			self.log.error ("file doesn't exist")
			return True

		if abort ():
			return False

		aborted = False

		if aloud:
			self.__speaker.activate ()


		process = self.__ffplay (filename, volume=volume)

		buffer = bytearray ()
		start = 0

		# watchdog: last time the position changed
		progress = time.monotonic ()
		stalls = 0

		while process.poll () is None:
			time.sleep (FFPLAY_POLL_DELAY)

			if abort ():
				self.__stop_ffplay (process)
				aborted = True
				break

			# parse current timestamp
			data = process.stderr.read ()
			if data is not None:
				buffer += data
				if 128 < len (buffer):
					buffer = buffer[-128:]

				_pos = self.__parse_ffplay_output (buffer)
				if _pos is not None:
					if _pos != start:
						progress = time.monotonic ()
					start = _pos
					buffer.clear ()
					self.log.debug ("duration: %f", start)

			# Sometimes ffplay starts, but neither produces output nor
			# exits (that's what pygame was initialised for once).
			if FFPLAY_STALL_TIMEOUT < time.monotonic () - progress:
				self.__stop_ffplay (process)

				if FFPLAY_STALL_RETRIES <= stalls:
					self.log.error ("ffplay stalled %d times, "
					                "giving up on %s",
					                stalls + 1, filename)
					break

				stalls += 1
				self.log.warning ("ffplay stalled at %f in %s, "
				                  "restarting (%d/%d)",
				                  start, filename, stalls,
				                  FFPLAY_STALL_RETRIES)
				buffer.clear ()
				process = self.__ffplay (filename,
				                         start,
				                         volume)
				progress = time.monotonic ()
				continue

			if wind and self.__back ():
				self.__stop_ffplay (process)
				start -= WIND_TIME

				self.log.debug ("wind back to %d", start)
				process = self.__ffplay (filename,
				                         start,
				                         volume)
				progress = time.monotonic ()


			if wind and self.__forward ():
				self.__stop_ffplay (process)
				start += WIND_TIME

				self.log.debug ("wind forward to %d", start)
				process = self.__ffplay (filename,
				                         start,
				                         volume)
				progress = time.monotonic ()

		if aloud:
			self.__speaker.deactivate ()

		if abort ():
			aborted = True

		return not aborted

	def play_system_sound (self, filename:str) -> True:
		return self.__play (filename,
		                    abort=self.__never, aloud=True)

	def play_ring (self):
		self.__play (RING_FILE, abort=self.__off_hook,
		             volume=70, aloud=True)

	def play_file (self, filename:str, aloud, wind) -> bool:
		return self.__play (filename, abort=self.__on_hook,
		                    aloud=aloud, wind=wind)


	def start_tone (self, command, aloud=False):
		self.stop_tone ()

		if aloud:
			self.__speaker.activate ()

		self.__process = subprocess.Popen (command,
		                                   stderr=subprocess.DEVNULL)
		return

	def stop_tone (self, aloud=False):
		if self.__process is not None:
			self.log.debug ("aborting tone")
			self.__process.terminate ()
			self.__process = None

		if aloud:
			self.__speaker.deactivate ()

		return

	def play_tone (self, command):
		self.start_tone (command)

		while self.__process.poll () is None:
			time.sleep (TONE_DELAY)

		self.stop_tone ()
		return

	def start_dial_tone (self):
		self.log.debug ("starting dial tone")
		self.start_tone (SOX_DIAL)
		return

	def start_busy_tone (self):
		self.log.debug ("starting busy tone")
		self.start_tone (SOX_BUSY)
		return

	def play_busy_tone (self):
		self.start_busy_tone ()

		timer = 0
		while timer < BUSY_TIMEOUT:
			if not self.__off_hook ():
				self.stop_tone ()
				return False

			time.sleep (BUSY_DELAY)
			timer += 1

		return self.play_release_tone ()

	def start_release_tone (self):
		self.log.debug ("starting release tone")
		self.start_tone (SOX_RELEASE)
		return

	def play_release_tone (self):
		self.start_release_tone ()

		while self.__off_hook ():
			time.sleep (RELEASE_DELAY)

		self.stop_tone ()
		return

	def start_secondary_dial_tone (self):
		self.log.debug ("starting secondary dial tone")
		self.start_tone (SOX_DIAL_SECONDARY)
		return

	def start_sit_tone (self, aloud=False):
		self.log.debug ("starting SIT tone")
		self.start_tone (SOX_SIT, aloud)
		return

	def play_sit_tone (self, aloud=False):
		self.start_sit_tone (aloud)

		timer = 0
		while timer < NO_NUMBER_TIMEOUT:
			if not self.__off_hook ():
				self.stop_tone ()
				return False

			time.sleep (NO_NUMBER_DELAY)
			timer += 1

		self.stop_tone (aloud)
		return True

	def dial_sound (self, number):

		if 1 == number:
			command = SOX_NUMBER_1
		elif 2 == number:
			command = SOX_NUMBER_2
		elif 3 == number:
			command = SOX_NUMBER_3
		elif 4 == number:
			command = SOX_NUMBER_4
		elif 5 == number:
			command = SOX_NUMBER_5
		elif 6 == number:
			command = SOX_NUMBER_6
		elif 7 == number:
			command = SOX_NUMBER_7
		elif 8 == number:
			command = SOX_NUMBER_8
		elif 9 == number:
			command = SOX_NUMBER_9
		elif "*" == number:
			command = SOX_NUMBER_S
		elif 0 == number:
			command = SOX_NUMBER_0
		elif "#" == number:
			command = SOX_NUMBER_R
		elif "A" == number:
			command = SOX_NUMBER_A
		elif "B" == number:
			command = SOX_NUMBER_B
		elif "C" == number:
			command = SOX_NUMBER_C
		elif "D" == number:
			command = SOX_NUMBER_D
		else:
			self.log.error ("can't make dial sound "
			                "for unknown number %s",
			                repr (number))
			return

		self.log.debug ("make dial sound %s", number)

		self.play_tone (command)
		return


	def start_say (self, text:str,
	               speed:int, amplitude:int, voice:str):
		command = (*ESPEAK_CMD,
		           *ESPEAK_SPEED, str(speed),
		           *ESPEAK_AMPLITUDE, str (amplitude),
		           *ESPEAK_VOICE, voice,
		           *ESPEAK_TEXT, text)

		self.log.debug ("invoking espeak: %s", repr (command))

		self.start_tone (command)
		return

	def play_say (self, text, abort,
	              speed=TTS_SPEED,
	              amplitude=TTS_AMPLITUDE,
	              voice=TTS_VOICE) -> bool:
		self.start_say (text, speed, amplitude, voice)

		while self.__process.poll () is None:
			if abort ():
				self.stop_tone ()
				return False

			time.sleep (SAY_DELAY)

		self.stop_tone ()
		return True

	def say (self, text, interruptible=True):
		if not interruptible:
			self.play_say (text, abort=self.__never)
			return not self.__on_hook ()

		return self.play_say (text, abort=self.__on_hook)

	def say_time (self, aloud, *args) -> bool:
		self.log.info ("saying time aloud=%r", aloud)

		if aloud:
			self.__speaker.activate ()

		now = datetime.datetime.now ()
		time_string = now.strftime (TIME_FORMAT)

		ret = self.say (time_string)

		if aloud:
			self.__speaker.deactivate ()

		return ret

	def notify_recording_start (self, recording_number:str) -> bool:
		self.log.debug ("notify recording %s start",
		                recording_number)

		return self.say ("Aufnahme %s wird gestartet"
		                 % recording_number)

	def notify_recording_end (self, recording_number:str,
	                          result:RECORDER_RESULT) -> bool:
		self.log.debug ("notify recording %s end with %r",
		                recording_number, result)

		if RECORDER_RESULT.ERROR == result:
			message = "Aufnahme %s fehlgeschlagen" \
			        % recording_number

		elif RECORDER_RESULT.ABORT == result:
			message = "Aufnahme %s abgebrochen" \
			        % recording_number

		elif RECORDER_RESULT.MIN_TIME == result:
			message = "Aufnahme zu kurz"

		elif RECORDER_RESULT.MAX_TIME == result:
			message = "Maximallänge erreicht. " \
			          "Aufnahme %s gespeichert." \
			        % recording_number

		elif RECORDER_RESULT.END == result:
			message = "Aufnahme %s gespeichert." \
			        % recording_number

		else:
			self.log.error ("unknown %r", result)
			return

		return self.say (message, interruptible=False)

	def notify_menu_start (self) -> bool:
		self.log.debug ("notify menu start")
		return self.say ("Menü wird geöffnet.")

	def notify_menu_error (self) -> bool:
		self.log.debug ("notify menu error")
		return self.say ("Das habe ich nicht verstanden. "
		                 "Auf Wiederhörn!",
		                 interruptible=False)
