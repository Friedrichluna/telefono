#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import socket

IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"

class IPC_MESSAGE (enum.IntEnum):
	ERROR = 0
	CALL = 1
	TTS = 2,
	GET_DESCRIPTION = 3,

IPC_INT_SIZE = 4

IPC_TTS_MESSAGE_SIZE = IPC_MAX_DATA -1 -1


class IPC_ANSWER (enum.IntEnum):
	OK = 0
	ERROR = 1,
	DESCRIPTION = 2,

IPC_DESCRIPTION_SIZE = 128

IPC_ANSWER_SIZE = 1 + IPC_DESCRIPTION_SIZE + 1


class IPC:
	def __init__ (self, socket):
		self.__socket = socket
		return

	def __serialize_int (self, integer:int) -> bytes:
		return integer.to_bytes (IPC_INT_SIZE,
		                         IPC_BYTEORDER,
		                         signed=False)

	def __deserialize_int (self, message:bytes) -> int:
		if len (message) < IPC_INT_SIZE:
			return None

		return int.from_bytes (message[:IPC_INT_SIZE],
		                       IPC_BYTEORDER, signed=False)

	def __serialize_str (self, string:str, max_size:int) -> bytes:
		if len (string) > max_size:
			print ("string too long")
			return b""

		return string.encode () + b"\0"

	def __deserialize_str (self, message:bytes, max_size) -> str:
		size = 0
		while size < max_size \
		and message[size] != 0:
			size += 1

		return message[:size].decode ()

	def _serialize_call (self, call_id:int) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.CALL)
		data.extend (self.__serialize_int (call_id))

		return data

	def _serialize_tts (self, message:str) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.TTS)

		text = self.__serialize_str (message,
		                             IPC_TTS_MESSAGE_SIZE)
		if not text:
			return bytearray ()

		data.extend (text)
		return data

	def _deserialize (self, message:bytes) -> (IPC_MESSAGE, object):

		if len (message) < 1:
			return (IPC_MESSAGE.ERROR, None)

		message_type = IPC_MESSAGE (message[0])

		if IPC_MESSAGE.CALL == message_type:
			payload = self.__deserialize_call (message[1:])

		elif IPC_MESSAGE.TTS == message_type:
			payload = self.__deserialize_tts (message[1:])

		elif IPC_MESSAGE.GET_DESCRIPTION == message_type:
			payload = self.__deserialize_record_get (message[1:])

		if payload is None:
			return (IPC_MESSAGE.ERROR, None)

		return (message_type, payload)

	def __deserialize_call (self, message:bytes) -> int:
		return self.__deserialize_int (message)

	def __deserialize_tts (self, message:bytes) -> str:
		return self.__deserialize_str (message,
		                               IPC_TTS_MESSAGE_SIZE)

	def _serialize_record_get (self, call_id:int) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.GET_DESCRIPTION)
		data.extend (self.__serialize_int (call_id))

		return data

	def __deserialize_record_get (self, message:bytes) -> int:
		return self.__deserialize_int (message)

	def _serialize_answer (self, answer:IPC_ANSWER,
	                       payload:bytes=b"") -> bytearray:
		data = bytearray ()
		data.append (answer)
		data.extend (payload)
		return data

	def _deserialize_answer (self, message:bytes) -> IPC_ANSWER:
		if len(message) < 1:
			return IPC_ANSWER.ERROR

		answer = IPC_ANSWER (message[0])

		if IPC_ANSWER.OK == answer:
			return answer, None

		if IPC_ANSWER.ERROR == answer:
			return answer, None

		if IPC_ANSWER.DESCRIPTION == answer:
			payload = self.__deserialize_description (message[1:])
			return answer, payload

	def _serialize_description (self, description:str) -> bytes:
		return self.__serialize_str (description,
		                             IPC_DESCRIPTION_SIZE)

	def __deserialize_description (self, message:bytes) -> str:
		return self.__deserialize_str (message,
		                               IPC_DESCRIPTION_SIZE)

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

	def get_description (self, call_id:int):
		data = self._serialize_record_get (call_id)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, data = self._deserialize_answer (data)

		if IPC_ANSWER.DESCRIPTION == answer:
			return data

		return None

	def queue_call (self, call_id:int):
		data = self._serialize_call (call_id)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Anruf %d abgesetzt" % call_id, "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		return "Ein Fehler ist aufgetreten.", "error"

	def queue_message (self, message:str):
		data = self._serialize_tts (message)
		if not data:
			return "Ein Fehler ist aufgetreten.", "error"

		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Text angesagt", "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		return "Ein Fehler ist aufgetreten.", "error"


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

	def handle_message (self, queue, records):

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

		elif IPC_MESSAGE.GET_DESCRIPTION == message_type \
		and payload in records:
			description = records[payload].description
			data = self._serialize_description (description)
			if data:
				data = self._serialize_answer (
				                        IPC_ANSWER.DESCRIPTION,
				                        data)
				self._send (data)
				return

		data = self._serialize_answer (IPC_ANSWER.ERROR)
		self._send (data)
		return
