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

	def __add_event (self, time, event):

		index = 0
		while index < len (self.__events) \
		and self.__events[index][0] <= time:
			index += 1

		self.__events.insert (index, (time, event))
		return

	def add_call (self, call:int, time=0):
		self.__add_event (time, (EVENT_TYPE.CALL, call))
		return

	def __get_time (self):
		return time.time ()

	def process (self, tts, speaker, PickUp, newWavName, ringing):
		if 0 == len (self.__events):
			return

		if self.__events[0][0] < self.__get_time ():
			event = self.__events.pop (0)[1]

			if EVENT_TYPE.CALL == event[0]:
				self.__process_call (event[1], tts, speaker, PickUp, newWavName, ringing)

		return

	def __process_call (self, call,
	                    tts, speaker, PickUp, newWavName, ringing):
		recording = newWavName (call)
		print ("call in queue: %s" % recording)
		ringing (tts, recording, speaker, PickUp)
