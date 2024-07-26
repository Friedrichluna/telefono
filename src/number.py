#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import logging


class NumberType (enum.IntEnum):
	INTERNAL = 0


class Number ():
	def __new__ (cls, network, number:str):

		# allow casting Number -> Number
		if isinstance (number, cls):
			number.__network = network
			return number

		return super ().__new__ (cls)

	def __init__ (self, network, number:str):

		# allow casting Number -> Number
		if isinstance (number, Number):
			return None

		if isinstance (number, int):
			number = str (number)

		if not isinstance (number, str):
			raise TypeError ("can only convert int, str "
			                 "to Number")

		for digit in number:
			if not ord('0') <= ord (digit) <= ord ('9'):
				raise ValueError (
				        "only digits allowed in number")

		self.__network = network
		self.__number = number
		self.__type = NumberType.INTERNAL

		self.log = logging.getLogger ("%r" % self)
		return

	def __str__ (self) -> str:
		return self.__number

	def __repr__ (self) -> str:
		return "Number(%s)" % repr (self.__number)

	def __copy__ (self):
		return Number (self.__network, self.__number)


	def __eq__ (self, other) -> bool:
		if self.__type != other.__type:
			return False

		if len (self.__number) != len (other.__number):
			return False

		for digit1, digit2 in zip (self.__number, other.__number):
			if digit1 != digit2:
				return False

		return True

	def __lt__ (self, other) -> bool:
		if self.__type != other.__type:
			return NotImplemented

		return self.__number < other.__number

	def __int__ (self):
		return int (self.__number)

	def __bool__ (self) -> bool:
		return self.__number != ""

	def __radd__ (self, other):
		return other + self.__number

	def __iadd__ (self, other):
		self.__number += Number (self.__network, other).__number

		# update log name
		self.log.name = repr (self)
		return

	def __add__ (self, other):
		copy = self.__copy__ ()
		copy.__iadd__ (other)
		return copy


	def add_digit (self, digit):

		if isinstance (digit, int):
			digit = str (digit)

		if not isinstance (digit, str):
			raise TypeError ("can add int, str as digit")

		if not ord('0') <= ord (digit) <= ord ('9'):
			raise ValueError ("only digits allowed in number")

		self.log.debug ("add digit %s", digit)
		self.__number += digit

		# update log name
		self.log.name = repr (self)
		return
