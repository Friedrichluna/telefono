#!/usr/bin/python3
# -*- coding: utf-8 -*-

import gpiozero


class Button (gpiozero.Button):
	def __init__ (self, *args, **kwargs):
		super ().__init__ (*args, **kwargs)

	@property
	def is_released (self) -> bool:
		if not self.is_pressed:
			return False

		while self.is_pressed:
			pass

		return True
