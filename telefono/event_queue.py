#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import time


class EVENT_TYPE (enum.IntEnum):
	CALL = 0


class EventQueue:
	def __init__ (self):
		self.__events = list ()
		return

	def add_call (self, call:int, time=0):

		index = 0
		while index < len (self.__events) \
		and self.__events[index][1] <= time:
			index += 1

		self.__events.insert (index,
		                     (EVENT_TYPE.CALL, time, call))
		return

	def __get_time (self):
		return time.time ()

	def process (self, tts, speaker, PickUp, newWavName, ringing):
		if 0 == len (self.__events):
			return

		if self.__events[0][1] < self.__get_time ():
			event = self.__events.pop (0)

			if EVENT_TYPE.CALL == event[0]:
				self.__process_call (event[2], tts, speaker, PickUp, newWavName, ringing)

		return

	def __process_call (self, call,
	                    tts, speaker, PickUp, newWavName, ringing):
		recording = newWavName (call)
		print ("call in queue: %s" % recording)
		ringing (tts, recording, speaker, PickUp)
