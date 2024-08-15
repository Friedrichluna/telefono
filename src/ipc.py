#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import socket

from .number import Number


IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"

class IPC_MESSAGE (enum.IntEnum):
	ERROR = 0
	CALL = 1
	TTS = 2,
	GET_DESCRIPTION = 3,
	SET_DESCRIPTION = 4,
	LIST = 5,
	FREE = 6,
	UPLOAD = 7

IPC_INT_SIZE = 4
IPC_NUMBER_SIZE = 32

IPC_TTS_MESSAGE_SIZE = IPC_MAX_DATA -1 -1


class IPC_ANSWER (enum.IntEnum):
	OK = 0
	ERROR = 1
	NO_NUMBER = 2
	DESCRIPTION = 3
	LIST = 4

IPC_DESCRIPTION_SIZE = 128

IPC_ANSWER_SIZE = 1048576


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

	@staticmethod
	def serialize_str (string:str, max_size:int) -> bytes:
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

	@staticmethod
	def deserialize_str (message:bytes, max_size) -> (str, bytes):
		size = 0
		while size < max_size \
		and size < len(message) \
		and message[size] != 0:
			size += 1

		return message[:size].decode (), message[size+1:]

	def _serialize_call (self, number:Number) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.CALL)
		data.extend (number.to_bytes (IPC_NUMBER_SIZE, self))

		return data

	def _serialize_tts (self, message:str) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.TTS)

		text = IPC.serialize_str (message, IPC_TTS_MESSAGE_SIZE)
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

		elif IPC_MESSAGE.SET_DESCRIPTION == message_type:
			payload = self.__deserialize_record_set (message[1:])

		elif IPC_MESSAGE.LIST == message_type:
			payload = self.__deserialize_record_list (message[1:])

		elif IPC_MESSAGE.FREE == message_type:
			payload = self.__deserialize_free (message[1:])

		elif IPC_MESSAGE.UPLOAD == message_type:
			payload = self.__deserialize_upload (message[1:])

		if payload is None:
			return (IPC_MESSAGE.ERROR, None)

		return (message_type, payload)

	def __deserialize_call (self, message:bytes) -> Number:
		return Number.from_bytes (message, IPC_NUMBER_SIZE, self)[0]

	def __deserialize_tts (self, message:bytes) -> str:
		return self.__deserialize_str (message,
		                               IPC_TTS_MESSAGE_SIZE)

	def _serialize_record_get (self, number:Number) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.GET_DESCRIPTION)
		data.extend (number.to_bytes (IPC_NUMBER_SIZE, self))

		return data

	def __deserialize_record_get (self, message:bytes) -> Number:
		return Number.from_bytes (message, IPC_NUMBER_SIZE, self)[0]

	def _serialize_record_set (self, number:Number,
	                           description:str) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.SET_DESCRIPTION)
		data.extend (number.to_bytes (IPC_NUMBER_SIZE, self))
		data.extend (IPC.serialize_str (description,
		                                IPC_DESCRIPTION_SIZE))

		return data

	def __deserialize_record_set (self, message:bytes) -> (Number, str):
		number, message = Number.from_bytes (message,
		                                     IPC_NUMBER_SIZE,
		                                     self)

		value = self.__deserialize_str (message,
		                                IPC_DESCRIPTION_SIZE)
		return number, value

	def _serialize_record_list (self) -> bytearray:
		data = bytearray ()
		data.append (IPC_MESSAGE.LIST)
		return data

	def __deserialize_record_list (self, message:bytes):
		return b""

	def _serialize_free (self, number:Number):
		data = bytearray ()
		data.append (IPC_MESSAGE.FREE)
		data.extend (number.to_bytes (IPC_NUMBER_SIZE, self))
		return data

	def __deserialize_free (self, message:bytes) -> Number:
		return Number.from_bytes (message, IPC_NUMBER_SIZE, self)[0]

	def _serialize_upload (self) -> bytearray:
		data = bytearray ()
		data.append (IPC_MESSAGE.UPLOAD)
		return data

	def __deserialize_upload (self, message:bytes):
		return b""


	def _serialize_answer (self, answer:IPC_ANSWER,
	                       payload:bytes=b"") -> bytearray:
		data = bytearray ()
		data.append (answer)
		data.extend (payload)
		return data

	def _deserialize_answer (self, message:bytes) -> IPC_ANSWER:
		if len(message) < 1:
			return IPC_ANSWER.ERROR, None

		answer = IPC_ANSWER (message[0])

		if IPC_ANSWER.OK == answer:
			return answer, None

		if IPC_ANSWER.ERROR == answer:
			return answer, None

		if IPC_ANSWER.NO_NUMBER == answer:
			return answer, None

		if IPC_ANSWER.DESCRIPTION == answer:
			payload = self.__deserialize_description (message[1:])
			return answer, payload

		if IPC_ANSWER.LIST == answer:
			payload = self.__deserialize_list (message[1:])
			return answer, payload

	def _serialize_description (self, description:str) -> bytes:
		return IPC.serialize_str (description,
		                          IPC_DESCRIPTION_SIZE)

	def __deserialize_description (self, message:bytes) -> str:
		return self.__deserialize_str (message,
		                               IPC_DESCRIPTION_SIZE)

	def _serialize_list (self, network) -> bytes:
		data = bytearray ()

		data.extend (self.__serialize_int (len (network)))

		for number in network:
			number = Number (number)
			data.extend (number.to_bytes (IPC_NUMBER_SIZE,
			                              self))

			value = IPC.serialize_str (
			                        network[number].description,
			                        IPC_DESCRIPTION_SIZE)
			data.extend (value)

		return data

	def __deserialize_list (self, message:bytes) -> list:
		records = list ()

		length = self.__deserialize_int (message)
		message = message[IPC_INT_SIZE:]

		while True:
			number, message = Number.from_bytes (message,
			                                     IPC_NUMBER_SIZE,
			                                     self)
			if not number:
				break

			value, message = self.deserialize_str (
			                        message,
			                        IPC_DESCRIPTION_SIZE)

			records.append ((number, value))

		return records

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

	def get_description (self, number:Number):
		data = self._serialize_record_get (number)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, data = self._deserialize_answer (data)

		if IPC_ANSWER.DESCRIPTION == answer:
			return data

		return None

	def set_description (self, number:Number, description:str):
		data = self._serialize_record_set (number, description)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Beschreibung ge&auml;ndert.", "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		return "Ein Fehler ist aufgetreten.", "error"

	def get_list (self):
		data = self._serialize_record_list ()
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		_, network_list = self._deserialize_answer (data)

		return network_list

	def is_free (self, number:Number):
		data = self._serialize_free (number)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return True
		return False

	def upload (self):
		data = self._serialize_upload ()
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)
		return

	def queue_call (self, number:Number):
		data = self._serialize_call (number)
		self._send (data)

		data = self._recv (IPC_ANSWER_SIZE)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Anruf %d abgesetzt" % number, "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		elif IPC_ANSWER.NO_NUMBER == answer:
			return "Die Nummer %d ist nicht vergeben." \
			           % number, \
			       "error"

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

	def handle_message (self, queue, network):

		data = self._recv (IPC_MAX_DATA, blocking=False)
		if b"" == data:
			return

		message_type, payload = self._deserialize (data)

		if IPC_MESSAGE.ERROR == message_type:
			data = self._serialize_answer (IPC_ANSWER.ERROR)
			self._send (data)
			return

		elif IPC_MESSAGE.CALL == message_type:
			call = network[payload]
			if not call.is_callable ():
				data = self._serialize_answer (
				                IPC_ANSWER.NO_NUMBER)
				self._send (data)
				return

			queue.add_call (call)

			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		elif IPC_MESSAGE.TTS == message_type:
			queue.add_text (payload)

			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		elif IPC_MESSAGE.GET_DESCRIPTION == message_type \
		and payload in network:
			description = network[payload].description
			data = self._serialize_description (description)
			if data:
				data = self._serialize_answer (
				                        IPC_ANSWER.DESCRIPTION,
				                        data)
				self._send (data)
				return

		elif IPC_MESSAGE.SET_DESCRIPTION == message_type \
		and payload[0] in network:
			key, value = payload
			network[key].description = value

			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		elif IPC_MESSAGE.LIST == message_type:
			data = self._serialize_list (network)
			data = self._serialize_answer (IPC_ANSWER.LIST,
			                               data)

			self._send (data)
			return

		elif IPC_MESSAGE.FREE == message_type:
			if network[payload].is_assignable ():
				answer = IPC_ANSWER.OK
			else:
				answer = IPC_ANSWER.ERROR

			data = self._serialize_answer (answer)
			self._send (data)
			return

		elif IPC_MESSAGE.UPLOAD == message_type:
			network.sync_fs ()
			data = self._serialize_answer (IPC_ANSWER.OK)
			self._send (data)
			return

		data = self._serialize_answer (IPC_ANSWER.ERROR)
		self._send (data)
		return
