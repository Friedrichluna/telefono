#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
import random

import pyttsx3

from .CONSTANTS import TIME_FORMAT


class TTS():
	def __init__ (self):
		self.__engine = pyttsx3.init()
		self.__engine.setProperty('rate', 140)    # Speed percent (can go over 100)
		self.__engine.setProperty('volume', 1)  # Volume 0-1
		self.__engine.setProperty('voice', "german+f2") #sprache auf Deutsch ändern

		return

	def say (self, text):
		logging.debug ("TTS: saying text \"%s\"", text)

		self.__engine.say(text)
		#self.__engine.startLoop(False)
		self.__engine.runAndWait()

	def say_time (self):
		logging.info ("TTS: saying time")

		now = datetime.datetime.now()
		timeInWords = now.strftime (TIME_FORMAT)

		self.say(timeInWords)
