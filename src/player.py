#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
import os
import random
import subprocess
import time

import pygame

from .CONSTANTS import RING_FILE

from .CONSTANTS import SOX_DIAL
from .CONSTANTS import SOX_BUSY
from .CONSTANTS import SOX_RELEASE
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
from .CONSTANTS import FFPLAY_STARTUP_TIME
from .CONSTANTS import FFPLAY_POLL_DELAY

from .CONSTANTS import ESPEAK_CMD
from .CONSTANTS import ESPEAK_SPEED
from .CONSTANTS import ESPEAK_AMPLITUDE
from .CONSTANTS import ESPEAK_VOICE

from .CONSTANTS import TTS_SPEED
from .CONSTANTS import TTS_AMPLITUDE
from .CONSTANTS import TTS_VOICE

from .CONSTANTS import WIND_TIME

from .CONSTANTS import NO_NUMBER_DELAY
from .CONSTANTS import NO_NUMBER_TIMEOUT

from .CONSTANTS import BUSY_DELAY
from .CONSTANTS import BUSY_TIMEOUT

from .CONSTANTS import TIME_FORMAT

from . import Record


class Player ():
	__supperPrayers = [101, 102, 103, 104, 105]
	__dicePrayers = [201, 202, 203, 204, 205, 206]
	__pater = [2, 10, 11, 19, 22, 26, 30, 88]

	def __init__ (self, hook, wind_back, wind_forward, speaker):
		# setup pygame
		pygame.mixer.init()
		pygame.init()

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

		logging.debug ("invoking ffplay: %s", repr (command))

		process = subprocess.Popen (command,
		                            stderr=subprocess.PIPE,
		                            text=True)

		# wait for ffplay to produce output
		time.sleep (FFPLAY_STARTUP_TIME)
		return process

	def __play (self, fileName, abort, volume=100,
	            aloud=False, wind=False) -> bool:

		logging.debug ("Player: play file %s, abort=%s, "
		               "volume=%d, aloud=%s, wind=%s",
		               fileName, repr (abort),
		               volume, repr (aloud), repr (wind))

		if abort ():
			return False

		aborted = False

		if aloud:
			self.__speaker.activate ()

		if os.path.exists (fileName):
			process = self.__ffplay (fileName, volume=volume)

			while process.poll () is None:
				time.sleep (FFPLAY_POLL_DELAY)
				if abort ():
					process.terminate ()
					aborted = True

				if wind and self.__back ():
					process.terminate ()
					data = process.communicate ()
					try:
						data = data[1]
						data = data.split ('\n')
						data = data[-2]
						data = data.strip ()
						data = data.split (' ')
						data = data[0]
						start = float (data)
						start -= WIND_TIME
					except:
						start = 0
						logging.error ("Player: failed to parse ffplay output")

					logging.debug ("Player: wind back to %d", start)

					process = self.__ffplay (fileName,
					                         start,
					                         volume)


				if wind and self.__forward ():
					process.terminate ()
					data = process.communicate ()
					try:
						data = data[1]
						data = data.split ('\n')
						data = data[-2]
						data = data.strip ()
						data = data.split (' ')
						data = data[0]
						start = float (data)
						start += WIND_TIME
					except:
						start = 0
						logging.error ("Player: failed to parse ffplay output")

					logging.debug ("Player: wind forward to %d", start)
					process = self.__ffplay (fileName,
					                         start,
					                         volume)
		else:
			if not self.play_sit_tone (abort):
				aborted = True

		if aloud:
			self.__speaker.deactivate ()

		if abort ():
			aborted = True

		return not aborted

	def play_aloud (self, fileName) -> True:
		return self.__play (fileName,
		                    abort=self.__never, aloud=True)

	def start_tone (self, command):
		self.stop_tone ()
		self.__process = subprocess.Popen (command,
		                                   stderr=subprocess.DEVNULL)
		return

	def stop_tone (self):
		if self.__process is not None:
			logging.debug ("aborting tone")
			self.__process.terminate ()
			self.__process = None
		return

	def play_tone (self, command):
		self.start_tone (command)

		while self.__process.poll () is None:
			pass

		self.stop_tone ()
		return

	def start_dial_tone (self):
		logging.debug ("starting dial tone")
		self.start_tone (SOX_DIAL)
		return

	def start_busy_tone (self):
		logging.debug ("starting busy tone")
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
		logging.debug ("starting release tone")
		self.start_tone (SOX_RELEASE)
		return

	def play_release_tone (self):
		self.start_release_tone ()

		while self.__off_hook ():
			pass

		self.stop_tone ()
		return

	def start_sit_tone (self):
		logging.debug ("starting SIT tone")
		self.start_tone (SOX_SIT)
		return

	def play_sit_tone (self, abort):
		self.start_sit_tone ()

		timer = 0
		while timer < NO_NUMBER_TIMEOUT:
			if abort ():
				self.stop_tone ()
				return False

			time.sleep (NO_NUMBER_DELAY)
			timer += 1

		self.stop_tone ()
		return True


	def play_recording (self, recording:int) -> bool:
		logging.info ("Player: play %d", recording)

		recording = Record (recording, "").filename

		return self.__play (recording, abort=self.__on_hook,
		                    wind=True)

	def call (self, call:int, ring=True) -> bool:
		logging.info ("Player: call %d", call)

		if ring:
			if self.__play (RING_FILE,
			                abort=self.__off_hook,
			                volume=70,
			                aloud=True):

				# never picked up
				return False

		recording = Record (call, "").filename
		return self.__play (recording, abort=self.__on_hook,
		                    aloud=(not ring))

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
			logging.error ("Player: can't make dial sound "
			               "for unknown number %s",
			               repr (number))
			return

		logging.debug ("Player: make dial sound %s", number)

		self.play_tone (command)
		return

	def __play_random (self, files) -> bool:
		recording = random.choice (files)
		return self.play_recording (recording)

	def random_prayer (self) -> bool:
		return self.__play_random (self.__supperPrayers)

	def random_dice_prayer (self) -> bool:
		return self.__play_random (self.__dicePrayers)

	def random_pater (self) -> bool:
		return self.__play_random (self.__pater)


	def start_say (self, text:str,
	               speed:int, amplitude:int, voice:str):
		command = (*ESPEAK_CMD,
		           *ESPEAK_SPEED, str(speed),
		           *ESPEAK_AMPLITUDE, str (amplitude),
		           *ESPEAK_VOICE, voice,
		           text)

		logging.debug ("invoking espeak: %s", repr (command))

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

		self.stop_tone ()
		return True

	def say (self, text, interruptible=True):
		if not interruptible:
			self.play_say (text, abort=self.__never)
			return not self.__on_hook ()

		return self.play_say (text, abort=self.__on_hook)

	def say_time (self) -> bool:
		logging.info ("Player: saying time")

		now = datetime.datetime.now ()
		time_string = now.strftime (TIME_FORMAT)

		return self.say (time_string)


	def quit (self):
		return pygame.quit ()
