#!/usr/bin/python3
# -*- coding: utf-8 -*-

import errno
import os
import shutil
import wave

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

import psutil

from werkzeug.exceptions import RequestEntityTooLarge

from ..CONSTANTS import FLASK_TEMPLATES
from ..CONSTANTS import FLASK_STATIC

from ..CONSTANTS import RECORD_PREFIX
from ..CONSTANTS import RECORD_SUFFIX

from ..CONSTANTS import UPLOAD_DIR
from ..CONSTANTS import UPLOAD_MAX_SIZE
from ..CONSTANTS import UPLOAD_CHECK_FRAMES

from ..audio import EncodeError
from ..audio import encode_mp3
from ..audio import probe_mp3
from ..audio import save_file
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


INVALID_NUMBER = "Ungültige Nummer, bitte nur Ziffern (0-9) eingeben."

# numbers stay digit strings like on the phone, where dialing 0, 0, 7
# is a different number than 7 (recording007.mp3), so no int ();
# None if the text is empty or has anything but the digits 0-9
# (str.isdecimal would also accept other unicode digits)
def parse_number (text:str):
	if not text:
		return None

	try:
		return Number (text)

	except ValueError:
		return None


# the upload can not be used, the message is shown to the user
class InvalidUpload (Exception):
	pass


# the page's own script sends forms in the background
# (data-async in the templates) and wants a JSON answer
def is_async ():
	return "XMLHttpRequest" == request.headers.get ("X-Requested-With")


class TelefonoWebApp (Flask):
	def __init__ (self, ipc):
		super ().__init__ (__name__, template_folder=FLASK_TEMPLATES, static_folder=FLASK_STATIC)

		self.ipc = ipc

		# larger requests are refused before they are read
		self.config["MAX_CONTENT_LENGTH"] = UPLOAD_MAX_SIZE

		# only signs the flashed messages (session cookie),
		# so a new key on every start does not matter
		self.secret_key = os.urandom (16)

		self.add_url_rule ("/", "home", self.home, methods=["POST", "GET"])
		self.add_url_rule ("/list", "list", self.list, methods=["POST", "GET"])
		self.add_url_rule ("/edit/<number>", "edit_value", self.edit_value, methods=["GET", "POST"])
		self.add_url_rule ("/say", "say", self.say, methods=["GET", "POST"])
		self.add_url_rule ("/upload", "upload_page", self.upload_page)
		self.add_url_rule ("/upload", "upload_file", self.upload_file, methods=["POST"])
		self.add_url_rule ("/help", "help", self.help)

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

	# answer that keeps the form as it is (e.g. an error): JSON for
	# the page's script, otherwise the page again with the input
	def reply (self, template:str, message:str, message_type:str,
	           status:int=200, **context):
		if is_async ():
			return jsonify (message=message, type=message_type,
			                **context), status

		return render_template (template,
		                        message=message,
		                        message_type=message_type,
		                        **context), status

	# answer after the request was done: JSON for the page's script,
	# otherwise redirect, so reloading the page does not send the
	# form (e.g. the call) again
	def finish (self, url:str, message:str, message_type:str,
	            **context):
		if is_async ():
			return jsonify (message=message, type=message_type,
			                **context)

		flash (message, message_type)
		return redirect (url)

	# the main process did not answer, e.g. while a recording plays
	def busy (self, error):
		self.logger.warning ("telefono busy: %s %s",
		                     request.method, request.path)

		if error.queued:
			message = "Telefon beschäftigt, die Anfrage wird ausgeführt, sobald es wieder frei ist."
		else:
			message = "Telefon beschäftigt, bitte später nochmal versuchen."

		# only offer to send a GET again, a queued request
		# would be done twice
		if "GET" == request.method:
			back, back_title = request.full_path, "Nochmal versuchen"
		else:
			back, back_title = request.path, "Zurück"

		return self.reply ("message.html", message, "warning", 503,
		                   back=back, back_title=back_title)

	# input that does not fit into an IPC message (e.g. a very long
	# number), the description and text are checked before sending
	def too_long (self, error):
		self.logger.warning ("input too long: %s %s: %s",
		                     request.method, request.path, error)

		return self.reply ("message.html", "Eingabe zu lang.", "error",
		                   400, back=request.path, back_title="Zurück")

	# request larger than UPLOAD_MAX_SIZE (or a form field larger
	# than Flask's MAX_FORM_MEMORY_SIZE)
	def too_large (self, error):
		self.logger.warning ("request too large: %s %s: %s bytes",
		                     request.method, request.path,
		                     request.content_length)

		if "upload_file" != request.endpoint:
			return self.reply ("message.html", "Eingabe zu groß.",
			                   "error", 413, back=request.path,
			                   back_title="Zurück")

		return self.upload_reply ("Datei zu groß, höchstens %d MiB erlaubt."
		                          % (UPLOAD_MAX_SIZE // 2**20),
		                          "error", 413)

	def home(self):
		if request.method == "POST":
			requested_number = request.form["nm"]

			number = parse_number (requested_number)
			if None is number:
				return self.reply ("index.html", INVALID_NUMBER,
				                   "error", 400,
				                   number=requested_number)

			message, message_type = self.ipc.queue_call (number)
			if "success" != message_type:
				return self.reply ("index.html", message,
				                   message_type,
				                   number=requested_number)

			return self.finish (url_for ("home"), message, message_type)
		else:
			return render_template("index.html")

	def list(self):
		if request.method == "POST":
			# Get the selected button value from the frontend
			requested_number = request.form["selected_value"]

			number = parse_number (requested_number)
			if None is number:
				return self.finish (url_for ("list"),
				                    INVALID_NUMBER, "error")

			message, message_type = self.ipc.queue_call (number)

			# back to the number that was called
			return self.finish (url_for ("list") + "#n%s" % number,
			                    message, message_type)

		return render_template("list.html",
		                       network_list=self.ipc.get_list ())

	def edit_value(self, number):
		number = parse_number (number)
		if None is number:
			return self.reply ("message.html", INVALID_NUMBER,
			                   "error", 404, back=url_for ("list"),
			                   back_title="Zur Liste")

		if request.method == "POST":
			new_value = request.form["new_value"]

			message = too_long_message ("Beschreibung", new_value,
			                            IPC_DESCRIPTION_MAX_BYTES)
			if message:
				return self.reply ("edit.html", message,
				                   "error", 400, number=number,
				                   value=new_value)

			message, message_type = \
			        self.ipc.set_description (number, new_value)

			# e.g. the main process refused it
			if "error" == message_type:
				return self.reply ("edit.html", message,
				                   message_type, number=number,
				                   value=new_value)

			# back to the edited number
			return self.finish (url_for ("list") + "#n%s" % number,
			                    "Beschreibung von %s geändert." % number,
			                    message_type)

		return render_template("edit.html",
		                       number=number,
		                       value=self.ipc.get_description (number))

	def say (self):
		if request.method == "POST":
			text = request.form["text"]

			message = too_long_message ("Text", text,
			                            IPC_TTS_MESSAGE_MAX_BYTES)
			if message:
				return self.reply ("say.html", message, "error",
				                   400, text=text)

			message, message_type = self.ipc.queue_message (text)
			if "success" != message_type:
				return self.reply ("say.html", message,
				                   message_type, text=text)

			return self.finish (url_for ("say"), message, message_type)

		return render_template ("say.html")

	# static, does not ask the main process, so it
	# also works while the phone is busy
	def help (self):
		return render_template ("help.html")

	# ffmpeg encodes any channels, rate or sample width to mp3, but the
	# file must be complete; only PCM can be checked with the wave
	# module, so that is required
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
			return "Keine gültige .wav Datei, bitte eine " \
			       "unkomprimierte (PCM) .wav Datei hochladen."

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

	# ffmpeg encodes the wav into f (the temporary file of save_file);
	# stream is a file in /tmp (werkzeug spools uploads), so ffmpeg
	# reads it directly
	def encode_wav (self, stream, f):
		stream.seek (0)

		try:
			encode_mp3 ("pipe:0", f, stdin=stream)

		except EncodeError as error:
			self.logger.warning ("encoding the upload failed: %s", error)
			raise InvalidUpload ("Umwandeln der .wav Datei fehlgeschlagen.")

		return

	# mp3 files are saved as they are, after a check that
	# they really are mp3 with audio
	def copy_mp3 (self, stream, f):
		shutil.copyfileobj (stream, f)

		try:
			probe_mp3 (f)

		except EncodeError as error:
			self.logger.warning ("upload is no mp3 file: %s", error)
			raise InvalidUpload ("Keine gültige .mp3 Datei.")

		return

	# the upload page again, with the number that was entered
	# (not read from request.form here: too_large can not parse it)
	def upload_reply (self, message:str, message_type:str,
	                  status:int=200, number:str=""):
		return self.reply ("upload.html", message, message_type,
		                   status,
		                   diskSpace=getFreeDiskSpace (),
		                   number=number)

	def upload_page(self):
		diskSpace = getFreeDiskSpace()
		return render_template("upload.html", diskSpace = diskSpace)


	def upload_file(self):
		uploaded_file = request.files["file"]
		requested_number = request.form["requestedNumber"]

		if not uploaded_file.filename:
			return self.upload_reply ("Keine Datei ausgewählt!",
			                          "error", 400,
			                          number=requested_number)

		if not requested_number:
			return self.upload_reply ("Keine Nummer angegeben!",
			                          "error", 400,
			                          number=requested_number)

		number = parse_number (requested_number)
		if None is number:
			return self.upload_reply (INVALID_NUMBER, "error", 400,
			                          number=requested_number)

		if not self.ipc.is_free (number):
			return self.upload_reply ("Nummer %s existiert bereits!"
			                          % number, "error", 409,
			                          number=requested_number)

		stream = uploaded_file.stream
		file_type = uploaded_file.filename.lower ()

		if file_type.endswith (".mp3"):
			write = lambda f: self.copy_mp3 (stream, f)

		# saved as mp3 like all recordings
		elif file_type.endswith (".wav"):
			message = self.check_wav (stream)
			if message:
				return self.upload_reply (message, "error", 400,
				                          number=requested_number)

			write = lambda f: self.encode_wav (stream, f)

		else:
			return self.upload_reply ("Bitte nur .mp3 oder .wav hochladen!",
			                          "error", 400,
			                          number=requested_number)

		# same name as Subscriber.register_file, e.g. recording007.mp3
		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(number) + RECORD_SUFFIX
		try:
			save_file (file_path, write)

		except InvalidUpload as error:
			return self.upload_reply (str (error), "error", 400,
			                          number=requested_number)

		# a file the main process does not know yet (e.g. copied
		# there by hand, or a second upload at the same time)
		except FileExistsError:
			return self.upload_reply ("Nummer %s existiert bereits!"
			                          % number, "error", 409,
			                          number=requested_number)

		# e.g. the SD card is full, nothing was written
		except OSError as error:
			self.logger.error ("saving %s failed: %s", file_path, error)

			if errno.ENOSPC == error.errno:
				message = "Speichern fehlgeschlagen, nicht genug freier Speicher."
			else:
				message = "Speichern fehlgeschlagen."

			return self.upload_reply (message, "error", 500,
			                          number=requested_number)

		self.ipc.upload ()

		self.logger.info ("uploaded %s", file_path)
		return self.finish (url_for ("upload_page"),
		                    "Aufnahme unter Nummer %s gespeichert." % number,
		                    "success",
		                    diskSpace=getFreeDiskSpace ())
