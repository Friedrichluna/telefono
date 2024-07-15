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
			self.__tts.say("Diese Aufnahme existiert noch nicht.")

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
