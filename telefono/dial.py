#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time


DIAL_TIMEOUT = 200000
DIAL_TIMEOUT_SLEEP = 0.001
DIAL_SLEEP = 0.01

class Dial ():
	def __init__ (self, DialInUse, DialCounter):
		self.__flag = DialInUse
		self.__counter = DialCounter
		return

	def is_used (self):
		if not self.dialing:
			return False

		time.sleep (0.1)

		return self.dialing

	@property
	def dialing (self):
		return self.__flag.is_pressed

	@property
	def digit_moved (self):
		return self.__counter.is_pressed

	def __get_digit (self, abort):
		# timeout while idle
		timeCounter = 0
		while timeCounter <= DIAL_TIMEOUT \
		and not abort ():
			if self.dialing:
				break

			time.sleep (DIAL_TIMEOUT_SLEEP)
			timeCounter += 1
		else:
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
			return None

		# 0 dialed
		elif digit > 9:
			return 0

		return digit

	def get_digit (self, abort, led):
		led.blink (on_time=0.1, off_time=0.1, n=None, background=True)

		digit = self.__get_digit (abort)

		# timeout
		if -1 == digit:
			digit = None

		if digit is not None:
			print(digit)

		led.off ()
		return digit

	def get_number (self, abort, led):
		led.blink (on_time=0.1, off_time=0.1, n=None, background=True)
		number = 0

		while not abort():
			digit = self.__get_digit (abort)

			# timeout
			if -1 == digit:
				break

			# not dialed
			if None is digit:
				continue

			number *= 10
			number += digit

		led.off ()
		return number
