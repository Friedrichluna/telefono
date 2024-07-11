#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time


class CallQueue:
	def __init__ (self):
		self.__calls = list ()
		return

	def add_call (self, call:int, time=0):

		index = 0
		while index < len (self.__calls) \
		and self.__calls[index][1] <= time:
			index += 1

		self.__calls.insert (index, (call, time))
		return

	def __get_time (self):
		return time.time ()

	def process (self, tts, speaker, PickUp, newWavName, ringing):
		if 0 == len (self.__calls):
			return

		if self.__calls[0][1] < self.__get_time ():
			call = self.__calls.pop (0)

			recording = newWavName (call[0])
			print ("call in queue: %s" % recording)
			ringing (tts, recording, speaker, PickUp)

		return
