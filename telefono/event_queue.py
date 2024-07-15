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
	TEXT = 1
	DAILY_RANDOM = 2
	DAILY_SHOUT = 3


class EventQueue:
	def __init__ (self, records):
		self.__events = list ()

		self.__records = records

		# schedule daily random call
		self.__add_random_call (datetime.datetime.today ())
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

	def add_text (self, text:str, time=0):
		self.__add_event (time, (EVENT_TYPE.TEXT, text))
		return

	def add_shout (self, call:int, filter, time:datetime.time):
		day = datetime.date.today ()

		# don't schedule for the past
		if time < datetime.datetime.now ().time ():
			day += datetime.timedelta (1)

		time = datetime.datetime.combine (day, time)
		time = int (time.timestamp ())

		event = (EVENT_TYPE.DAILY_SHOUT, call, filter)

		self.__add_event (time, event)
		return


	def __get_random_call_time (self, day:datetime.date) -> int:
		min_hour = datetime.time (MIN_HOUR)
		max_hour = datetime.time (MAX_HOUR)

		# don't schedule for the past
		current_time = datetime.datetime.now ().time ()

		if max_hour < current_time:
			day += datetime.timedelta (1)

		elif min_hour < current_time:
			min_hour = current_time

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

	def process (self, tts, player):
		if 0 == len (self.__events):
			return

		_time = self.__events[0][0]
		if _time < self.__get_time ():
			event = self.__events.pop (0)[1]

			if EVENT_TYPE.CALL == event[0]:
				self.__process_call (event[1], player)

			elif EVENT_TYPE.TEXT == event[0]:
				self.__process_text (event[1], tts, player)

			elif EVENT_TYPE.DAILY_RANDOM == event[0]:
				self.__process_call (event[1], player)

				tomorrow = datetime.date.today ()
				tomorrow += datetime.timedelta (1)
				self.__add_random_call (tomorrow)

			elif EVENT_TYPE.DAILY_SHOUT == event[0]:
				date = datetime.datetime.fromtimestamp (_time)
				if event[2] (date):
					self.__process_shout (event[1], player)

				self.add_shout (event[1], event[2],
				                date.time ())

		return

	def __process_call (self, call, player):
		print ("call in queue: %d" % call)
		if player.call (call):
			# still off-hook
			player.play_busy_tone ()
		return

	def __process_text (self, text, tts, player):
		tts.say (text)
		# still off-hook
		player.play_busy_tone ()
		return

	def __process_shout (self, call, player):
		if player.call (call, ring=False):
			# still off-hook
			player.play_busy_tone ()
		return
