#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time

import gpiozero

from .CONSTANTS import BUTTON_DELAY


# inverted: the input reads pressed at rest (the wiring differs between
# the phones, see telefono.conf); value and is_pressed are inverted,
# gpiozero's events (when_pressed, wait_for_press, ...) are not,
# telefono only polls
class Button (gpiozero.Button):
	def __init__ (self, *args, inverted:bool=False, **kwargs):
		# set first, gpiozero's __init__ already reads value
		self._inverted = inverted
		super ().__init__ (*args, **kwargs)

	@property
	def value (self) -> int:
		value = super ().value
		if self._inverted:
			return int (not value)

		return value

	@property
	def is_released (self) -> bool:
		if not self.is_pressed:
			return False

		while self.is_pressed:
			time.sleep (BUTTON_DELAY)

		return True
