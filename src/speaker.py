#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import time
import threading

import RPi.GPIO as GPIO

from .CONSTANTS import SPEAKER_DELAY
from .CONSTANTS import SPEAKER_POWERON_DELAY

from .config import SPEAKER_RELAY_PIN

RELAIS_1_GPIO = SPEAKER_RELAY_PIN

# the relay powers the loudspeaker's amplifier: low is on, or high if
# the relay is inverted ("speaker_relay = yes" in telefono.conf, the
# phones are wired differently)
class SpeakerThread (threading.Thread):
	def __init__ (self, switch, gpio=RELAIS_1_GPIO, inverted:bool=False):
		super ().__init__ ()

		self.log = logging.getLogger ("Speaker")

		self.__switch = switch
		self.__gpio = gpio

		if inverted:
			self.__on_level, self.__off_level = GPIO.HIGH, GPIO.LOW
		else:
			self.__on_level, self.__off_level = GPIO.LOW, GPIO.HIGH

		# GPIO Numbers instead of board numbers
		GPIO.setmode(GPIO.BCM)
		# output, off from the start
		GPIO.setup (self.__gpio, GPIO.OUT, initial=self.__off_level)

		# activate () holds the relay on until the matching
		# deactivate (), the switch is ignored meanwhile (counted, so
		# a shout keeps it on when something inside it lets go); the
		# lock keeps the thread from switching it off right after an
		# activate ()
		self.__lock = threading.Lock ()
		self.__holds = 0
		self.__stop = threading.Event ()

		# force to set pin off
		self.__is_on = True
		self.__set_off ()

		return

	def __set_on (self):
		if self.__is_on:
			return False

		GPIO.output (self.__gpio, self.__on_level)
		self.log.debug ("activated")

		self.__is_on = True
		return True

	def __set_off (self):
		if not self.__is_on:
			return False

		GPIO.output (self.__gpio, self.__off_level)
		self.log.debug ("deactivated")

		self.__is_on = False
		return True

	# the relay follows the loudspeaker switch (lock held)
	def __follow_switch (self):
		if self.__switch.is_pressed:
			self.__set_on ()
		else:
			self.__set_off ()
		return

	def run (self):
		while not self.__stop.is_set ():
			with self.__lock:
				if 0 == self.__holds:
					self.__follow_switch ()

			self.__stop.wait (SPEAKER_DELAY)

		return

	def activate (self):
		self.log.debug ("activate request")

		with self.__lock:
			self.__holds += 1
			changed = self.__set_on ()

		if changed:
			# only wait, if the state has actually changed
			time.sleep (SPEAKER_POWERON_DELAY)
		return

	# back to what the switch says, once every activate () is undone
	def deactivate (self):
		self.log.debug ("deactivate request")

		with self.__lock:
			if 0 < self.__holds:
				self.__holds -= 1
			else:
				self.log.warning ("deactivate without activate")

			if 0 == self.__holds:
				self.__follow_switch ()
		return

	def join (self, timeout=None):
		self.log.debug ("shutting down with timeout %s",
		                repr (timeout))

		self.__stop.set ()
		result = super ().join (timeout)

		# telefono stops: the loudspeaker is off (the pin keeps its
		# level after the process ended)
		if not self.is_alive ():
			with self.__lock:
				self.__set_off ()

		return result
