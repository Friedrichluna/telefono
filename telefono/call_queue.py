#!/usr/bin/python3
# -*- coding: utf-8 -*-

class CallQueue:
	def __init__ (self):
		self.__calls = list ()
		return

	def add_call (self, call:int):
		self.__calls.append ((call, ))
		return

	def process (self, tts, speaker, PickUp, newWavName, ringing):
		if 0 == len (self.__calls):
			return

		call = self.__calls.pop (0)

		recording = newWavName (call[0])
		print ("call in queue: %s" % recording)
		ringing (tts, recording, speaker, PickUp)
