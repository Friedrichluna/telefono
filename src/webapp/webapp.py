#!/usr/bin/python3
# -*- coding: utf-8 -*-

from flask import Flask, redirect, render_template, request

import psutil

from ..CONSTANTS import FLASK_TEMPLATES
from ..CONSTANTS import FLASK_STATIC

from ..CONSTANTS import RECORD_PREFIX
from ..CONSTANTS import RECORD_SUFFIX

from ..CONSTANTS import UPLOAD_DIR

from ..ipc import IPC_Timeout
from ..number import Number


def getFreeDiskSpace():
	hdd = psutil.disk_usage (UPLOAD_DIR)
	return round(hdd.free / (2**30), 2)


class TelefonoWebApp (Flask):
	def __init__ (self, ipc):
		super ().__init__ (__name__, template_folder=FLASK_TEMPLATES, static_folder=FLASK_STATIC)

		self.ipc = ipc

		self.add_url_rule ("/", "home", self.home, methods=["POST", "GET"])
		self.add_url_rule ("/list", "list", self.list, methods=["POST", "GET"])
		self.add_url_rule ("/edit/<int:index>", "edit_value", self.edit_value, methods=["GET", "POST"])
		self.add_url_rule ("/say", "say", self.say, methods=["GET", "POST"])
		self.add_url_rule ("/upload", "upload_page", self.upload_page)
		self.add_url_rule ("/upload", "upload_file", self.upload_file, methods=["POST"])

		self.register_error_handler (IPC_Timeout, self.busy)
		return

	# the main process did not answer, e.g. while a recording plays
	def busy (self, error):
		self.logger.warning ("telefono busy: %s %s",
		                     request.method, request.path)

		if error.queued:
			message = "Telefon beschäftigt, die Anfrage wird ausgeführt, sobald es wieder frei ist."
		else:
			message = "Telefon beschäftigt, bitte später nochmal versuchen."

		return render_template ("index.html",
		                        message=message,
		                        message_type="warning"), 503

	def home(self):
		if request.method == "POST":
			requested_number = request.form["nm"]
			print(requested_number)

			# ignore malicious number
			if not requested_number.isdecimal ():
				return render_template ("index.html")

			recording = int (requested_number)
			number = Number.from_int (recording)
			message, message_type = self.ipc.queue_call (number)

			return render_template("index.html",
			                       message=message,
			                       message_type=message_type)
		else:
			return render_template("index.html")

	def list(self):
		message, message_type = None, None

		if request.method == "POST":
			# Get the selected button value from the frontend
			requested_number = request.form["selected_value"]

			# ignore malicious number
			if not requested_number.isdecimal ():
				return render_template("index.html")

			recording = int (requested_number)
			number = Number.from_int (recording)
			message, message_type = self.ipc.queue_call (number)

		return render_template("list.html",
		                       network_list=self.ipc.get_list (),
		                       message=message,
		                       message_type=message_type)

	def edit_value(self, index):
		number = Number.from_int (index)

		if request.method == "POST":
			new_value = request.form["new_value"]
			self.ipc.set_description (number, new_value)

			return redirect("/list")

		return render_template("edit.html",
		                       value=self.ipc.get_description (number))

	def say (self):
		if request.method == "POST":
			text = request.form["text"]

			message, message_type = self.ipc.queue_message (text)
		else:
			message, message_type = None, None

		return render_template ("say.html",
		                        message=message,
		                        message_type=message_type)


	def upload_page(self):
		diskSpace = getFreeDiskSpace()
		return render_template("upload.html", diskSpace = diskSpace)


	def upload_file(self):
		uploaded_file = request.files["file"]
		requested_number = request.form["requestedNumber"]

		if (not uploaded_file.filename) or (not requested_number):
			return redirect ("/upload")

		if not requested_number.isdecimal ():
			return render_template("upload.html",
				message="Keine Nummer angegeben!",
				message_type="error")

		requested_number = int(requested_number)
		number = Number.from_int (requested_number)

		if not self.ipc.is_free (number):
			return render_template("upload.html",
				message="Nummer %s existiert bereits!" % number,
				message_type="error")

		if not uploaded_file.filename.endswith(".wav"):
			return render_template("upload.html",
				message="Bitte nur .wav hochladen!",
				message_type="error")

		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(number) + RECORD_SUFFIX
		uploaded_file.save(file_path)

		self.ipc.upload ()

		print("test")
		return render_template("upload.html",
			message="erfolgreich unter %s gespeichert!" % file_path,
			message_type="success")
