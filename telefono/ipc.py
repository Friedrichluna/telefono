#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import socket

IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"

class IPC_MESSAGE (enum.IntEnum):
	ERROR = 0
	CALL = 1
	TTS = 2

IPC_CALL_ID_SIZE = 4

IPC_TTS_MESSAGE_SIZE = IPC_MAX_DATA -1 -1


class IPC_ANSWER (enum.IntEnum):
	OK = 0
	ERROR = 1

IPC_ANSWER_SIZE = 4


class IPC:
	def __init__ (self, socket):
		self.__socket = socket
		return

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
			return (IPC_MESSAGE.ERROR, None)

		message_type = IPC_MESSAGE (message[0])

		if IPC_MESSAGE.CALL == message_type:
			payload = self.__deserialize_call (message[1:])

		elif IPC_MESSAGE.TTS == message_type:
			payload = self.__deserialize_tts (message[1:])

		if payload is None:
			return (IPC_MESSAGE.ERROR, None)

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

	def _serialize_answer (self, answer:IPC_ANSWER) -> bytearray:
		data = bytearray ()

		answer_id = answer.to_bytes (IPC_ANSWER_SIZE,
		                             IPC_BYTEORDER,
		                             signed=False)
		data.extend (answer_id)
		return data

	def _deserialize_answer (self, message:bytes) -> IPC_ANSWER:
		if len(message) < IPC_ANSWER_SIZE:
			return IPC_ANSWER.ERROR

		answer = int.from_bytes (message[:IPC_ANSWER_SIZE],
		                         IPC_BYTEORDER, signed=False)
		return IPC_ANSWER (answer)

	def _send (self, message):
		self.__socket.send (message)
		return

	def _recv (self, size, blocking=True):
		if blocking:
			return self.__socket.recv (size)

		try:
			return self.__socket.recv (size,
			                           socket.MSG_DONTWAIT)

		# no queued call
		except BlockingIOError:
			return b""



class IPC_Client (IPC):
	def __init__ (self, fd):
		super ().__init__ (socket.socket (fileno=fd))
		return

	def queue_call (self, call_id:int):
		data = self._serialize_call (call_id)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Anruf %d abgesetzt" % call_id

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten."

		return "Ein Fehler ist aufgetreten."

	def queue_message (self, message:str):
		data = self._serialize_tts (message)
		if not data:
			return "Ein Fehler ist aufgetreten."

		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Text angesagt"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten."

		return "Ein Fehler ist aufgetreten."


class IPC_Server (IPC):
	def __init__ (self):

		server, client = socket.socketpair (socket.AF_UNIX,
	                                            socket.SOCK_DGRAM,
	                                            0)

		super ().__init__ (server)

		# needs to store the whole socket object,
		# as otherwise it is GC'ed
		self.__client = client
		return

	def get_client_fd (self):
		return self.__client.fileno ()

	def handle_message (self, queue):

		data = self._recv (IPC_MAX_DATA, blocking=False)
		if b"" == data:
			return

		message_type, payload = self._deserialize (data)

		if IPC_MESSAGE.ERROR == message_type:
			data = self._serialize_answer (IPC_ANSWER.ERROR)
			self._send (data)
			return

		elif IPC_MESSAGE.CALL == message_type:
			queue.add_call (payload)

			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		elif IPC_MESSAGE.TTS == message_type:
			queue.add_text (payload)

			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		data = self._serialize_answer (IPC_ANSWER.ERROR)
		self._send (data)
		return
