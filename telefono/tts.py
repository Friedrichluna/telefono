#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import pyttsx3
import random

class TTS():
	supperPrayers = [101, 102, 103, 104, 105]
	dicePrayers = [201, 202, 203, 204, 205, 206]
	pater = [2, 10, 11, 19, 22, 26, 30, 88]

	def __init__ (self):
		self.__engine = pyttsx3.init()
		self.__engine.setProperty('rate', 140)    # Speed percent (can go over 100)
		self.__engine.setProperty('volume', 1)  # Volume 0-1
		self.__engine.setProperty('voice', "german+f2") #sprache auf Deutsch ändern

		return

	def say (self, text):
		print(text)
		self.__engine.say(text)
		#self.__engine.startLoop(False)
		self.__engine.runAndWait()

	def say_time (self):
		print("uhrzeit ansagen")

		FORMAT = "Es ist %H Uhr %M am %d.%m.%Y."
		now = datetime.datetime.now()
		timeInWords = now.strftime (FORMAT)

		self.say(timeInWords)

	def _random (self, _list, PickUp):
		recording = random.choice (_list)
		print("playing: %d" % recording)
		play_recording (self, recording, PickUp)

	def random_prayer (self, PickUp):
		self._random (self.supperPrayers, PickUp)

	def random_dice_prayer (self, PickUp):
		self._random (self.dicePrayers, PickUp)

	def random_pater (self, PickUp):
		self._random (self.pater, PickUp)
