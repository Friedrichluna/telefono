#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import enum
import logging
import random
import time

from .CONSTANTS import DEBUG_TIME_FORMAT

from .CONSTANTS import MIN_HOUR
from .CONSTANTS import MAX_HOUR

from . import Record


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

	def add_call (self, call:Record, time=0):
		logging.info ("EventQueue: schedule call %d for %s",
		              call.number, self.__get_debug_time (time))
		self.__add_event (time, (EVENT_TYPE.CALL, call))
		return

	def add_text (self, text:str, time=0):
		logging.info ("EventQueue: schedule text %s for %s",
		              text, self.__get_debug_time (time))
		self.__add_event (time, (EVENT_TYPE.TEXT, text))
		return

	def add_shout (self, call:Record, filter, time:datetime.time):
		day = datetime.date.today ()

		# don't schedule for the past
		if time < datetime.datetime.now ().time ():
			day += datetime.timedelta (1)

		time = datetime.datetime.combine (day, time)
		time = int (time.timestamp ())

		event = (EVENT_TYPE.DAILY_SHOUT, call, filter)

		logging.info ("EventQueue: schedule shout %d for %s",
		              call.number, self.__get_debug_time (time))

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
			logging.error ("failed to schedule random call, "
			               "due to no calls being available")
			return

		event = (EVENT_TYPE.DAILY_RANDOM, call)
		time = self.__get_random_call_time (day)

		logging.info ("EventQueue: schedule random call %d for %s",
		              call.number, self.__get_debug_time (time))

		return self.__add_event (time, event)

	def __get_debug_time (self, timestamp):
		return time.strftime (DEBUG_TIME_FORMAT,
		                      time.localtime (timestamp))

	def process (self, player):
		if 0 == len (self.__events):
			return

		_time = self.__events[0][0]
		if _time < time.time ():
			event = self.__events.pop (0)[1]

			if EVENT_TYPE.CALL == event[0]:
				logging.info ("EventQueue: process call %d at %s",
				              event[1].number,
				              self.__get_debug_time (_time))
				self.__process_call (event[1], player)

			elif EVENT_TYPE.TEXT == event[0]:
				logging.info ("EventQueue: process text %s at %s",
				              event[1],
				              self.__get_debug_time (_time))
				self.__process_text (event[1], player)

			elif EVENT_TYPE.DAILY_RANDOM == event[0]:
				logging.info ("EventQueue: process random call %d at %s",
				              event[1].number,
				              self.__get_debug_time (_time))
				self.__process_call (event[1], player)

				tomorrow = datetime.date.today ()
				tomorrow += datetime.timedelta (1)
				self.__add_random_call (tomorrow)

			elif EVENT_TYPE.DAILY_SHOUT == event[0]:
				logging.info ("EventQueue: process shout %s at %s",
				              event[1],
				              self.__get_debug_time (_time))
				date = datetime.datetime.fromtimestamp (_time)
				if event[2] (date):
					self.__process_shout (event[1], player)
				else:
					logging.info ("EventQueue: suppress shout due to filter")

				self.add_shout (event[1], event[2],
				                date.time ())
			else:
				logging.error ("EventQueue: failed to handle unknown event type %s", event[0])

		return

	def __process_call (self, call, player):
		if player.call (call):
			# still off-hook
			player.play_busy_tone ()
		return

	def __process_text (self, text, player):
		if player.say (text, interruptible=False):
			# still off-hook
			player.play_busy_tone ()
		return

	def __process_shout (self, call, player):
		if player.call (call, ring=False):
			# still off-hook
			player.play_busy_tone ()
		return
