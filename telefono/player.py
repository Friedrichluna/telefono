#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import random
import time

import pygame

from .CONSTANTS import DIAL_TONE_FILE
from .CONSTANTS import RING_FILE


class Player ():
	__supperPrayers = [101, 102, 103, 104, 105]
	__dicePrayers = [201, 202, 203, 204, 205, 206]
	__pater = [2, 10, 11, 19, 22, 26, 30, 88]

	def __init__ (self, hook, newWavName):
		# setup pygame
		pygame.mixer.init()
		pygame.init()

		self.__hook = hook
		self.newWavName = newWavName
		return

	def __on_hook (self):
		return not self.__hook.is_pressed

	def __off_hook (self):
		return self.__hook.is_pressed

	def __never (self):
		return False

	def __play (self, tts, fileName, speaker, abort):
		if abort ():
			return

		if speaker is not None:
			speaker.activate ()
			time.sleep (2)

		if os.path.exists (fileName):
			pygame.mixer.music.load(fileName)
			pygame.mixer.music.play()
			while pygame.mixer.music.get_busy():
				time.sleep (0.01)
				if abort ():
					pygame.mixer.music.stop()
		else:
			tts.say("Diese Aufnahme existiert noch nicht.")

		if speaker is not None:
			speaker.deactivate ()

		return

	def play_aloud (self, tts, fileName, speaker):
		return  self.__play (tts, fileName, speaker,
		                     abort=self.__never)

	def start_dial_tone (self):
		pygame.mixer.music.load (DIAL_TONE_FILE)
		pygame.mixer.music.play (loops=-1)

	def stop_dial_tone (self):
		pygame.mixer.music.stop ()

	def play_recording (self, tts, recording):
		recording = self.newWavName (recording)

		return self.__play (tts, recording, speaker=None,
		             abort=self.__on_hook)

	def ringing (self, tts, callingFile_, speaker):
		self.__play (tts, RING_FILE, speaker,
		             abort=self.__off_hook)
		time.sleep (1) #test
		self.play_recording (tts, callingFile_)

	def shout (self, tts, call, speaker):
		wavName = self.newWavName (call)
		self.__play (tts, wavName, speaker,
		             abort=self.__off_hook)

	def __play_random (self, files):
		recording = random.choice (files)
		print("playing: %d" % recording)
		self.play_recording (recording)
		return

	def random_prayer (self):
		return self.__play_random (self.__supperPrayers)

	def random_dice_prayer (self):
		return self.__play_random (self.__dicePrayers)

	def random_pater (self):
		return self.__play_random (self.__pater)
