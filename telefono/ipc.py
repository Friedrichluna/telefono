#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import socket

IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"

class IPC_MESSAGE (enum.IntEnum):
	CALL = 0
	TTS = 1

IPC_CALL_ID_SIZE = 4

IPC_TTS_MESSAGE_SIZE = IPC_MAX_DATA -1 -1

class IPC:
	def __init__ (self, fd):
		self.__fd = fd
		self.__socket = socket.socket (fileno=fd)

	def _serialize_call (self, call_id:int) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.CALL)

		call = call_id.to_bytes (IPC_CALL_ID_SIZE,
		                         IPC_BYTEORDER,
		                         signed=False)
		data.extend (call)

		return data

	def _serialize_tts (self, message:str) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.TTS)

		message = message.encode ()

		if len (message) > IPC_TTS_MESSAGE_SIZE:
			print ("tts message too long")
			return bytearray ()

		data.extend (message)
		data.append (0)
		return data

	def _deserialize (self, message:bytes) -> (IPC_MESSAGE, object):

		if len (message) < 1:
			return (None, None)

		message_type = IPC_MESSAGE (message[0])

		if IPC_MESSAGE.CALL == message_type:
			payload = self.__deserialize_call (message[1:])

		elif IPC_MESSAGE.TTS == message_type:
			payload = self.__deserialize_tts (message[1:])

		if payload is None:
			return (None, None)

		return (message_type, payload)

	def __deserialize_call (self, message:bytes) -> int:
		if len (message) < IPC_CALL_ID_SIZE:
			return None

		call_id = int.from_bytes (message[:IPC_CALL_ID_SIZE],
		                          IPC_BYTEORDER, signed=False)

		return call_id

	def __deserialize_tts (self, message:bytes) -> str:
		size = 0
		while size < IPC_TTS_MESSAGE_SIZE \
		and message[size] != 0:
			size += 1

		return message[:size].decode ()

	def _send (self, message):
		self.__socket.send (message)
		return



class IPC_Client (IPC):
	def __init__ (self, fd):
		super ().__init__ (fd)
		return

	def queue_call (self, call_id:int):
		data = self._serialize_call (call_id)
		self._send (data)
		return

	def queue_message (self, message:str):
		data = self._serialize_tts (message)
		if not data:
			return

		self._send (data)
		return


class IPC_Server (IPC):
	def __init__ (self):

		server, client = socket.socketpair (socket.AF_UNIX,
	                                            socket.SOCK_DGRAM,
	                                            0)

		self.__socket = server
		self.__fd = server.fileno ()

		# needs to store the whole socket object,
		# as otherwise it is GC'ed
		self.__client = client
		return

	def get_client_fd (self):
		return self.__client.fileno ()

	def handle_message (self, tts, speaker, PickUp,
	                    newWavName, ringing):
		try:
			data = self.__socket.recv (IPC_MAX_DATA,
			                           socket.MSG_DONTWAIT)

		# no queued call
		except BlockingIOError:
			return

		message_type, payload = self._deserialize (data)

		if message_type is None:
			return

		elif IPC_MESSAGE.CALL == message_type:
			recording = newWavName (payload)
			print ("call in queue: %s" % recording)
			ringing (tts, recording, speaker, PickUp)

		elif IPC_MESSAGE.TTS == message_type:
			tts.say (payload)

		return
