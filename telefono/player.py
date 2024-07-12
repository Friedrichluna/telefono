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

	def __init__ (self, newWavName):
		# setup pygame
		pygame.mixer.init()
		pygame.init()

		self.newWavName = newWavName
		return

	def play_aloud (self, tts, fileName, speaker, breakButton=None):
		speaker.activate ()
		time.sleep (2)

		if os.path.exists (fileName):
			pygame.mixer.music.load(fileName)
			pygame.mixer.music.play()
			while pygame.mixer.music.get_busy():
					if breakButton is not None \
					and breakButton.is_pressed:
						pygame.mixer.music.stop()
		else:
			tts.say("Diese Aufnahme existiert noch nicht.")

		speaker.deactivate ()

	def start_dial_tone (self):
		pygame.mixer.music.load (DIAL_TONE_FILE)
		pygame.mixer.music.play (loops=-1)

	def stop_dial_tone (self):
		pygame.mixer.music.stop ()

	def play_recording (self, tts, recording, contButton):
		if not contButton.is_pressed:
			return

		recording = self.newWavName (recording)

		if os.path.exists (recording):
			pygame.mixer.music.load(recording)
			pygame.mixer.music.play()

			while pygame.mixer.music.get_busy():
				time.sleep (0.01)
				if not contButton.is_pressed:
					pygame.mixer.music.stop()
		else:
			tts.say("Diese Aufnahme existiert noch nicht.")

	def ringing (self, tts, callingFile_, speaker, PickUp):
		self.play_aloud (tts, RING_FILE, speaker, PickUp) #hört auf wenn PickUp == True
		time.sleep (1) #test
		self.play_recording (tts, callingFile_, PickUp) #hört auf wenn PickUp == False

	def shout (self, tts, call, speaker, PickUp):
		wavName = self.newWavName (call)
		self.play_aloud (tts, wavName, speaker, PickUp) #hört auf wenn PickUp == True

	def __play_random (self, files, PickUp):
		recording = random.choice (files)
		print("playing: %d" % recording)
		self.play_recording (recording, PickUp)
		return

	def random_prayer (self, PickUp):
		return self.__play_random (self.__supperPrayers, PickUp)

	def random_dice_prayer (self, PickUp):
		return self.__play_random (self.__dicePrayers, PickUp)

	def random_pater (self, PickUp):
		return self.__play_random (self.__pater, PickUp)
