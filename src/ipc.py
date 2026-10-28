#!/usr/bin/python3
# -*- coding: utf-8 -*-

import enum
import logging
import select
import socket
import threading

from .CONSTANTS import IPC_TIMEOUT

from .number import Number


IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"

class IPC_MESSAGE (enum.IntEnum):
	ERROR = 0
	CALL = 1
	TTS = 2
	GET_DESCRIPTION = 3
	SET_DESCRIPTION = 4
	LIST = 5
	FREE = 6
	UPLOAD = 7

IPC_INT_SIZE = 4
IPC_NUMBER_SIZE = 32

# a string field holds the UTF-8 encoded string and a terminating NUL,
# the *_SIZE of a string field counts both,
# *_MAX_BYTES is the longest string (in bytes, umlauts take two)

# TTS datagram: message type + text field
IPC_TTS_MESSAGE_SIZE = IPC_MAX_DATA -1
IPC_TTS_MESSAGE_MAX_BYTES = IPC_TTS_MESSAGE_SIZE -1


class IPC_ANSWER (enum.IntEnum):
	OK = 0
	ERROR = 1
	NO_NUMBER = 2
	DESCRIPTION = 3
	LIST = 4

IPC_DESCRIPTION_SIZE = 128
IPC_DESCRIPTION_MAX_BYTES = IPC_DESCRIPTION_SIZE -1

IPC_ANSWER_SIZE = 1048576


# string does not fit into its field, raised instead of sending it
class IPC_StringTooLong (ValueError):
	def __init__ (self, size:int, max_size:int):
		super ().__init__ ("string too long: %d bytes, at most %d"
		                   % (size, max_size -1))
		self.size = size
		self.max_bytes = max_size -1
		return


# received message does not have the expected layout
class IPC_Malformed (ValueError):
	pass


# the main process did not answer within IPC_TIMEOUT
# queued: the request was sent and changes something (call, text,
#         description, upload), it is still executed later
class IPC_Timeout (TimeoutError):
	def __init__ (self, queued:bool):
		super ().__init__ ("no answer within %s s" % IPC_TIMEOUT)
		self.queued = queued
		return


class IPC:
	def __init__ (self, socket):
		self.__socket = socket
		self.log = logging.getLogger ("IPC")
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
		data = string.encode ()

		# the terminating NUL has to fit as well
		if len (data) >= max_size:
			raise IPC_StringTooLong (len (data), max_size)

		return data + b"\0"

	@staticmethod
	def deserialize_str (message:bytes, max_size) -> (str, bytes):
		size = 0
		while size < max_size \
		and size < len(message) \
		and message[size] != 0:
			size += 1

		if max_size == size or len (message) == size:
			raise IPC_Malformed ("no NUL within %d bytes"
			                     % max_size)

		try:
			return message[:size].decode (), message[size+1:]

		except UnicodeDecodeError as error:
			raise IPC_Malformed (str (error))

	# for strings the main process sends from its own data
	# (records.list may be edited by hand): shorten at a character
	# boundary rather than sending nothing
	def _shorten_str (self, string:str, max_size:int) -> str:
		data = string.encode ()
		if len (data) < max_size:
			return string

		self.log.warning ("%d bytes too long for IPC, shortened: %r",
		                  len (data), string)

		return data[:max_size -1].decode (errors="ignore")

	def _serialize_call (self, number:Number) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.CALL)
		data.extend (number.to_bytes (IPC_NUMBER_SIZE, self))

		return data

	def _serialize_tts (self, message:str) -> bytearray:
		data = bytearray ()

		data.append (IPC_MESSAGE.TTS)

		text = IPC.serialize_str (message, IPC_TTS_MESSAGE_SIZE)

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
		return self.deserialize_str (message,
		                             IPC_TTS_MESSAGE_SIZE)[0]

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

		value = self.deserialize_str (message,
		                              IPC_DESCRIPTION_SIZE)[0]
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
		description = self._shorten_str (description,
		                                 IPC_DESCRIPTION_SIZE)

		return IPC.serialize_str (description,
		                          IPC_DESCRIPTION_SIZE)

	def __deserialize_description (self, message:bytes) -> str:
		return self.deserialize_str (message,
		                             IPC_DESCRIPTION_SIZE)[0]

	def _serialize_list (self, network) -> bytes:
		data = bytearray ()
		length = 0

		for number in network:
			try:
				key = number.to_bytes (IPC_NUMBER_SIZE, self)

			except IPC_StringTooLong:
				self.log.warning ("number %s too long for IPC,"
				                  " not listed", number)
				continue

			data.extend (key)

			value = self._serialize_description (
			                        network[number].description)
			data.extend (value)
			length += 1

		return self.__serialize_int (length) + data

	def __deserialize_list (self, message:bytes) -> list:
		records = list ()

		length = self.__deserialize_int (message)
		message = message[IPC_INT_SIZE:]

		while message:
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

	# sleep for at most timeout seconds, but wake up as soon as a
	# message arrives (the main loop answers the webapp at once)
	def wait (self, timeout:float):
		select.select ((self.__socket, ), (), (), timeout)
		return



class IPC_Client (IPC):
	def __init__ (self, fd):
		client = socket.socket (fileno=fd)
		client.settimeout (IPC_TIMEOUT)
		super ().__init__ (client)

		# all webapp threads share this socket,
		# so only one request/answer pair at a time
		self.__lock = threading.Lock ()

		# requests that timed out: the server still answers them
		# later, in order, before the answer of the next request
		self.__pending = 0
		return

	def __request (self, data, queued:bool=False) -> bytes:
		with self.__lock:
			try:
				self._send (data)
			except TimeoutError:
				raise IPC_Timeout (False)

			try:
				# skip the late answers of timed out requests
				while self.__pending:
					self._recv (IPC_ANSWER_SIZE)
					self.__pending -= 1

				return self._recv (IPC_ANSWER_SIZE)

			except TimeoutError:
				self.__pending += 1
				raise IPC_Timeout (queued)

	def get_description (self, number:Number):
		data = self._serialize_record_get (number)
		data = self.__request (data)
		answer, data = self._deserialize_answer (data)

		if IPC_ANSWER.DESCRIPTION == answer:
			return data

		return None

	def set_description (self, number:Number, description:str):
		data = self._serialize_record_set (number, description)
		data = self.__request (data, queued=True)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Beschreibung geändert.", "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		return "Ein Fehler ist aufgetreten.", "error"

	def get_list (self):
		data = self._serialize_record_list ()
		data = self.__request (data)
		_, network_list = self._deserialize_answer (data)

		return network_list

	def is_free (self, number:Number):
		data = self._serialize_free (number)
		data = self.__request (data)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return True
		return False

	def upload (self):
		data = self._serialize_upload ()
		data = self.__request (data, queued=True)
		answer, _ = self._deserialize_answer (data)
		return

	def queue_call (self, number:Number):
		data = self._serialize_call (number)
		data = self.__request (data, queued=True)
		answer, _ = self._deserialize_answer (data)

		if IPC_ANSWER.OK == answer:
			return "Anruf %s abgesetzt" % number, "success"

		elif IPC_ANSWER.ERROR == answer:
			return "Ein Fehler ist aufgetreten.", "error"

		elif IPC_ANSWER.NO_NUMBER == answer:
			return "Die Nummer %s ist nicht vergeben." \
			           % number, \
			       "error"

		return "Ein Fehler ist aufgetreten.", "error"

	def queue_message (self, message:str):
		data = self._serialize_tts (message)
		data = self.__request (data, queued=True)
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

		try:
			message_type, payload = self._deserialize (data)

		# answer with an error rather than storing a broken value
		except ValueError as error:
			self.log.error ("malformed request %r: %s",
			                data[:40], error)
			message_type, payload = IPC_MESSAGE.ERROR, None

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
