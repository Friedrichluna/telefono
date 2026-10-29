#!/usr/bin/python3
# -*- coding: utf-8 -*-

import collections
import datetime
import logging
import os
import threading
import time

import psutil

from ..CONSTANTS import VCS_VERSION
from ..CONSTANTS import RECORD_DIR
from ..CONSTANTS import RECORD_PREFIX
from ..CONSTANTS import RECORD_SUFFIX
from ..CONSTANTS import HISTORY_MAX_SIZE

from ..audio import mp3_duration


log = logging.getLogger (__name__)


# status page (/status): the state of the phone and its history
# (src/history.py), everything read from files and /proc, never through
# the main process (works while the phone is used) and without
# starting programs


THERMAL_FILE = "/sys/class/thermal/thermal_zone0/temp"
WIRELESS_FILE = "/proc/net/wireless"

WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


# German numbers: 1,5
def decimal (value:float, digits:int=1) -> str:
	return ("%.*f" % (digits, value)).replace (".", ",")


def size_text (size:int) -> str:
	if size < 1000 * 1000:
		return "%s kB" % decimal (size / 1000)

	if size < 1000 * 1000 * 1000:
		return "%s MB" % decimal (size / 1000 / 1000)

	return "%s GB" % decimal (size / 1000 / 1000 / 1000)


# e.g. 12 s, 2:05 min, 1:02 Std., 3 Tage 4 Std.
def duration_text (seconds:float) -> str:
	if seconds < 60:
		return "%s s" % decimal (seconds) if seconds < 10 \
		       else "%d s" % seconds

	seconds = int (seconds)
	if seconds < 3600:
		return "%d:%02d min" % (seconds // 60, seconds % 60)

	if seconds < 2 * 86400:
		return "%d:%02d Std." % (seconds // 3600, seconds // 60 % 60)

	return "%d Tage %d Std." % (seconds // 86400, seconds // 3600 % 24)


# e.g. "heute 14:03", "gestern 09:12", "Mo 27.10.2026 18:30"
def day_text (day:datetime.date, today:datetime.date) -> str:
	if day == today:
		return "Heute"

	if day == today - datetime.timedelta (1):
		return "Gestern"

	return "%s %s" % (WEEKDAYS[day.weekday ()], day.strftime ("%d.%m.%Y"))


def moment_text (timestamp:float, now:float=None) -> str:
	moment = datetime.datetime.fromtimestamp (timestamp)
	today = datetime.date.fromtimestamp (now or time.time ())
	return "%s %s" % (day_text (moment.date (), today),
	                  moment.strftime ("%H:%M"))


# length of all recordings, cached by name, size and time of change
# (the mp3 header is only read for new or changed files)
class Recordings ():
	def __init__ (self, directory:str=RECORD_DIR):
		self.directory = directory
		self.__lock = threading.Lock ()
		self.__durations = dict ()
		return

	# (count, bytes, seconds), seconds None if a length is unknown
	def summary (self) -> (int, int, float):
		count, size, seconds = 0, 0, 0.0
		durations = dict ()

		with self.__lock, os.scandir (self.directory) as entries:
			for entry in entries:
				if not entry.name.startswith (RECORD_PREFIX) \
				or not entry.name.endswith (RECORD_SUFFIX) \
				or not entry.is_file ():
					continue

				stat = entry.stat ()
				key = (entry.name, stat.st_size, stat.st_mtime_ns)

				if key in self.__durations:
					duration = self.__durations[key]
				else:
					try:
						duration = mp3_duration (entry.path)
					except (OSError, IndexError, KeyError) as error:
						log.warning ("length of %s: %r",
						             entry.path, error)
						duration = None

				durations[key] = duration

				count += 1
				size += stat.st_size
				if duration is None or seconds is None:
					seconds = None
				else:
					seconds += duration

			# forget removed files
			self.__durations = durations

		return count, size, seconds


# temperature of the CPU in °C, None if unknown
def cpu_temperature ():
	try:
		with open (THERMAL_FILE) as f:
			return int (f.read ()) / 1000

	except (OSError, ValueError):
		return None


# (interface, level in dBm, quality) of the first WLAN interface,
# None if there is none
def wlan_signal ():
	try:
		with open (WIRELESS_FILE) as f:
			lines = f.readlines ()[2:]

	except OSError:
		return None

	for line in lines:
		name, _, values = line.partition (":")
		values = values.split ()

		try:
			return name.strip (), float (values[2]), float (values[1])
		except (IndexError, ValueError):
			continue

	return None


def wlan_text (signal) -> str:
	if signal is None:
		return "kein WLAN"

	name, level, quality = signal

	if level >= -60:
		rating = "gut"
	elif level >= -70:
		rating = "mittel"
	else:
		rating = "schwach"

	return "%s, %d dBm (%s), Qualität %d/70" % (rating, level, name,
	                                             quality)


def rss (pid:int):
	try:
		return psutil.Process (pid).memory_info ().rss
	except psutil.Error:
		return None


# the status table: list of (label, text)
def system_status (started, recordings:Recordings, history_size:int,
                   history_count:int) -> list:
	now = time.time ()
	items = [("Version", VCS_VERSION)]

	if started is not None:
		items.append (("Telefono läuft seit",
		               "%s (%s)" % (moment_text (started, now),
		                            duration_text (now - started))))

	boot = psutil.boot_time ()
	items.append (("System läuft seit", "%s (%s)"
	               % (moment_text (boot, now), duration_text (now - boot))))

	try:
		count, size, seconds = recordings.summary ()
		text = "%d, %s" % (count, size_text (size))
		if seconds is not None:
			text += ", %s" % duration_text (seconds)
	except OSError as error:
		log.error ("reading %s failed: %s", recordings.directory, error)
		text = "nicht lesbar"
	items.append (("Aufnahmen", text))

	try:
		disk = psutil.disk_usage (RECORD_DIR)
		items.append (("Freier Speicher", "%s GiB von %s GiB"
		               % (decimal (disk.free / 2**30),
		                  decimal (disk.total / 2**30))))
	except OSError:
		pass

	memory = psutil.virtual_memory ()
	text = "%d MB von %d MB frei" % (memory.available // 2**20,
	                                 memory.total // 2**20)
	main, webapp = rss (os.getppid ()), rss (os.getpid ())
	if main is not None and webapp is not None:
		text += " (Telefono %d MB, Webapp %d MB)" % (main // 2**20,
		                                             webapp // 2**20)
	items.append (("Arbeitsspeicher", text))

	items.append (("Prozessorlast", " / ".join (decimal (load, 2)
	               for load in os.getloadavg ()) + " (1, 5, 15 min)"))

	temperature = cpu_temperature ()
	if temperature is not None:
		items.append (("CPU-Temperatur", "%s °C" % decimal (temperature)))

	items.append (("WLAN", wlan_text (wlan_signal ())))

	items.append (("Verlauf", "%d Ereignisse, %s (höchstens %s, dann "
	               "werden die ältesten gelöscht)"
	               % (history_count, size_text (history_size),
	                  size_text (HISTORY_MAX_SIZE))))
	return items


# the history filters of the page: key, title, event types
FILTERS = (
	("", "Alle", None),
	("anrufe", "Anrufe", ("call", "dial_empty", "menu")),
	("hoerer", "Hörer", ("off_hook", "on_hook")),
	("aufnahmen", "Aufnahmen", ("recording", )),
	("webapp", "Webapp", ("webapp", )),
	("system", "System", ("start", "stop", "random_planned")),
)


def matches (event:dict, types) -> bool:
	return types is None or event.get ("event") in types


def quoted (text) -> str:
	return "„%s“" % text


def number_text (event:dict) -> str:
	return str (event.get ("number", "?"))


def seconds_text (event:dict) -> str:
	seconds = event.get ("seconds")
	if not isinstance (seconds, (int, float)):
		return ""

	return duration_text (seconds)


def call_text (event:dict) -> str:
	number = number_text (event)
	cause = event.get ("cause")
	kind = event.get ("kind")
	result = event.get ("result")
	seconds = seconds_text (event)

	if "out" == event.get ("direction"):
		if "menu" == cause:
			text = "Menü ruft %s an" % number
		else:
			text = "%s gewählt" % number
	elif "random" == cause:
		text = "Zufallsanruf %s" % number
	elif "shout" == cause:
		text = "Durchsage %s" % number
	else:
		text = "Anruf %s aus der Webapp" % number

	if "list" == kind and "routed" in event:
		text += " (Liste, gespielt: %s)" % event["routed"]
	elif "callback" == kind:
		text += " (Zeitansage)"

	incoming = "in" == event.get ("direction") and "shout" != cause

	if "not picked up" == result:
		return text + ": nicht abgenommen"

	if "no recording" == result:
		return text + ": nicht vergeben"

	if "complete" == result:
		text += ": abgenommen, bis zum Ende" if incoming \
		        else ": bis zum Ende"
		return text + (" (%s)" % seconds if seconds else "")

	if "aborted" == result:
		if "shout" == cause:
			text += ": abgebrochen, Hörer aufgelegt"
		elif incoming:
			text += ": abgenommen, aufgelegt"
		else:
			text += ": aufgelegt"
		return text + (" nach %s" % seconds if seconds else "")

	return text


RECORDING_RESULTS = {
	"end": "Aufnahme %s gespeichert",
	"max_time": "Aufnahme %s gespeichert, Höchstlänge erreicht",
	"abort": "Aufnahme %s verworfen (mittlerer Knopf)",
	"min_time": "Aufnahme %s zu kurz, verworfen",
	"error": "Aufnahme %s fehlgeschlagen",
}

WEBAPP_TESTS = {
	"led": "LED-Test",
	"speaker": "Test des Lautsprecher-Relais",
	"handset_sound": "Testton im Hörer",
	"speaker_sound": "Testton im Lautsprecher",
	"ring_sound": "Klingel-Test",
}

VOLUME_NAMES = (("handset", "Hörer"),
                ("speaker", "Lautsprecher"),
                ("ring", "Klingeln"))


def volume_text (event:dict) -> str:
	parts = []
	for key, name in VOLUME_NAMES:
		if key not in event:
			continue

		value = event[key]
		if value is None:
			parts.append ("%s nicht mehr eingestellt" % name)
		else:
			parts.append ("%s %s %%" % (name, value))

	text = "Webapp: Lautstärke geändert"
	return text + (": " + ", ".join (parts) if parts else "")


def webapp_text (event:dict) -> str:
	action = event.get ("action")
	number = number_text (event)

	if "call" == action:
		if "no number" == event.get ("result"):
			return "Webapp: Anruf %s, Nummer nicht vergeben" % number
		return "Webapp: Anruf %s angefordert" % number

	if "text" == action:
		return "Webapp: Text angesagt %s" % quoted (event.get ("text", ""))

	if "description" == action:
		return "Webapp: Beschreibung von %s geändert in %s" \
		       % (number, quoted (event.get ("description", "")))

	if "upload" == action:
		if event.get ("number") is None:
			return "Webapp: Aufnahme hochgeladen"

		text = "Webapp: Aufnahme %s hochgeladen" % number
		if event.get ("description"):
			text += " %s" % quoted (event["description"])
		return text

	if "test" == action:
		return "Webapp: %s" % WEBAPP_TESTS.get (event.get ("output"),
		                                        event.get ("output"))

	if "volume" == action:
		return volume_text (event)

	return "Webapp: %s" % action


# German text of an event
def event_text (event:dict, now:float=None) -> str:
	kind = event.get ("event")
	seconds = seconds_text (event)

	if "start" == kind:
		return "Telefono gestartet (Version %s)" % event.get ("version", "?")

	if "stop" == kind:
		if "button" == event.get ("reason"):
			return "Telefono beendet (mittlerer Knopf)"
		return "Telefono beendet"

	if "off_hook" == kind:
		return "Hörer abgenommen"

	if "on_hook" == kind:
		return "Hörer aufgelegt" + (" nach %s" % seconds if seconds else "")

	if "dial_empty" == kind:
		return "Nichts gewählt (Besetztzeichen)"

	if "menu" == kind:
		option = event.get ("option")
		if option is None:
			return "Menü: nichts gewählt"
		if isinstance (option, int) and 0 <= option <= 3:
			return "Menü: %d gewählt" % option
		return "Menü: %s gewählt, gibt es nicht" % option

	if "call" == kind:
		return call_text (event)

	if "recording" == kind:
		text = RECORDING_RESULTS.get (event.get ("result"),
		                              "Aufnahme %s: " + str (event.get ("result")))
		text %= number_text (event)
		return text + (" (%s)" % seconds if seconds else "")

	if "random_planned" == kind:
		at = event.get ("at")
		if isinstance (at, (int, float)):
			return "Zufallsanruf %s geplant für %s" \
			       % (number_text (event), moment_text (at, now).lower ())
		return "Zufallsanruf %s geplant" % number_text (event)

	if "webapp" == kind:
		return webapp_text (event)

	return str (kind)


# the newest events (newest first) matching the filter, grouped by day:
# [(day text, [(time text, text, event type), ...]), ...]
def history_days (events:list, types, limit:int, now:float=None) -> list:
	now = now or time.time ()
	today = datetime.date.fromtimestamp (now)

	days = list ()
	shown = 0
	for event in reversed (events):
		if shown >= limit:
			break

		if not matches (event, types):
			continue

		try:
			moment = datetime.datetime.fromtimestamp (event["time"])
			text = event_text (event, now)

		# a hand-edited or strange line, it should not break the page
		except (ValueError, TypeError, OverflowError, OSError):
			continue

		day = day_text (moment.date (), today)
		if not days or days[-1][0] != day:
			days.append ((day, list ()))

		days[-1][1].append ((moment.strftime ("%H:%M:%S"), text,
		                     event["event"]))
		shown += 1

	return days


# most dialed numbers and the calls of the last days
def statistics (events:list, days:int, top:int, now:float=None) -> dict:
	now = now or time.time ()
	today = datetime.date.fromtimestamp (now)
	first = today - datetime.timedelta (days - 1)

	dialed = collections.Counter ()
	per_day = collections.OrderedDict ()
	for index in range (days):
		day = today - datetime.timedelta (index)
		per_day[day] = {"day": day_text (day, today), "dialed": 0,
		                "incoming": 0, "answered": 0, "recordings": 0}

	for event in events:
		kind = event.get ("event")
		if kind not in ("call", "recording"):
			continue

		try:
			day = datetime.date.fromtimestamp (event["time"])
		except (ValueError, TypeError, OverflowError, OSError):
			continue

		if "call" == kind and "out" == event.get ("direction") \
		and "dial" == event.get ("cause"):
			dialed[str (event.get ("number"))] += 1

		if day < first or day not in per_day:
			continue

		counts = per_day[day]
		if "recording" == kind:
			if event.get ("result") in ("end", "max_time"):
				counts["recordings"] += 1
		elif "out" == event.get ("direction"):
			counts["dialed"] += 1
		elif "shout" != event.get ("cause"):
			counts["incoming"] += 1
			if "not picked up" != event.get ("result"):
				counts["answered"] += 1

	since = None
	if events:
		try:
			since = moment_text (events[0]["time"], now)
		except (ValueError, TypeError, OverflowError, OSError):
			pass

	rows = list (per_day.values ())
	most = max ([1] + [row["dialed"] + row["incoming"] for row in rows])

	return {
		"dialed": dialed.most_common (top),
		"days": rows,
		"most": most,
		"since": since,
	}
