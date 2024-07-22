#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging

import pyttsx3


class TTS():
	def __init__ (self):
		self.__engine = pyttsx3.init()
		self.__engine.setProperty('rate', 140)    # Speed percent (can go over 100)
		self.__engine.setProperty('volume', 1)  # Volume 0-1
		self.__engine.setProperty('voice', "german+f2") #sprache auf Deutsch ändern

		return

	def say (self, text, abort) -> bool:
		logging.debug ("TTS: saying text \"%s\"", text)

		self.__engine.say (text)
		self.__engine.runAndWait ()
		return not abort ()
