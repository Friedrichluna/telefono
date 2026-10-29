#!/usr/bin/python3
# -*- coding: utf-8 -*-

import collections
import json
import logging
import os
import re
import subprocess
import tempfile

from .CONSTANTS import MIXER_CMD
from .CONSTANTS import MIXER_CONTROLS
from .CONSTANTS import MIXER_SPEAKER_CHANNEL
from .CONSTANTS import MIXER_HANDSET_CHANNEL
from .CONSTANTS import MIXER_TIMEOUT
from .CONSTANTS import VOLUME_FILE
from .CONSTANTS import RING_VOLUME

from .history import history


log = logging.getLogger ("Volume")


# The volume of handset and loudspeaker (webapp page /volume).
#
# Hardware (docs/circuit_diagram.png): the USB card's left output goes
# to the amplifier of the loudspeaker, which the relay switches on (GPIO
# 4, see speaker.py), the right output to the handset. So both have
# their own channel of the card's playback volume control: nothing has
# to be switched when the relay switches, the levels are set in the
# card (amixer) and stay there. The ring is played by ffplay with its
# own volume (ffplay -volume, percent of the file's level), so it can be
# quieter than the rest of the loudspeaker.
#
# The settings (VOLUME_FILE) are in percent: of the control's range for
# handset and speaker (like amixer and alsamixer show it), of the full
# level for the ring. The webapp writes the file (atomically) and sets
# the mixer at once, also while the phone is busy; the main process sets
# the mixer from the file at startup, and again (and logs it in the
# history) when it sees that the file changed. Without the file (or
# without an entry) nothing is changed: the card keeps what alsactl
# restored at boot, the ring has RING_VOLUME.

# the entries of the settings file, all in percent (0 to 100)
KEYS = ("handset", "speaker", "ring")

# the mixer channel of the entries that are set in the card
CHANNELS = {"speaker": MIXER_SPEAKER_CHANNEL,
            "handset": MIXER_HANDSET_CHANNEL}


class MixerError (Exception):
	pass


# a playback volume control of the card: name, range (steps), current
# values (one per channel), the range in dB (None if unknown) and
# whether the lowest step is muted
MixerState = collections.namedtuple ("MixerState",
                                     ("name", "minimum", "maximum", "values",
                                      "db_min", "db_max", "mute"))


def to_percent (state:MixerState, step:int) -> int:
	if state.maximum <= state.minimum:
		return 100

	return round ((step - state.minimum) * 100
	              / (state.maximum - state.minimum))


# lossless for ranges of up to 100 steps: to_step (to_percent (x)) == x
def to_step (state:MixerState, percent:int) -> int:
	percent = max (0, min (100, percent))
	return state.minimum + round (percent * (state.maximum - state.minimum)
	                              / 100)


# None if the card does not say
def to_db (state:MixerState, step:int):
	if state.db_min is None or state.maximum <= state.minimum:
		return None

	return state.db_min + (step - state.minimum) \
	       * (state.db_max - state.db_min) / (state.maximum - state.minimum)


# ; type=INTEGER,access=rw---R--,values=2,min=0,max=37,step=0
RANGE_RE = re.compile (r";\s*type=INTEGER,.*?values=(\d+),min=(-?\d+),max=(-?\d+)")
# : values=37,37
VALUES_RE = re.compile (r"^\s*:\s*values=(-?\d+(?:,-?\d+)*)\s*$", re.MULTILINE)
# | dBminmaxmute-min=-37.00dB,max=0.00dB  (or dBminmax-...)
DB_MINMAX_RE = re.compile (r"\|\s*dBminmax(mute)?-min=(-?[\d.]+)dB,max=(-?[\d.]+)dB")
# | dBscale-min=-51.00dB,step=0.50dB,mute=1
DB_SCALE_RE = re.compile (r"\|\s*dBscale-min=(-?[\d.]+)dB,step=(-?[\d.]+)dB,mute=(\d)")


def parse_cget (name:str, text:str) -> MixerState:
	match = RANGE_RE.search (text)
	values = VALUES_RE.search (text)
	if not match or not values:
		raise MixerError ("unexpected amixer output for %s: %r"
		                  % (name, text[:200]))

	count, minimum, maximum = (int (x) for x in match.groups ())
	values = [int (x) for x in values.group (1).split (",")]

	if count != len (values):
		raise MixerError ("%s: %d values, expected %d"
		                  % (name, len (values), count))

	db_min = db_max = None
	mute = False

	db = DB_MINMAX_RE.search (text)
	if db:
		mute = bool (db.group (1))
		db_min, db_max = float (db.group (2)), float (db.group (3))

	else:
		db = DB_SCALE_RE.search (text)
		if db:
			db_min = float (db.group (1))
			db_max = db_min + float (db.group (2)) * (maximum - minimum)
			mute = "1" == db.group (3)

	return MixerState (name, minimum, maximum, values, db_min, db_max, mute)


# the playback volume control of the card that plays (amixer without
# -c: the "default" card, like sox, ffplay and espeak)
class Mixer ():
	def __init__ (self, command=MIXER_CMD, controls=MIXER_CONTROLS):
		self.command = tuple (command)
		self.controls = tuple (controls)
		self.__name = None
		return

	def __run (self, *args) -> str:
		try:
			result = subprocess.run ((*self.command, *args),
			                         capture_output=True, text=True,
			                         timeout=MIXER_TIMEOUT)

		except (OSError, subprocess.SubprocessError) as error:
			raise MixerError ("amixer: %s" % error)

		if result.returncode:
			raise MixerError ("amixer %s: %s"
			                  % (" ".join (args),
			                     result.stderr.strip ()
			                     or "exit status %d" % result.returncode))

		return result.stdout

	# the first of MIXER_CONTROLS the card has
	def name (self) -> str:
		if self.__name is not None:
			return self.__name

		found = set (re.findall (r"name='([^']*)'", self.__run ("controls")))

		for name in self.controls:
			if name in found:
				self.__name = name
				return name

		raise MixerError ("the card has none of the controls %s"
		                  % ", ".join (self.controls))

	def read (self) -> MixerState:
		name = self.name ()
		try:
			return parse_cget (name, self.__run ("cget", "name=" + name))

		# e.g. another card now (USB), look for the control again
		except MixerError:
			self.__name = None
			raise

	def write (self, values:list):
		self.__run ("-q", "cset", "name=" + self.name (),
		            ",".join (str (value) for value in values))
		return

	# sets the channels of the entries in settings (percent), the
	# others stay; returns the state (after setting it)
	def apply (self, settings:dict) -> MixerState:
		state = self.read ()

		if len (state.values) <= max (CHANNELS.values ()):
			raise MixerError ("%s has %d channel(s), handset and speaker"
			                  " need their own" % (state.name,
			                                       len (state.values)))

		values = list (state.values)
		for key, channel in CHANNELS.items ():
			if key in settings:
				values[channel] = to_step (state, settings[key])

		if values != state.values:
			self.write (values)
			state = state._replace (values=values)

		return state


# the settings file: {"handset": 80, "speaker": 100, "ring": 70}, all
# entries optional; returns (settings, problems): only valid entries,
# values out of range are limited to 0 to 100, problems are texts
# (English, for the journal); a missing file is no problem
def read_settings (path:str=VOLUME_FILE) -> (dict, list):
	settings = dict ()
	problems = list ()

	try:
		with open (path, "rb") as f:
			data = json.loads (f.read (65536).decode ())

	except FileNotFoundError:
		return settings, problems

	except (OSError, ValueError) as error:
		problems.append ("%s can not be read: %s" % (path, error))
		return settings, problems

	if not isinstance (data, dict):
		problems.append ("%s is no JSON object" % path)
		return settings, problems

	for key, value in data.items ():
		if key not in KEYS:
			problems.append ("%s: unknown entry \"%s\" is ignored"
			                 % (path, key))
			continue

		# bool is an int in python
		if isinstance (value, bool) or not isinstance (value, int):
			problems.append ("%s: %s = %r is no whole number, ignored"
			                 % (path, key, value))
			continue

		if not 0 <= value <= 100:
			problems.append ("%s: %s = %d is not within 0 to 100, %d is"
			                 " used" % (path, key, value,
			                            max (0, min (100, value))))
			value = max (0, min (100, value))

		settings[key] = value

	return settings, problems


# written to a temporary file in the same directory, which replaces
# the old one (a power loss leaves the old or the new file, both
# complete), like records.list
def write_settings (settings:dict, path:str=VOLUME_FILE):
	data = json.dumps ({key: settings[key] for key in KEYS if key in settings},
	                   indent=1) + "\n"

	directory = os.path.dirname (os.path.abspath (path))
	fd, temporary = tempfile.mkstemp (dir=directory,
	                                  prefix="." + os.path.basename (path) + ".",
	                                  suffix=".tmp")
	try:
		with os.fdopen (fd, "w") as f:
			f.write (data)
			f.flush ()
			os.fsync (f.fileno ())

		os.replace (temporary, path)

	except BaseException:
		try:
			os.unlink (temporary)
		except OSError:
			pass
		raise

	# the new name survives a power loss
	fd = os.open (directory, os.O_RDONLY | os.O_DIRECTORY)
	try:
		os.fsync (fd)
	finally:
		os.close (fd)

	return


# the main process' view of the settings file: update () reads it again
# when it was replaced or changed (one stat () per call otherwise)
class VolumeSettings ():
	def __init__ (self, path:str=VOLUME_FILE, mixer:Mixer=None):
		self.path = path
		self.mixer = mixer or Mixer ()
		self.settings = dict ()
		# the first update () always reads the file
		self.__key = object ()
		self.__loaded = False
		return

	@property
	def ring (self) -> int:
		return self.settings.get ("ring", RING_VOLUME)

	def __stat_key (self):
		try:
			stat = os.stat (self.path)
		except OSError:
			return None

		return (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size)

	# returns the changed entries {key: new value or None (removed)},
	# None if nothing changed; sets the mixer if handset or speaker
	# changed (or always, if apply), errors are only logged; a change
	# is logged in the history as a webapp action (not the first read)
	def update (self, apply:bool=False):
		stat_key = self.__stat_key ()
		if stat_key == self.__key and not apply:
			return None

		self.__key = stat_key
		settings, problems = read_settings (self.path)
		for problem in problems:
			log.warning ("%s", problem)

		changed = {key: settings.get (key) for key in KEYS
		           if settings.get (key) != self.settings.get (key)}
		self.settings = settings

		if changed and self.__loaded:
			log.info ("volume settings changed: %r", changed)
			history.add ("webapp", action="volume", **changed)
		self.__loaded = True

		if apply or any (key in CHANNELS for key in changed):
			mixer_settings = {key: value for key, value in settings.items ()
			                  if key in CHANNELS}
			if mixer_settings:
				try:
					state = self.mixer.apply (mixer_settings)
					log.info ("mixer %s: %s", state.name,
					          ",".join (str (v) for v in state.values))

				except MixerError as error:
					log.error ("setting the volume failed: %s", error)

		return changed or None
