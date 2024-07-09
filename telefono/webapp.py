#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import socket
import sys

from flask import Flask, redirect, render_template, request

import psutil


from CONSTANTS import FLASK_DEBUG
from CONSTANTS import FLASK_IP
from CONSTANTS import FLASK_PORT

from CONSTANTS import RECORD_DIR
from CONSTANTS import RECORD_PREFIX
from CONSTANTS import RECORD_SUFFIX

from CONSTANTS import UPLOAD_DIR

from CONSTANTS import WEBAPP_LOG_FILE

from records import Records

IPC_MAX_DATA = 4
IPC_BYTEORDER = "big"

def queue_call (connection:socket.socket, recording:int):
	data = recording.to_bytes (IPC_MAX_DATA, IPC_BYTEORDER,
	                           signed=False)
	connection.send (b"\0" + data)
	return

def queue_message (connection:socket.socket, message:str):
	message = message.encode ()
	connection.send (b"\1" + message + b"\0")
	return

def getFreeDiskSpace():
	hdd = psutil.disk_usage (UPLOAD_DIR)
	return round(hdd.free / (2**30), 2)


class TelefonoWebApp (Flask):
	def __init__ (self, records, connection):
		super ().__init__ (__name__)

		self.records = records
		self.connection = connection

		self.add_url_rule ("/", "home", self.home, methods=["POST", "GET"])
		self.add_url_rule ("/list", "list", self.list)
		self.add_url_rule ("/edit/<int:index>", "edit_value", self.edit_value, methods=["GET", "POST"])
		self.add_url_rule ("/get_value", "get_value", self.get_value, methods=["POST"])
		self.add_url_rule ("/say", "say", self.say, methods=["GET", "POST"])
		self.add_url_rule ("/upload", "upload_page", self.upload_page)
		self.add_url_rule ("/upload", "upload_file", self.upload_file, methods=["POST"])
		return

	def home(self):
		if request.method == "POST":
			requested_number = request.form["nm"]
			print(requested_number)

			# ignore malicious number
			if not requested_number.isdecimal ():
				return render_template ("index.html")

			recording = int (requested_number)
			queue_call (self.connection, recording)

			return render_template("index.html", content = requested_number)
		else:
			return render_template("index.html")

	def list(self):
		self.records.sync_fs ()
		return render_template("list.html", records=self.records)

	def edit_value(self, index):
		if request.method == "POST":
			new_value = request.form["new_value"]
			self.records[index] = new_value

			return redirect("/list")
		return render_template("edit.html", index=index, value=self.records[index])

	def get_value(self):
		# Get the selected button value from the frontend
		requested_number = request.form["selected_value"]

		# ignore malicious number
		if not requested_number.isdecimal ():
			return render_template("index.html")

		recording = int (requested_number)
		queue_call (self.connection, recording)

		return redirect("/list") #jsonify({"message": "Value received successfully"})

	def say (self):
		if request.method == "POST":
			text = request.form["text"]

			queue_message (self.connection, text)

		return render_template ("say.html")


	def upload_page(self):
		diskSpace = getFreeDiskSpace()
		return render_template("upload.html", diskSpace = diskSpace)


	def upload_file(self):
		uploaded_file = request.files["file"]
		requested_number = request.form["requestedNumber"]

		if (not uploaded_file.filename) or (not requested_number):
			return redirect ("/upload")

		if not requested_number.isdecimal ():
			return render_template("upload.html", content ="Keine Nummer angegeben!".format(requested_number))

		requested_number = int(requested_number)

		if requested_number in self.records:
			return render_template("upload.html", content ="Nummer {} existiert bereits!".format(requested_number))
		if not uploaded_file.filename.endswith(".wav"):
			return render_template("upload.html", content = "Bitte nur .wav hochladen!")

		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(requested_number) + RECORD_SUFFIX
		uploaded_file.save(file_path)

		self.records.sync_fs ()
		print("test")
		return render_template("upload.html", content ="erfolgreich unter {} gespeichert!".format(file_path))

def main ():
	if not sys.argv[1].isdecimal ():
		print ("invalid fileno")
		sys.exit (1)

	records = Records ()
	records.sync_fs ()

	# setup connection to server
	connection = socket.socket (fileno=int(sys.argv[1]))

	app = TelefonoWebApp (records, connection)
	app.run(host=FLASK_IP, port=FLASK_PORT, debug=FLASK_DEBUG)

if __name__ == "__main__":
	try:
		main ()

	except Exception as error:
		# creating/opening a file
		f = open(WEBAPP_LOG_FILE, "a")

		# writing in the file
		f.write (time.asctime ())
		f.write (": ")
		f.write (str (error))
		f.write ("\n")

		# closing the file
		f.close()
