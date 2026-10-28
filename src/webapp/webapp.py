#!/usr/bin/python3
# -*- coding: utf-8 -*-

import wave

from flask import Flask, redirect, render_template, request

import psutil

from werkzeug.exceptions import RequestEntityTooLarge

from ..CONSTANTS import FLASK_TEMPLATES
from ..CONSTANTS import FLASK_STATIC

from ..CONSTANTS import RECORD_PREFIX
from ..CONSTANTS import RECORD_SUFFIX

from ..CONSTANTS import UPLOAD_DIR
from ..CONSTANTS import UPLOAD_MAX_SIZE
from ..CONSTANTS import UPLOAD_CHECK_FRAMES

from ..ipc import IPC_DESCRIPTION_MAX_BYTES
from ..ipc import IPC_StringTooLong
from ..ipc import IPC_Timeout
from ..ipc import IPC_TTS_MESSAGE_MAX_BYTES
from ..number import Number


def getFreeDiskSpace():
	hdd = psutil.disk_usage (UPLOAD_DIR)
	return round(hdd.free / (2**30), 2)


# the IPC limits are in bytes (UTF-8), not characters
def too_long_message (name:str, text:str, max_bytes:int):
	size = len (text.encode ())
	if size <= max_bytes:
		return None

	return "%s zu lang: %d Bytes, höchstens %d erlaubt " \
	       "(Umlaute zählen doppelt)." % (name, size, max_bytes)


class TelefonoWebApp (Flask):
	def __init__ (self, ipc):
		super ().__init__ (__name__, template_folder=FLASK_TEMPLATES, static_folder=FLASK_STATIC)

		self.ipc = ipc

		# larger requests are refused before they are read
		self.config["MAX_CONTENT_LENGTH"] = UPLOAD_MAX_SIZE

		self.add_url_rule ("/", "home", self.home, methods=["POST", "GET"])
		self.add_url_rule ("/list", "list", self.list, methods=["POST", "GET"])
		self.add_url_rule ("/edit/<int:index>", "edit_value", self.edit_value, methods=["GET", "POST"])
		self.add_url_rule ("/say", "say", self.say, methods=["GET", "POST"])
		self.add_url_rule ("/upload", "upload_page", self.upload_page)
		self.add_url_rule ("/upload", "upload_file", self.upload_file, methods=["POST"])

		self.register_error_handler (IPC_Timeout, self.busy)
		self.register_error_handler (IPC_StringTooLong, self.too_long)
		self.register_error_handler (RequestEntityTooLarge, self.too_large)

		# maxlength hints for the templates (counts characters,
		# so the byte limit is still checked here)
		self.jinja_env.globals.update (
		        description_max=IPC_DESCRIPTION_MAX_BYTES,
		        text_max=IPC_TTS_MESSAGE_MAX_BYTES,
		        upload_max=UPLOAD_MAX_SIZE // 2**20)
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

	# input that does not fit into an IPC message (e.g. a very long
	# number), the description and text are checked before sending
	def too_long (self, error):
		self.logger.warning ("input too long: %s %s: %s",
		                     request.method, request.path, error)

		return render_template ("index.html",
		                        message="Eingabe zu lang.",
		                        message_type="error"), 400

	# request larger than UPLOAD_MAX_SIZE (or a form field larger
	# than Flask's MAX_FORM_MEMORY_SIZE)
	def too_large (self, error):
		self.logger.warning ("request too large: %s %s: %s bytes",
		                     request.method, request.path,
		                     request.content_length)

		if "upload_file" != request.endpoint:
			return render_template ("index.html",
			                        message="Eingabe zu groß.",
			                        message_type="error"), 413

		return render_template ("upload.html",
		                        diskSpace=getFreeDiskSpace (),
		                        message="Datei zu groß, höchstens %d MiB erlaubt."
		                                % (UPLOAD_MAX_SIZE // 2**20),
		                        message_type="error"), 413

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

			message = too_long_message ("Beschreibung", new_value,
			                            IPC_DESCRIPTION_MAX_BYTES)
			if message:
				return render_template ("edit.html",
				                        value=new_value,
				                        message=message,
				                        message_type="error"), 400

			message, message_type = \
			        self.ipc.set_description (number, new_value)

			# e.g. the main process refused it
			if "error" == message_type:
				return render_template ("edit.html",
				                        value=new_value,
				                        message=message,
				                        message_type=message_type)

			return redirect("/list")

		return render_template("edit.html",
		                       value=self.ipc.get_description (number))

	def say (self):
		if request.method == "POST":
			text = request.form["text"]

			message = too_long_message ("Text", text,
			                            IPC_TTS_MESSAGE_MAX_BYTES)
			if message:
				return render_template ("say.html",
				                        text=text,
				                        message=message,
				                        message_type="error"), 400

			message, message_type = self.ipc.queue_message (text)
		else:
			message, message_type = None, None

		return render_template ("say.html",
		                        message=message,
		                        message_type=message_type)


	# the recordings are played by ffplay, which does not care about
	# channels, rate or sample width, but the file must be complete;
	# only PCM can be checked with the wave module, so that is required
	def check_wav (self, stream):
		try:
			with wave.open (stream, "rb") as wav:
				frame_size = wav.getnchannels () * wav.getsampwidth ()
				expected = wav.getnframes () * frame_size

				size = 0
				data = wav.readframes (UPLOAD_CHECK_FRAMES)
				while data:
					size += len (data)
					data = wav.readframes (UPLOAD_CHECK_FRAMES)

		# wave raises a plain RuntimeError for a chunk that is
		# larger than the file
		except (wave.Error, EOFError, RuntimeError) as error:
			self.logger.warning ("upload is no PCM wav file: %s", error)
			return "Keine gültige .wav Datei, bitte eine unkomprimierte " 			       "(PCM) .wav Datei hochladen."

		finally:
			stream.seek (0)

		if 0 == expected:
			self.logger.warning ("upload has no audio data")
			return "Die .wav Datei enthält keine Audiodaten."

		if size < expected:
			self.logger.warning ("upload is truncated: %d of %d bytes",
			                     size, expected)
			return "Die .wav Datei ist unvollständig."

		return None

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

		message = self.check_wav (uploaded_file.stream)
		if message:
			return render_template ("upload.html",
			                        diskSpace=getFreeDiskSpace (),
			                        message=message,
			                        message_type="error"), 400

		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(number) + RECORD_SUFFIX
		uploaded_file.save(file_path)

		self.ipc.upload ()

		print("test")
		return render_template("upload.html",
			message="erfolgreich unter %s gespeichert!" % file_path,
			message_type="success")
