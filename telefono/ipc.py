#!/usr/bin/python3
# -*- coding: utf-8 -*-

import socket

IPC_MAX_DATA = 4
IPC_BYTEORDER = "big"

class IPC:
	def __init__ (self, fd):
		self.__fd = fd
		self.__socket = socket.socket (fileno=fd)

	def queue_call (self, recording:int):
		data = recording.to_bytes (IPC_MAX_DATA, IPC_BYTEORDER,
		                           signed=False)
		self.__socket.send (b"\0" + data)
		return

	def queue_message (self, message:str):
		message = message.encode ()
		self.__socket.send (b"\1" + message + b"\0")
		return
