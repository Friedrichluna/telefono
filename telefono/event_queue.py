#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import enum
import random
import time

from .CONSTANTS import MIN_HOUR
from .CONSTANTS import MAX_HOUR


class EVENT_TYPE (enum.IntEnum):
	CALL = 0
	DAILY_RANDOM = 1


class EventQueue:
	def __init__ (self, records):
		self.__events = list ()

		self.__records = records

		# schedule daily random call
		self.__add_random_call (datetime.datetime.today ())

		# schedule startup call
		call = self.__records.get_random ()
		if call is None:
			print ("no call available")

		else:
			self.add_call (call)

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

	def __get_random_call_time (self, day:datetime.date) -> int:
		min_hour = datetime.time (MIN_HOUR)
		max_hour = datetime.time (MAX_HOUR)

		min_date = datetime.datetime.combine (day, min_hour)
		max_date = datetime.datetime.combine (day, max_hour)

		min_time = int (min_date.timestamp ())
		max_time = int (max_date.timestamp ())

		return random.randint (min_time, max_time)

	def __add_random_call (self, day:datetime.date):
		call = self.__records.get_random ()
		if call is None:
			print ("no call available")
			return

		event = (EVENT_TYPE.DAILY_RANDOM, call)
		time = self.__get_random_call_time (day)

		print ("call scheduled for: %02d:%02d Uhr"
		       % ((time // 60) // 60 % 24, (time // 60) % 60))

		return self.__add_event (time, event)

	def __get_time (self):
		return time.time ()

	def process (self, tts, speaker, PickUp, newWavName, ringing):
		if 0 == len (self.__events):
			return

		if self.__events[0][0] < self.__get_time ():
			event = self.__events.pop (0)[1]

			if EVENT_TYPE.CALL == event[0]:
				self.__process_call (event[1], tts, speaker, PickUp, newWavName, ringing)

			elif EVENT_TYPE.DAILY_RANDOM == event[0]:
				self.__process_call (event[1], tts, speaker, PickUp, newWavName, ringing)

				tomorrow = datetime.date.today ()
				tomorrow += datetime.timedelta (1)
				self.__add_random_call (tomorrow)

		return

	def __process_call (self, call,
	                    tts, speaker, PickUp, newWavName, ringing):
		recording = newWavName (call)
		print ("call in queue: %s" % recording)
		ringing (tts, recording, speaker, PickUp)
