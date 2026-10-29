#!/usr/bin/python3
# -*- coding: utf-8 -*-

import bisect
import enum
import logging
import time

from .CONSTANTS import DIAL_IN_USE_DELAY
from .CONSTANTS import DIAL_SLEEP
from .CONSTANTS import DIAL_TIMEOUT_DELAY
from .CONSTANTS import DIAL_TIMEOUT
from .CONSTANTS import DIAL_AUTO_TIMEOUT

from .number import Number


# how dialing a number ended (Dial.end, in the history as "dialed")
class DIAL_END (enum.Enum):
	# the digits are a number and no other number starts with them
	IMMEDIATE = "immediate"
	# no number starts with the digits, it can never become one
	REJECTED = "rejected"
	# DIAL_AUTO_TIMEOUT after the last digit
	TIMEOUT = "timeout"
	# abort () (left button or hang-up)
	ABORTED = "aborted"


# the numbers that can be called, as str (007 and 7 are different
# numbers), sorted: the numbers starting with some digits are next to
# each other, beginning where the digits would be inserted
class Prefixes ():
	def __init__ (self, numbers):
		self.__numbers = sorted (set (str (number) for number in numbers))
		return

	def __len__ (self):
		return len (self.__numbers)

	# (the digits are a number, a longer number starts with them)
	def match (self, digits:str) -> (bool, bool):
		index = bisect.bisect_left (self.__numbers, digits)
		numbers = self.__numbers[index : index + 2]

		if numbers and numbers[0] == digits:
			exact = True
			numbers = numbers[1:]
		else:
			exact = False

		longer = bool (numbers) and numbers[0].startswith (digits)
		return exact, longer


class Dial ():
	def __init__ (self, DialInUse, DialCounter):
		self.log = logging.getLogger ("Dial")

		self.__flag = DialInUse
		self.__counter = DialCounter

		# how the last get_number ended
		self.end = None
		# whether the last __get_digit returned -1 for the timeout
		self.__timed_out = False
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
			# the condition is short-circuited: on the timeout
			# abort () is not asked (no button press is taken)
			self.__timed_out = timeCounter > timeout
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

	# numbers: None (wait for the left button or the timeout, like
	# before), or a function returning the numbers that can be called;
	# then the number is complete as soon as it is one of them and no
	# other starts with its digits, and dialing stops as soon as none
	# starts with them (the caller gets the SIT tone of an unassigned
	# number). It is asked after the first digit (when the dial is back
	# at rest, a digit ends when the dial is not in use any more), so
	# nothing delays counting the pulses, and only once: nothing changes
	# the numbers while dialing (the webapp is answered when on the hook)
	def get_number (self, abort, led, player, numbers=None) -> Number:
		self.log.debug ("started dialing number")
		led.blink (on_time=0.1, off_time=0.1, n=None, background=True)
		number = Number ()
		prefixes = None

		self.end = DIAL_END.ABORTED
		while not abort():
			digit = self.__get_digit (abort, DIAL_AUTO_TIMEOUT)

			# timeout
			if -1 == digit:
				# don't timeout (i.e. auto dial)
				# if nothing was dialed yet
				if not number:
					continue
				else:
					# -1 is abort () as well
					if self.__timed_out:
						self.end = DIAL_END.TIMEOUT
					break

			# not dialed
			if None is digit:
				continue

			number.add_digit (digit)

			player.dial_sound (digit)

			if numbers is None:
				continue

			if prefixes is None:
				try:
					prefixes = Prefixes (numbers ())
				except Exception:
					# dial like before rather than not at all
					self.log.exception ("can't get the numbers,"
					                    " waiting for the timeout")
					numbers = None
					continue

				self.log.debug ("%d numbers can be called",
				                len (prefixes))

			exact, longer = prefixes.match (str (number))
			if exact and not longer:
				self.log.info ("%s is complete", number)
				self.end = DIAL_END.IMMEDIATE
				break

			if not exact and not longer:
				self.log.info ("no number starts with %s", number)
				self.end = DIAL_END.REJECTED
				break

		self.log.info ("dialed number %s", number)
		led.off ()
		return number
