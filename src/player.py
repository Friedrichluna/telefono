#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import fcntl
import logging
import os
import socket
import subprocess
import time

import psutil

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
from .CONSTANTS import FFPLAY_DURATION
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

from .CONSTANTS import RING_VOLUME
from .CONSTANTS import VOLUME_TEST_RING_TIME

from .CONSTANTS import WIND_TIME

from .CONSTANTS import NO_NUMBER_DELAY
from .CONSTANTS import NO_NUMBER_TIMEOUT

from .CONSTANTS import BUSY_DELAY
from .CONSTANTS import BUSY_TIMEOUT

from .CONSTANTS import TONE_DELAY
from .CONSTANTS import RELEASE_DELAY
from .CONSTANTS import SAY_DELAY

from .CONSTANTS import TIME_FORMAT

from .CONSTANTS import FLASK_PORT

from .recorder import RECORDER_RESULT


# the addresses of the webapp for the menu, spoken (espeak reads
# 192.168.0.144 as thousands): "192 Punkt 168 Punkt 0 Punkt 144
# Doppelpunkt 5000", one per interface that is up (not loopback)
def webapp_addresses () -> list:
	stats = psutil.net_if_stats ()
	result = list ()
	for name, addresses in psutil.net_if_addrs ().items ():
		if "lo" == name or name not in stats or not stats[name].isup:
			continue

		for address in addresses:
			if socket.AF_INET == address.family \
			and not address.address.startswith ("127."):
				result.append ("%s Doppelpunkt %d" % (
				    address.address.replace (".", " Punkt "),
				    FLASK_PORT))
				break

	return result


class Player ():
	def __init__ (self, hook, wind_back, wind_forward, speaker):
		self.log = logging.getLogger ("Player")

		self.__hook = hook
		self.__wind_back = wind_back
		self.__wind_forward = wind_forward
		self.__speaker = speaker
		self.__process = None

		# ffplay volume (percent) of the ring, set by the main process
		# from the volume settings (src/volume.py)
		self.ring_volume = RING_VOLUME

		# whether telefono is stopping (SIGTERM), set by the main
		# process: the only thing that ends a shout early
		self.stopping = self.__never

		return

	def __on_hook (self):
		return not self.__hook.is_pressed

	def __off_hook (self):
		return self.__hook.is_pressed

	# e.g. whether a ringing call was answered (for the history)
	def is_off_hook (self) -> bool:
		return self.__hook.is_pressed

	def __never (self):
		return False

	def __back (self):
		return self.__wind_back.is_released

	def __forward (self):
		return self.__wind_forward.is_released

	# duration: only the first seconds (from start), None: all
	def __ffplay (self, filename, start=0, volume=100, duration=None):
		command = (*FFPLAY_CMD, filename,
		           *FFPLAY_START, str (start),
		           *FFPLAY_VOLUME, str (volume))

		if duration is not None:
			command += (*FFPLAY_DURATION, str (duration))

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

	# duration: only the first seconds of the file (not with wind)
	# returns whether it was not aborted
	def __play (self, filename, abort, volume=100,
	            aloud=False, wind=False, duration=None) -> bool:
		return "aborted" != self.__play_result (filename, abort, volume,
		                                        aloud, wind, duration)

	# how the playback ended: "complete", "aborted", "missing" (no
	# file) or "failed" (ffplay gave up after stalling, exited with
	# an error or never showed a position: a broken file, ffplay
	# exits with 0 then)
	def __play_result (self, filename, abort, volume=100,
	                   aloud=False, wind=False, duration=None) -> str:

		self.log.debug ("play file %s, abort=%s, "
		                "volume=%d, aloud=%s, wind=%s, duration=%r",
		                filename, repr (abort),
		                volume, repr (aloud), repr (wind), duration)

		if not os.path.exists (filename):
			self.log.error ("file doesn't exist")
			return "missing"

		if abort ():
			return "aborted"

		aborted = False
		failed = False
		# whether ffplay ever showed a position
		played = False

		if aloud:
			self.__speaker.activate ()


		process = self.__ffplay (filename, volume=volume,
		                         duration=duration)

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
					played = True
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
					failed = True
					break

				stalls += 1
				self.log.warning ("ffplay stalled at %f in %s, "
				                  "restarting (%d/%d)",
				                  start, filename, stalls,
				                  FFPLAY_STALL_RETRIES)
				buffer.clear ()
				process = self.__ffplay (filename,
				                         start,
				                         volume,
				                         None if duration is None
				                         else max (duration - start,
				                                   0.1))
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

		if aborted:
			return "aborted"

		if failed:
			return "failed"

		if 0 != process.returncode:
			self.log.error ("ffplay failed on %s (exit status %r)",
			                filename, process.returncode)
			return "failed"

		if not played:
			# what ffplay wrote after the last poll
			try:
				data = process.stderr.read ()
			except (OSError, ValueError):
				data = None

			if data:
				played = self.__parse_ffplay_output (
				        bytes (buffer + data)) is not None

		if not played:
			self.log.error ("ffplay played nothing of %s", filename)
			return "failed"

		return "complete"

	def play_system_sound (self, filename:str) -> True:
		return self.__play (filename,
		                    abort=self.__never, aloud=True)

	def play_ring (self):
		self.__play (RING_FILE, abort=self.__off_hook,
		             volume=self.ring_volume, aloud=True)

	# test sounds of the webapp's volume page: the beginning of the
	# ring (one strike), a text in the handset or aloud
	def play_ring_test (self):
		self.__play (RING_FILE, abort=self.__off_hook,
		             volume=self.ring_volume, aloud=True,
		             duration=VOLUME_TEST_RING_TIME)
		return

	def play_test_text (self, text:str, aloud:bool):
		if aloud:
			self.__speaker.activate ()

		self.play_say (text, abort=self.__never)

		if aloud:
			self.__speaker.deactivate ()

		return

	def play_file (self, filename:str, aloud, wind) -> bool:
		return self.__play (filename, abort=self.__on_hook,
		                    aloud=aloud, wind=wind)

	# the daily shouts (src/event_queue.py): the files one after the
	# other over the loudspeaker (relay on, whatever the speaker
	# switch says, back to the switch afterwards) and to the end,
	# with the handset on the hook or lifted; only stopping telefono
	# ends them early; per file (result, seconds played), result:
	# "complete", "aborted" (stopping), "missing" or "failed"
	def play_shout (self, filenames) -> list:
		results = list ()
		if not filenames:
			return results

		self.__speaker.activate ()
		try:
			for filename in filenames:
				if self.stopping ():
					results.append (("aborted", 0))
					continue

				self.log.info ("shout: playing %s", filename)
				started = time.monotonic ()
				result = self.__play_result (filename,
				                             abort=self.stopping)
				results.append ((result, time.monotonic () - started))
		finally:
			self.__speaker.deactivate ()

		return results


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
				self.stop_tone (aloud)
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

	def say_address (self, aloud, *args) -> bool:
		self.log.info ("saying webapp address aloud=%r", aloud)

		addresses = webapp_addresses ()
		if addresses:
			message = "Webseite: %s." % " oder ".join (addresses)
		else:
			message = "Keine Netzwerkverbindung."

		if aloud:
			self.__speaker.activate ()

		ret = self.say (message)

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
