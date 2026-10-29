#!/usr/bin/python3
# -*- coding: utf-8 -*-

import contextlib
import errno
import logging
import math
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import wave

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for

import psutil

from werkzeug.exceptions import RequestEntityTooLarge

from ..CONSTANTS import FLASK_TEMPLATES
from ..CONSTANTS import FLASK_STATIC

from ..CONSTANTS import CONFIG_FILE
from ..CONSTANTS import DIAGNOSE_POLL_INTERVAL
from ..CONSTANTS import SPEAKER_POWERON_DELAY

from ..CONSTANTS import RECORD_DIR
from ..CONSTANTS import RECORD_PREFIX
from ..CONSTANTS import RECORD_SUFFIX

from ..CONSTANTS import UPLOAD_DIR
from ..CONSTANTS import UPLOAD_MAX_SIZE
from ..CONSTANTS import UPLOAD_CHECK_FRAMES
from ..CONSTANTS import UPLOAD_EXTENSIONS
from ..CONSTANTS import MP3_ENCODE_TIMEOUT

from ..CONSTANTS import BROWSER_RECORD_MIN
from ..CONSTANTS import BROWSER_RECORD_MAX
from ..CONSTANTS import BROWSER_RECORD_TOLERANCE

from ..CONSTANTS import HISTORY_FILE
from ..CONSTANTS import STATUS_EVENTS
from ..CONSTANTS import STATUS_EVENTS_MAX
from ..CONSTANTS import STATUS_DAYS
from ..CONSTANTS import STATUS_TOP_NUMBERS
from ..CONSTANTS import STATUS_REFRESH

from ..CONSTANTS import VOLUME_FILE
from ..CONSTANTS import RING_VOLUME

from ..audio import EncodeError
from ..audio import EncodeTimeout
from ..audio import NoAudioError
from ..audio import convert_audio
from ..audio import encode_mp3
from ..audio import probe_mp3
from ..audio import save_file
from ..config import PINS
from ..config import load_inverted
from ..diagnose import GpioError
from ..diagnose import GpioRegisters
from ..diagnose import INPUTS as DIAGNOSE_INPUTS
from ..diagnose import OUTPUTS as DIAGNOSE_OUTPUTS
from ..diagnose import Sampler
from ..diagnose import all_pins
from ..diagnose import evaluate_inputs
from ..diagnose import evaluate_outputs
from ..history import HistoryReader
from ..ipc import IPC_DESCRIPTION_MAX_BYTES
from ..ipc import IPC_OUTPUT
from ..ipc import IPC_StringTooLong
from ..ipc import IPC_Timeout
from ..ipc import IPC_TTS_MESSAGE_MAX_BYTES
from ..number import Number
from ..volume import CHANNELS as VOLUME_CHANNELS
from ..volume import Mixer
from ..volume import MixerError
from ..volume import read_settings
from ..volume import to_db
from ..volume import to_percent
from ..volume import to_step
from ..volume import write_settings

from . import status


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


# same name as Subscriber.register_file, e.g. recording007.mp3; only
# built from a parsed number (digits), so it is always in RECORD_DIR
def recording_path (number:Number) -> str:
	return os.path.join (RECORD_DIR,
	                     RECORD_PREFIX + str (number) + RECORD_SUFFIX)


# the numbers (as str) that have a recording file, read from the
# directory and not from the main process, like the recording routes
def recorded_numbers () -> set:
	numbers = set ()

	try:
		with os.scandir (RECORD_DIR) as entries:
			for entry in entries:
				name = entry.name
				if not name.startswith (RECORD_PREFIX) \
				or not name.endswith (RECORD_SUFFIX):
					continue

				number = name[len (RECORD_PREFIX):-len (RECORD_SUFFIX)]
				if parse_number (number) and entry.is_file ():
					numbers.add (number)

	# no play buttons then, the list is still shown
	except OSError as error:
		# the same logger as the app's (Flask.logger)
		logging.getLogger (__name__).error ("reading %s failed: %s",
		                                    RECORD_DIR, error)

	return numbers


# start time of the main process (the webapp's parent), to see whether
# telefono.conf was changed after it read it; None if unknown
def telefono_start_time ():
	try:
		return psutil.Process (os.getppid ()).create_time ()

	except psutil.Error:
		return None


# CONFIG_FILE as the hardware test page shows it (German): status, the
# problems found, and whether it is newer than the running telefono
def config_state (config, started) -> dict:
	problems = list ()

	if config.error:
		status = "fehlerhaft, nichts ist invertiert"
		problems.append ("Die Datei kann nicht gelesen werden: %s"
		                 % config.error)

	elif not config.found:
		if os.path.exists (config.path):
			status = "nicht lesbar, nichts ist invertiert"
		else:
			status = "nicht vorhanden, nichts ist invertiert"

	else:
		status = "vorhanden"

	for section in config.unknown_sections:
		problems.append ("Unbekannter Abschnitt [%s] wird ignoriert."
		                 % section)

	for key in config.unknown_inputs:
		problems.append ("Unbekannter Eintrag „%s“ wird ignoriert." % key)

	for key, value in config.invalid.items ():
		problems.append ("„%s = %s“: nur yes oder no erlaubt, %s ist "
		                 "nicht invertiert." % (key, value, key))

	changed = False
	if started is not None:
		try:
			changed = os.stat (config.path).st_mtime > started
		except OSError:
			pass

	return {
		"path": config.path,
		"found": config.found,
		"status": status,
		"problems": problems,
		"changed": changed,
	}


# the outputs the hardware test page can switch through the main process
TEST_OUTPUTS = {
	"led": (IPC_OUTPUT.LED, "Die LED blinkt."),
	"speaker": (IPC_OUTPUT.SPEAKER,
	            "Das Lautsprecher-Relais ist für %d s eingeschaltet."
	            % SPEAKER_POWERON_DELAY),
}


# the volume page: the settings (key, name), the test sounds (through
# the main process, only if it is idle right now) and their messages
VOLUME_ITEMS = (("handset", "Hörer"),
                ("speaker", "Lautsprecher"),
                ("ring", "Klingeln"))

TEST_SOUNDS = {
	"handset": (IPC_OUTPUT.HANDSET_SOUND, "Testton im Hörer wird abgespielt."),
	"speaker": (IPC_OUTPUT.SPEAKER_SOUND,
	            "Testton im Lautsprecher wird abgespielt (der Lautsprecher "
	            "braucht %d s zum Einschalten)." % SPEAKER_POWERON_DELAY),
	"ring": (IPC_OUTPUT.RING_SOUND, "Das Telefon klingelt einmal."),
}


# e.g. "85 % (-6 dB)", "stumm"; db None: unknown
def level_text (percent:int, db, muted:bool) -> str:
	if muted:
		return "stumm"

	if db is None:
		return "%d %%" % percent

	db = round (db)
	return "%d %% (%s dB)" % (percent, "0" if 0 == db
	                                   else ("+%d" % db if db > 0
	                                         else "\u2212%d" % -db))


# the upload can not be used, the message is shown to the user
class InvalidUpload (Exception):
	pass


# the main process did not say which number is free
class NoFreeNumber (Exception):
	pass


# what happened to one uploaded file: HTTP status, message (German),
# message type (success, error, warning) and the number it got
class UploadResult:
	def __init__ (self, status:int, message:str, message_type:str,
	              number:Number=None):
		self.status = status
		self.message = message
		self.type = message_type
		self.number = number
		return


BUSY_MESSAGE = "Telefon beschäftigt, bitte später nochmal versuchen."

# the extensions for the templates, e.g. ".mp3, .wav, .m4a"
UPLOAD_EXTENSIONS_TEXT = ", ".join (UPLOAD_EXTENSIONS)

WRONG_EXTENSION = "Bitte nur Audiodateien hochladen (%s)!" \
                  % UPLOAD_EXTENSIONS_TEXT


# e.g. 2:05 min
def minutes (seconds:float) -> str:
	seconds = int (seconds)
	return "%d:%02d min" % (seconds // 60, seconds % 60)


# ffmpeg needs the upload as a file it can open through /proc and seek
# in (mp4); werkzeug spools uploads in a SpooledTemporaryFile, whose
# fileno () moves it from memory into /tmp; a stream without a file
# (e.g. BytesIO) is copied into a temporary file (closed afterwards)
@contextlib.contextmanager
def upload_as_file (stream):
	stream.seek (0)

	try:
		stream.fileno ()

	# io.UnsupportedOperation is an OSError
	except (OSError, AttributeError):
		pass

	else:
		yield stream
		return

	with tempfile.TemporaryFile () as f:
		shutil.copyfileobj (stream, f)
		f.flush ()
		f.seek (0)
		yield f

	return


# the page's own script sends forms in the background
# (data-async in the templates) and wants a JSON answer
def is_async ():
	return "XMLHttpRequest" == request.headers.get ("X-Requested-With")


class TelefonoWebApp (Flask):
	def __init__ (self, ipc):
		super ().__init__ (__name__, template_folder=FLASK_TEMPLATES, static_folder=FLASK_STATIC)

		self.ipc = ipc

		# port of the https server, if there is one (set by main),
		# the record page links to it from http
		self.https_port = None

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
		self.add_url_rule ("/record", "record_page", self.record_page)
		self.add_url_rule ("/record", "record_save", self.record_save, methods=["POST"])
		self.add_url_rule ("/record/free", "record_free", self.record_free)
		self.add_url_rule ("/help", "help", self.help)
		self.add_url_rule ("/status", "status", self.show_status)
		self.add_url_rule ("/recording/<number>", "recording", self.recording)
		self.add_url_rule ("/download/<number>", "download", self.download)
		self.add_url_rule ("/diagnose", "diagnose", self.diagnose, methods=["GET", "POST"])
		self.add_url_rule ("/diagnose/data", "diagnose_data", self.diagnose_data)
		self.add_url_rule ("/volume", "volume", self.volume, methods=["GET", "POST"])

		# hardware test: GPIO registers read directly, not through
		# the main process (it does not answer while the phone is used)
		self.gpio = GpioRegisters ()
		self.sampler = Sampler (self.gpio)
		self.telefono_started = telefono_start_time ()

		# status page: the history file of the main process and the
		# lengths of the recordings, both read directly
		self.history = HistoryReader (HISTORY_FILE)
		self.recordings = status.Recordings (RECORD_DIR)

		# volume page: the settings file is written and the card set
		# here, not through the main process (so it also works while
		# the phone is busy); one change at a time
		self.mixer = Mixer ()
		self.volume_lock = threading.Lock ()

		# the test page updates several times a second,
		# that does not belong into the journal
		logging.getLogger ("werkzeug").addFilter (
		        lambda record: "/diagnose/data" not in record.getMessage ())

		self.register_error_handler (IPC_Timeout, self.busy)
		self.register_error_handler (IPC_StringTooLong, self.too_long)
		self.register_error_handler (RequestEntityTooLarge, self.too_large)

		# maxlength hints for the templates (counts characters,
		# so the byte limit is still checked here)
		self.jinja_env.globals.update (
		        description_max=IPC_DESCRIPTION_MAX_BYTES,
		        text_max=IPC_TTS_MESSAGE_MAX_BYTES,
		        upload_max=UPLOAD_MAX_SIZE // 2**20,
		        upload_extensions=UPLOAD_EXTENSIONS,
		        upload_extensions_text=UPLOAD_EXTENSIONS_TEXT,
		        record_min=BROWSER_RECORD_MIN,
		        record_max=BROWSER_RECORD_MAX)
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
			message = BUSY_MESSAGE

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

		message = "Datei zu groß, höchstens %d MiB erlaubt." \
		          % (UPLOAD_MAX_SIZE // 2**20)

		if "upload_file" == request.endpoint:
			return self.upload_reply (message, "error", 413)

		if "record_save" == request.endpoint:
			return self.record_reply (message, "error", 413)

		return self.reply ("message.html", "Eingabe zu groß.",
		                   "error", 413, back=request.path,
		                   back_title="Zurück")

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

		network_list = self.ipc.get_list ()

		return render_template("list.html",
		                       network_list=network_list,
		                       recorded=recorded_numbers ())

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
		                       value=self.ipc.get_description (number),
		                       recorded=os.path.isfile (recording_path (number)))

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
		return render_template ("help.html", net=status.network_names ())

	# state of the phone and its history, read from files (not through
	# the main process, so it also works while the phone is busy);
	# filter: see status.FILTERS, limit: number of events shown
	def show_status (self):
		filters = {key: types for key, _, types in status.FILTERS}

		selected = request.args.get ("filter", "")
		if selected not in filters:
			selected = ""

		try:
			limit = int (request.args.get ("limit", STATUS_EVENTS))
		except ValueError:
			limit = STATUS_EVENTS
		limit = max (1, min (limit, STATUS_EVENTS_MAX))

		error = None
		try:
			events = self.history.read ()
			size = os.stat (HISTORY_FILE).st_size if events else 0

		except OSError as failure:
			self.logger.error ("reading the history failed: %s", failure)
			error = "Der Verlauf kann nicht gelesen werden: %s" 			        % (failure.strerror or failure)
			events, size = [], 0

		types = filters[selected]
		count = sum (1 for event in events if status.matches (event, types))

		# "show more": the next step, up to STATUS_EVENTS_MAX
		more = None
		if count > limit and limit < STATUS_EVENTS_MAX:
			more = min (limit * 5, STATUS_EVENTS_MAX)

		response = self.make_response (render_template (
		        "status.html",
		        items=status.system_status (self.telefono_started,
		                                    self.recordings, size,
		                                    len (events)),
		        days=status.history_days (events, types, limit),
		        stats=status.statistics (events, STATUS_DAYS,
		                                 STATUS_TOP_NUMBERS),
		        filters=status.FILTERS, selected=selected,
		        limit=limit, count=count, more=more,
		        error=error, refresh=STATUS_REFRESH * 1000,
		        time=time.strftime ("%H:%M:%S")))

		response.cache_control.no_store = True
		return response

	# what the hardware test page shows; reads the GPIO registers and
	# telefono.conf on every call, never asks the main process
	def diagnose_state (self) -> dict:
		config = load_inverted (CONFIG_FILE)

		state = {
			"time": time.strftime ("%H:%M:%S"),
			"config": config_state (config, self.telefono_started),
			"error": None,
			"inputs": [],
			"outputs": [],
			"sampler": None,
		}

		try:
			snapshot = self.gpio.read (all_pins ())
			state["inputs"] = evaluate_inputs (snapshot, config)
			state["outputs"] = evaluate_outputs (snapshot, config)
			state["sampler"] = self.sampler.poll (config.inverted)

		except GpioError as error:
			state["error"] = "GPIO kann nicht gelesen werden: %s" % error

		# the page shows the error instead of the values
		except Exception as error:
			self.logger.exception ("reading the GPIO failed")
			state["error"] = "GPIO kann nicht gelesen werden: %r" % error

		return state

	def diagnose_data (self):
		response = jsonify (self.diagnose_state ())
		response.cache_control.no_store = True
		return response

	def diagnose (self):
		if "POST" == request.method:
			output = TEST_OUTPUTS.get (request.form.get ("output"))
			if output is None:
				return self.finish (url_for ("diagnose"),
				                    "Unbekannter Ausgang.", "error")

			# IPC_Timeout: busy message, done later
			if not self.ipc.test_output (output[0]):
				return self.finish (url_for ("diagnose"),
				                    "Ein Fehler ist aufgetreten.",
				                    "error")

			return self.finish (url_for ("diagnose"), output[1],
			                    "success")

		return render_template ("diagnose.html",
		                        state=self.diagnose_state (),
		                        specs=DIAGNOSE_INPUTS,
		                        pins=PINS,
		                        output_specs=DIAGNOSE_OUTPUTS,
		                        poll_interval=int (DIAGNOSE_POLL_INTERVAL * 1000))

	# what the volume page shows: [{key, name, value, minimum, maximum,
	# text, ...}] (value None: the card can not be read), the error
	# (German), the settings file and the mixer state (None on errors);
	# the value is what is saved, if it is, else what the card has
	def volume_state (self):
		settings, problems = read_settings (VOLUME_FILE)
		for problem in problems:
			self.logger.warning ("%s", problem)

		error = None
		try:
			mixer = self.mixer.read ()

			if len (mixer.values) <= max (VOLUME_CHANNELS.values ()):
				raise MixerError ("%s has %d channel(s)"
				                  % (mixer.name, len (mixer.values)))

		except MixerError as failure:
			self.logger.error ("reading the volume failed: %s", failure)
			error = "Die Lautstärke der Soundkarte kann nicht gelesen " \
			        "werden: %s" % failure
			mixer = None

		items = []
		for key, name in VOLUME_ITEMS:
			item = {"key": key, "name": name, "value": None}

			if "ring" == key:
				value = settings.get (key, RING_VOLUME)
				item.update (value=value, minimum=0, maximum=100,
				             percent=value, db=20 * math.log10 (value / 100)
				                            if value else None,
				             muted=0 == value, linear=True)

			elif mixer is not None:
				if key in settings:
					value = to_step (mixer, settings[key])
				else:
					value = mixer.values[VOLUME_CHANNELS[key]]

				item.update (value=value, minimum=mixer.minimum,
				             maximum=mixer.maximum,
				             percent=to_percent (mixer, value),
				             db=to_db (mixer, value),
				             muted=mixer.mute and value == mixer.minimum,
				             db_min=mixer.db_min, db_max=mixer.db_max,
				             mute=mixer.mute, linear=False)

			if item["value"] is not None:
				item["text"] = level_text (item["percent"], item["db"],
				                           item["muted"])
			items.append (item)

		return items, error, settings, mixer

	# without the script: back to the page with the message; with it:
	# JSON with the message and the levels
	def volume_reply (self, message:str, message_type:str, status:int=200,
	                  **context):
		if is_async ():
			return jsonify (message=message, type=message_type,
			                **context), status

		flash (message, message_type)
		return redirect (url_for ("volume"))

	# GET: the page; POST: saves the values that differ from what the
	# page showed (only those get into the file, the rest stays as it
	# is), sets the card, then plays the test sound (name "test")
	def volume (self):
		if "POST" != request.method:
			items, error, _, _ = self.volume_state ()
			response = self.make_response (render_template (
			        "volume.html", items=items, error=error))
			response.cache_control.no_store = True
			return response

		test = request.form.get ("test")
		if test is not None and test not in TEST_SOUNDS:
			return self.volume_reply ("Unbekannter Testton.", "error", 400)

		with self.volume_lock:
			items, error, settings, mixer = self.volume_state ()
			new = dict (settings)

			for item in items:
				key = item["key"]
				text = request.form.get (key)
				if text is None or item["value"] is None:
					continue

				try:
					value = int (text.strip ())
				except ValueError:
					value = None

				if value is None \
				or not item["minimum"] <= value <= item["maximum"]:
					return self.volume_reply ("Ungültiger Wert für %s."
					                          % item["name"], "error", 400)

				if value != item["value"]:
					new[key] = value if "ring" == key \
					           else to_percent (mixer, value)

			changed = new != settings
			if changed:
				try:
					write_settings (new, VOLUME_FILE)

				except OSError as failure:
					self.logger.error ("saving %s failed: %s",
					                   VOLUME_FILE, failure)
					return self.volume_reply ("Speichern fehlgeschlagen.",
					                          "error", 500)

				self.logger.info ("volume settings: %r", new)

			# the card gets what is saved (also after it was changed
			# some other way); the main process sees the new file
			# when it is free and logs it
			mixer_settings = {key: value for key, value in new.items ()
			                  if key in VOLUME_CHANNELS}
			if mixer is not None and mixer_settings:
				try:
					self.mixer.apply (mixer_settings)

				except MixerError as failure:
					self.logger.error ("setting the volume failed: %s",
					                   failure)
					return self.volume_reply (
					        ("Gespeichert, aber die " if changed else "Die ")
					        + "Soundkarte konnte nicht eingestellt werden.",
					        "error", 500)

			items = self.volume_state ()[0] if changed else items

		levels = {item["key"]: item["text"] for item in items
		          if item["value"] is not None}
		message = "Lautstärke gespeichert." if changed \
		          else "Lautstärke unverändert."

		if test is None:
			return self.volume_reply (message, "success", levels=levels)

		output, test_message = TEST_SOUNDS[test]
		saved = "Lautstärke gespeichert. " if changed else ""

		# a test that can not be done now is not done later (that
		# would surprise everyone), the main process skips it
		try:
			done = self.ipc.test_output (output, only_now=True)

		except IPC_Timeout:
			self.logger.warning ("telefono busy: test sound %s", test)
			return self.volume_reply (saved + BUSY_MESSAGE, "warning",
			                          503, levels=levels)

		if not done:
			return self.volume_reply (saved + "Ein Fehler ist aufgetreten.",
			                          "error", 500, levels=levels)

		return self.volume_reply (saved + test_message, "success",
		                          levels=levels)

	# the recording file itself, read from RECORD_DIR without asking
	# the main process, so it can also be heard while the phone is
	# busy; conditional: Range requests (seeking), ETag, 304
	def send_recording (self, number:str, as_attachment:bool):
		number = parse_number (number)
		if None is number:
			return self.reply ("message.html", INVALID_NUMBER,
			                   "error", 404, back=url_for ("list"),
			                   back_title="Zur Liste")

		try:
			response = send_file (recording_path (number),
			                      mimetype="audio/mpeg",
			                      as_attachment=as_attachment,
			                      download_name="telefono-%s%s"
			                                    % (number, RECORD_SUFFIX),
			                      conditional=True)

		# e.g. no recording (also a number too long for a file name)
		except OSError as error:
			if error.errno not in (errno.ENOENT, errno.ENOTDIR,
			                       errno.EISDIR, errno.ENAMETOOLONG):
				raise

		else:
			# werkzeug only sends it on answers to a Range request
			response.accept_ranges = "bytes"
			return response

		return self.reply ("message.html",
		                   "Unter der Nummer %s gibt es keine Aufnahme."
		                   % number, "error", 404,
		                   back=url_for ("list"), back_title="Zur Liste")

	def recording (self, number):
		return self.send_recording (number, False)

	def download (self, number):
		return self.send_recording (number, True)

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
	# it reads the upload from stdin, which has to be a real file
	def encode_wav (self, stream, f):
		try:
			with upload_as_file (stream) as source:
				encode_mp3 ("pipe:0", f, stdin=source)

		except EncodeError as error:
			self.logger.warning ("encoding the upload failed: %s", error)
			raise InvalidUpload ("Umwandeln der .wav Datei fehlgeschlagen.")

		return

	# any other audio file (AUDIO_INPUT_FORMATS) is converted to mp3
	# into f; max_duration: longer files are cut there (the caller
	# checks the returned duration of the mp3)
	def convert_upload (self, stream, f, max_duration:float=None) -> float:
		try:
			with upload_as_file (stream) as source:
				return convert_audio (source, f, max_duration)

		except NoAudioError as error:
			self.logger.warning ("upload has no audio: %s", error)
			raise InvalidUpload ("Die Datei enthält keinen Ton.")

		except EncodeTimeout as error:
			self.logger.warning ("converting the upload failed: %s", error)
			raise InvalidUpload ("Umwandeln dauert zu lange (mehr als %s), "
			                     "bitte eine kürzere Datei hochladen."
			                     % minutes (MP3_ENCODE_TIMEOUT))

		except EncodeError as error:
			self.logger.warning ("converting the upload failed: %s", error)
			raise InvalidUpload ("Keine gültige Audiodatei, oder "
			                     "Umwandeln fehlgeschlagen.")

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

	# the upload page again, with the number and description that were
	# entered (not read from request.form here: too_large can not parse
	# it); results: one line per file of an upload with several files
	def upload_reply (self, message:str, message_type:str,
	                  status:int=200, number:str="", description:str="",
	                  results:list=None):
		return self.reply ("upload.html", message, message_type,
		                   status,
		                   diskSpace=getFreeDiskSpace (),
		                   number=number,
		                   description=description,
		                   results=results)

	def upload_page(self):
		diskSpace = getFreeDiskSpace()
		return render_template("upload.html", diskSpace = diskSpace)

	# saves one uploaded file under the requested number, or under the
	# next free one if none is given (like a recording on the phone);
	# IPC_Timeout while asking whether the number is free or for the
	# next free number: nothing was saved
	def save_upload (self, uploaded_file, requested_number:str,
	                 description:str) -> UploadResult:
		def failed (message:str, status:int):
			return UploadResult (status, message, "error")

		if not uploaded_file or not uploaded_file.filename:
			return failed ("Keine Datei ausgewählt!", 400)

		message = too_long_message ("Beschreibung", description,
		                            IPC_DESCRIPTION_MAX_BYTES)
		if message:
			return failed (message, 400)

		saved = []

		# same name as Subscriber.register_file, e.g. recording007.mp3
		def path (number:Number) -> str:
			return os.path.join (UPLOAD_DIR, RECORD_PREFIX + str (number)
			                                 + RECORD_SUFFIX)

		# the next free number is only asked for once the file is
		# converted (that takes a while), and again if a file appeared
		# there meanwhile (e.g. a recording on the phone, or a second
		# upload at the same time)
		def next_name ():
			number = self.ipc.next_free ()
			if number is None:
				raise NoFreeNumber ()

			saved.append (number)
			return path (number)

		if requested_number:
			number = parse_number (requested_number)
			if None is number:
				return failed (INVALID_NUMBER, 400)

			if not self.ipc.is_free (number):
				return failed ("Nummer %s existiert bereits!" % number,
				               409)

			saved.append (number)
			filename, attempts = path (number), 1

		else:
			filename, attempts = next_name, 3

		stream = uploaded_file.stream
		file_type = uploaded_file.filename.lower ()

		if file_type.endswith (".mp3"):
			write = lambda f: self.copy_mp3 (stream, f)

		# saved as mp3 like all recordings
		elif file_type.endswith (".wav"):
			message = self.check_wav (stream)
			if message:
				return failed (message, 400)

			write = lambda f: self.encode_wav (stream, f)

		# e.g. m4a or ogg from a phone, checked and converted by ffmpeg
		elif file_type.endswith (UPLOAD_EXTENSIONS):
			write = lambda f: self.convert_upload (stream, f)

		else:
			return failed (WRONG_EXTENSION, 400)

		try:
			file_path = save_file (filename, write,
			                       directory=UPLOAD_DIR,
			                       attempts=attempts)

		except InvalidUpload as error:
			return failed (str (error), 400)

		# a file the main process does not know yet (e.g. copied
		# there by hand, or a second upload at the same time)
		except FileExistsError:
			return failed ("Nummer %s existiert bereits!" % saved[-1], 409)

		except NoFreeNumber:
			self.logger.error ("main process sent no free number")
			return failed ("Ein Fehler ist aufgetreten.", 500)

		# asking for the free number, nothing was saved (busy
		# message); a TimeoutError is an OSError, so before that
		except IPC_Timeout:
			raise

		# e.g. the SD card is full, nothing was written
		except OSError as error:
			self.logger.error ("saving %s failed: %s",
			                   saved[-1] if saved else "an upload", error)

			if errno.ENOSPC == error.errno:
				message = "Speichern fehlgeschlagen, nicht genug freier Speicher."
			else:
				message = "Speichern fehlgeschlagen."

			return failed (message, 500)

		number = saved[-1]
		self.logger.info ("uploaded %s", file_path)

		message = "Aufnahme unter Nummer %s gespeichert." % number

		# the file is saved, the main process registers it (and sets
		# the description) as soon as it is free; sending it again
		# would add another number, so this is no busy error
		try:
			self.ipc.upload (number, description)

		except IPC_Timeout:
			self.logger.warning ("telefono busy, %s is registered later",
			                     number)
			message += " Das Telefon ist gerade beschäftigt, sie " \
			           "erscheint in der Liste, sobald es frei ist."

		return UploadResult (200, message, "success", number)

	# the upload page's script sends one file per request (the phone
	# converts them one after the other, and /tmp is in RAM); without
	# the script several files can come in one request
	def upload_file(self):
		uploaded_files = [uploaded
		                  for uploaded in request.files.getlist ("file")
		                  if uploaded.filename]
		requested_number = request.form.get ("requestedNumber", "").strip ()
		description = request.form.get ("description", "").strip ()

		if 1 < len (uploaded_files):
			return self.upload_files (uploaded_files, requested_number,
			                          description)

		result = self.save_upload (uploaded_files[0] if uploaded_files
		                           else None,
		                           requested_number, description)

		if "success" != result.type:
			return self.upload_reply (result.message, result.type,
			                          result.status,
			                          number=requested_number,
			                          description=description)

		list_url = url_for ("list") + "#n%s" % result.number
		return self.finish (url_for ("upload_page"), result.message,
		                    "success",
		                    diskSpace=getFreeDiskSpace (),
		                    number=str (result.number),
		                    list_url=list_url)

	# several files in one request (form sent without the script): all
	# get the next free numbers in the order they came, one failing file
	# does not stop the others; the page shows a line for each
	def upload_files (self, uploaded_files:list, requested_number:str,
	                  description:str):
		def error (message:str):
			return self.upload_reply (message, "error", 400,
			                          number=requested_number,
			                          description=description)

		if requested_number:
			return error ("Mehrere Dateien bekommen die nächsten freien "
			              "Nummern, bitte keine Nummer eingeben (oder "
			              "nur eine Datei wählen).")

		message = too_long_message ("Beschreibung", description,
		                            IPC_DESCRIPTION_MAX_BYTES)
		if message:
			return error (message)

		results = []
		for uploaded in uploaded_files:
			try:
				result = self.save_upload (uploaded, "", description)

			# nothing saved; the phone may be free again for the next
			except IPC_Timeout:
				self.logger.warning ("telefono busy: %s not saved",
				                     uploaded.filename)
				result = UploadResult (503, BUSY_MESSAGE, "warning")

			results.append ({
				"name": uploaded.filename,
				"message": result.message,
				"type": result.type,
				"status": result.status,
				"number": None if result.number is None
				          else str (result.number),
			})

		saved = sum (1 for result in results
		             if "success" == result["type"])

		message = "%d von %d Dateien gespeichert." \
		          % (saved, len (results))

		if saved == len (results):
			message_type, status = "success", 200
		elif saved:
			message_type, status = "warning", 200
		else:
			message_type, status = "error", results[0]["status"]

		return self.upload_reply (message, message_type, status,
		                          results=results)

	# the page for recording in the browser: getUserMedia only works
	# on https (or localhost), from http it links to the https server
	def https_url (self):
		if request.is_secure or self.https_port is None:
			return None

		host = urllib.parse.urlsplit ("//" + request.host).hostname
		if not host:
			return None

		if ":" in host:
			host = "[%s]" % host

		return "https://%s:%d%s" % (host, self.https_port,
		                            url_for ("record_page"))

	# the record page again with the input (number, description), the
	# recording itself is still in the page (script) or has to be
	# chosen again (without script)
	def record_reply (self, message:str, message_type:str,
	                  status:int=200, number:str="", description:str=""):
		return self.reply ("record.html", message, message_type,
		                   status, https_url=self.https_url (),
		                   number=number, description=description)

	def record_page (self):
		return render_template ("record.html",
		                        https_url=self.https_url ())

	# the number a recording without a chosen number gets,
	# shown on the page (busy: 503 like everywhere)
	def record_free (self):
		number = self.ipc.next_free ()
		response = jsonify (number=None if number is None
		                           else str (number))
		response.cache_control.no_store = True
		return response

	# converts the recording (whatever the browser or the phone's
	# recorder app made) into f, checks its length
	def convert_recording (self, stream, f):
		maximum = BROWSER_RECORD_MAX + BROWSER_RECORD_TOLERANCE

		# a bit more than allowed, to see that it is too long
		duration = self.convert_upload (stream, f, maximum + 1)

		self.logger.info ("recording: %.1f s", duration)

		if duration > maximum:
			raise InvalidUpload ("Aufnahme zu lang, höchstens %s erlaubt. "
			                     "Längere Dateien bitte über „Upload“ "
			                     "hochladen."
			                     % minutes (BROWSER_RECORD_MAX))

		if duration < BROWSER_RECORD_MIN - BROWSER_RECORD_TOLERANCE:
			raise InvalidUpload ("Aufnahme zu kurz (%.1f s), mindestens "
			                     "%d s." % (duration, BROWSER_RECORD_MIN))

		return

	# saves a recording made in the browser (or with the phone's
	# recorder app) under the chosen or the next free number
	def record_save (self):
		uploaded_file = request.files.get ("file")
		requested_number = request.form.get ("requestedNumber", "").strip ()
		description = request.form.get ("description", "").strip ()

		def error (message:str, status:int):
			return self.record_reply (message, "error", status,
			                          number=requested_number,
			                          description=description)

		if not uploaded_file or not uploaded_file.filename:
			return error ("Keine Aufnahme vorhanden, bitte zuerst aufnehmen.",
			              400)

		message = too_long_message ("Beschreibung", description,
		                            IPC_DESCRIPTION_MAX_BYTES)
		if message:
			return error (message, 400)

		saved = []

		# the next free number is only asked for once the recording
		# is converted, and again if a file appeared there meanwhile
		def next_name ():
			number = self.ipc.next_free ()
			if number is None:
				raise NoFreeNumber ()

			saved.append (number)
			return recording_path (number)

		if requested_number:
			number = parse_number (requested_number)
			if None is number:
				return error (INVALID_NUMBER, 400)

			if not self.ipc.is_free (number):
				return error ("Nummer %s existiert bereits!" % number,
				              409)

			saved.append (number)
			filename, attempts = recording_path (number), 1

		else:
			filename, attempts = next_name, 3

		stream = uploaded_file.stream
		write = lambda f: self.convert_recording (stream, f)

		try:
			file_path = save_file (filename, write,
			                       directory=RECORD_DIR,
			                       attempts=attempts)

		except InvalidUpload as invalid:
			return error (str (invalid), 400)

		except FileExistsError:
			return error ("Nummer %s existiert bereits!" % saved[-1],
			              409)

		except NoFreeNumber:
			self.logger.error ("main process sent no free number")
			return error ("Ein Fehler ist aufgetreten.", 500)

		# asking for the free number, nothing was saved (busy
		# message); a TimeoutError is an OSError, so before that
		except IPC_Timeout:
			raise

		# e.g. the SD card is full, nothing was written
		except OSError as failure:
			self.logger.error ("saving a recording failed: %s", failure)

			if errno.ENOSPC == failure.errno:
				message = "Speichern fehlgeschlagen, nicht genug freier Speicher."
			else:
				message = "Speichern fehlgeschlagen."

			return error (message, 500)

		number = saved[-1]
		self.logger.info ("recorded %s", file_path)

		message = "Aufnahme unter Nummer %s gespeichert." % number

		# the file is saved, the main process registers it (and sets
		# the description) as soon as it is free; the page must not
		# keep the recording, saving it again would add another number
		try:
			self.ipc.upload (number, description)

		except IPC_Timeout:
			self.logger.warning ("telefono busy, %s is registered later",
			                     number)
			message += " Das Telefon ist gerade beschäftigt, sie " \
			           "erscheint in der Liste, sobald es frei ist."

		return self.finish (url_for ("list") + "#n%s" % number,
		                    message, "success", number=str (number),
		                    list_url=url_for ("list") + "#n%s" % number)
