#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import time

from .CONSTANTS import DIAL_IN_USE_DELAY
from .CONSTANTS import DIAL_SLEEP
from .CONSTANTS import DIAL_TIMEOUT_DELAY
from .CONSTANTS import DIAL_TIMEOUT
from .CONSTANTS import DIAL_AUTO_TIMEOUT

from .number import Number


class Dial ():
	def __init__ (self, DialInUse, DialCounter):
		self.log = logging.getLogger ("Dial")

		self.__flag = DialInUse
		self.__counter = DialCounter
		return

	def is_used (self):
		if not self.dialing:
			return False

		time.sleep (DIAL_IN_USE_DELAY)

		return self.dialing

	@property
	def dialing (self):
		return self.__flag.is_pressed

	@property
	def digit_moved (self):
		return self.__counter.is_pressed

	def __get_digit (self, abort, timeout):
		# timeout while idle
		timeCounter = 0
		while timeCounter <= timeout \
		and not abort ():
			if self.dialing:
				break

			time.sleep (DIAL_TIMEOUT_DELAY)
			timeCounter += 1
		else:
			self.log.debug ("aborted dialing")
			return -1


		digit = 0
		while self.dialing:

			# wait for LOW
			while self.dialing:
				if not self.digit_moved:
					break

				time.sleep (DIAL_SLEEP)
			else:
				break

			digit += 1

			# wait for HIGH
			while not self.digit_moved \
			and self.dialing:
				time.sleep (DIAL_SLEEP)

		# not dialed
		if digit == 0:
			self.log.debug ("dialing failure")
			return None

		# 0 dialed
		elif digit > 9:
			self.log.debug ("dailed 0")
			return 0

		self.log.debug ("dailed %d", digit)
		return digit

	def get_digit (self, abort, led, player):
		self.log.debug ("started dialing single digit")
		led.blink (on_time=0.1, off_time=0.1, n=None, background=True)

		digit = self.__get_digit (abort, DIAL_TIMEOUT)

		# timeout
		if -1 == digit:
			digit = None

		if digit is not None:
			player.dial_sound (digit)
			self.log.debug ("dialed digit %d", digit)

		led.off ()
		return digit

	def get_number (self, abort, led, player) -> Number:
		self.log.debug ("started dialing number")
		led.blink (on_time=0.1, off_time=0.1, n=None, background=True)
		number = Number (None, "")

		while not abort():
			digit = self.__get_digit (abort, DIAL_AUTO_TIMEOUT)

			# timeout
			if -1 == digit:
				# don't timeout (i.e. auto dial)
				# if nothing was dialed yet
				if not number:
					continue
				else:
					break

			# not dialed
			if None is digit:
				continue

			number.add_digit (digit)

			player.dial_sound (digit)

		self.log.info ("dialed number %s", number)
		led.off ()
		return number
