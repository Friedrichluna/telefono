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

	def get_number (self, abort, led):
		led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
		number = 0

		while not abort():

			# timeout while idle
			timeCounter = 0
			while timeCounter <= DIAL_TIMEOUT \
			and not abort ():

				if self.dialing:
					break
				time.sleep (DIAL_TIMEOUT_SLEEP)
				timeCounter += 1
			else:
				break

			digit = 0
			while self.dialing:

				# wait for HIGH
				while self.dialing:
					time.sleep (DIAL_SLEEP)
					if not self.digit_moved:
						break
				else:
					break

				digit += 1

				# wait for LOW
				while not self.digit_moved \
				and self.dialing:
					time.sleep (DIAL_SLEEP)

			# not dialed
			if digit == 0:
				continue

			# 0 dialed
			if digit > 9:
				digit = 0

			number *= 10
			number += digit
			print(digit)

		led.off()
		return number

	def get_digit (self, abort, led):
		led.blink(on_time=0.1, off_time=0.1, n=None, background=True)

		# timeout while idle
		timeCounter = 0
		while timeCounter <= DIAL_TIMEOUT \
		and not abort():
			if self.dialing:
				break

			time.sleep (DIAL_TIMEOUT_SLEEP)
			timeCounter += 1
		else:
			led.off()
			return None


		dialedDigit = 0
		while self.dialing:

			# wait for LOW
			while self.dialing:
				if not self.digit_moved:
					break

				time.sleep (DIAL_SLEEP)
			else:
				break

			dialedDigit += 1

			# wait for HIGH
			while not self.digit_moved \
			and self.dialing:
				time.sleep (DIAL_SLEEP)

		# not dialed
		if dialedDigit == 0:
			dialedDigit = None

		# 0 dialed
		elif dialedDigit > 9:
			dialedDigit = 0
			print(dialedDigit)

		else:
			print(dialedDigit)

		led.off()
		return dialedDigit
