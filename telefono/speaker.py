#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import threading

import RPi.GPIO as GPIO

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

	def run (self):
		while not self.__stop.is_set ():
			if self.__event.is_set () or self.__switch.is_pressed:
				GPIO.output (self.__gpio, GPIO.LOW) # on
			else:
				GPIO.output (self.__gpio, GPIO.HIGH) # off
			time.sleep (0.2)

	def activate (self):
		self.__event.set ()

	def deactivate (self):
		self.__event.clear ()

	def join (self, timeout=None):
		self.__stop.set ()
		super ().join (timeout)
