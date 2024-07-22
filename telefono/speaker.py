#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import threading

import RPi.GPIO as GPIO

from .CONSTANTS import SPEAKER_DELAY
from .CONSTANTS import SPEAKER_POWERON_DELAY

RELAIS_1_GPIO = 4

class SpeakerThread (threading.Thread):
	def __init__ (self, switch, gpio=RELAIS_1_GPIO):
		super ().__init__ ()

		self.__switch = switch
		self.__gpio = gpio

		# GPIO Numbers instead of board numbers
		GPIO.setmode(GPIO.BCM)
		# GPIO Assign mode
		GPIO.setup (self.__gpio, GPIO.OUT)

		self.__event = threading.Event ()
		self.__stop = threading.Event ()

		# force to set pin off
		self.__is_on = True
		self.__set_off ()

		return

	def __set_on (self):
		if self.__is_on:
			return

		GPIO.output (self.__gpio, GPIO.LOW)

		self.__is_on = True
		return

	def __set_off (self):
		if not self.__is_on:
			return

		GPIO.output (self.__gpio, GPIO.HIGH)

		self.__is_on = False
		return

	def run (self):
		while not self.__stop.is_set ():
			if self.__event.is_set () \
			or self.__switch.is_pressed:
				self.__set_on ()
			else:
				self.__set_off ()
			time.sleep (SPEAKER_DELAY)

		return

	def activate (self):
		self.__event.set ()
		time.sleep (SPEAKER_POWERON_DELAY)
		return

	def deactivate (self):
		self.__event.clear ()

	def join (self, timeout=None):
		self.__stop.set ()
		super ().join (timeout)
