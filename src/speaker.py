#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import time
import threading

import RPi.GPIO as GPIO

from .CONSTANTS import SPEAKER_DELAY
from .CONSTANTS import SPEAKER_POWERON_DELAY

from .config import SPEAKER_RELAY_PIN

# low is on
RELAIS_1_GPIO = SPEAKER_RELAY_PIN

class SpeakerThread (threading.Thread):
	def __init__ (self, switch, gpio=RELAIS_1_GPIO):
		super ().__init__ ()

		self.log = logging.getLogger ("Speaker")

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
			return False

		GPIO.output (self.__gpio, GPIO.LOW)
		self.log.debug ("activated")

		self.__is_on = True
		return True

	def __set_off (self):
		if not self.__is_on:
			return False

		GPIO.output (self.__gpio, GPIO.HIGH)
		self.log.debug ("deactivated")

		self.__is_on = False
		return True

	def run (self):
		while not self.__stop.is_set ():
			# block while event
			while self.__event.is_set ():
				time.sleep (SPEAKER_DELAY)

			if self.__switch.is_pressed:
				self.__set_on ()
			else:
				self.__set_off ()

			time.sleep (SPEAKER_DELAY)

		return

	def activate (self):
		self.log.debug ("activate request")
		self.__event.set ()

		if self.__set_on ():
			# only wait, if the state has actually changed
			time.sleep (SPEAKER_POWERON_DELAY)
		return

	def deactivate (self):
		self.log.debug ("deactivate request")
		self.__event.clear ()
		return

	def join (self, timeout=None):
		self.log.debug ("shutting down with timeout %s",
		                repr (timeout))

		self.__stop.set ()
		return super ().join (timeout)
