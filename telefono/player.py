#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import random
import subprocess
import time

import pygame

from .CONSTANTS import RING_FILE

from .CONSTANTS import SOX_DIAL
from .CONSTANTS import SOX_BUSY
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

from .CONSTANTS import NO_NUMBER_DELAY
from .CONSTANTS import NO_NUMBER_TIMEOUT

from . import Record


class Player ():
	__supperPrayers = [101, 102, 103, 104, 105]
	__dicePrayers = [201, 202, 203, 204, 205, 206]
	__pater = [2, 10, 11, 19, 22, 26, 30, 88]

	def __init__ (self, hook, tts, speaker):
		# setup pygame
		pygame.mixer.init()
		pygame.init()

		self.__hook = hook
		self.__tts = tts
		self.__speaker = speaker
		self.__process = None
		return

	def __on_hook (self):
		return not self.__hook.is_pressed

	def __off_hook (self):
		return self.__hook.is_pressed

	def __never (self):
		return False

	def __play (self, fileName, abort, aloud=False) -> bool:
		if abort ():
			return False

		aborted = False

		if aloud:
			self.__speaker.activate ()
			time.sleep (2)

		if os.path.exists (fileName):
			pygame.mixer.music.load(fileName)
			pygame.mixer.music.play()
			while pygame.mixer.music.get_busy():
				time.sleep (0.01)
				if abort ():
					pygame.mixer.music.stop()
					aborted = True
		else:
			self.start_sit_tone ()

			timer = 0
			while timer < NO_NUMBER_TIMEOUT:
				if abort ():
					self.stop_tone ()
					return False

				time.sleep (NO_NUMBER_DELAY)
				timer += 1

			self.stop_tone ()

		if aloud:
			self.__speaker.deactivate ()

		if abort ():
			aborted = True

		return not aborted

	def play_aloud (self, fileName) -> True:
		return self.__play (fileName,
		                    abort=self.__never, aloud=True)

	def stop_tone (self):
		if self.__process is not None:
			self.__process.terminate ()
			self.__process = None
		return

	def start_dial_tone (self):
		self.stop_tone ()
		self.__process = subprocess.Popen (SOX_DIAL)
		return

	def start_busy_tone (self):
		self.stop_tone ()
		self.__process = subprocess.Popen (SOX_BUSY)
		return

	def play_busy_tone (self):
		self.start_busy_tone ()

		while self.__off_hook ():
			pass

		self.stop_tone ()
		return

	def start_sit_tone (self):
		self.stop_tone ()
		self.__process = subprocess.Popen (SOX_SIT)
		return

	def play_recording (self, recording) -> bool:
		recording = Record (recording, "").filename

		return self.__play (recording, abort=self.__on_hook)

	def call (self, call, ring=True) -> bool:
		if ring:
			if self.__play (RING_FILE,
			                abort=self.__off_hook,
			                aloud=True):

				# never picked up
				return False

			time.sleep (1) #test

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
			print ("dialed unknown number %s", str(number))
			return

		self.stop_tone ()
		self.__process = subprocess.Popen (command)
		return

	def __play_random (self, files) -> bool:
		recording = random.choice (files)
		print("playing: %d" % recording)
		return self.play_recording (recording)

	def random_prayer (self) -> bool:
		return self.__play_random (self.__supperPrayers)

	def random_dice_prayer (self) -> bool:
		return self.__play_random (self.__dicePrayers)

	def random_pater (self) -> bool:
		return self.__play_random (self.__pater)

	def quit (self):
		return pygame.quit ()
