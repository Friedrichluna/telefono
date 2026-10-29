#!/usr/bin/python3
# -*- coding: utf-8 -*-

import collections
import configparser
import logging

from .CONSTANTS import CONFIG_FILE


log = logging.getLogger ("Config")


# the inputs of the [inverted] section in CONFIG_FILE and their GPIO
# (BCM numbers), all with the pull-up of gpiozero.Button: a closed
# contact reads low, which is "pressed" unless the input is inverted
PINS = {"hook":           18,
        "left":            3,
        "middle":         27,
        "dial_counter":    2,
        "dial_in_use":    26,
        "speaker_switch": 17}

INPUTS = tuple (PINS)

# outputs: the LED (gpiozero, high is on) and the loudspeaker relay
# (src/speaker.py, low is on, high if "speaker_relay" is inverted)
LED_PIN = 20
SPEAKER_RELAY_PIN = 4

# the outputs of the [inverted] section
OUTPUTS = ("speaker_relay", )

# every key of the [inverted] section
KEYS = (*INPUTS, *OUTPUTS)

# [network] (mDNS name and WLAN hotspot) is read by tools/telefono-net.in
SECTIONS = ("inverted", "network")


# what was read from CONFIG_FILE:
# inverted: {key: bool} for all KEYS (inputs and the relay)
# found:    the file was read
# error:    the file can not be parsed (str), nothing is inverted then
# unknown_sections, unknown_inputs: ignored names (lists)
# invalid:  {input: value} that are neither yes nor no (not inverted)
ConfigResult = collections.namedtuple ("ConfigResult",
                                       ("path", "inverted", "found", "error",
                                        "unknown_sections", "unknown_inputs",
                                        "invalid"))


# like read_inverted, but without logging (the webapp's hardware test
# page reads it on every update)
def load_inverted (path:str=CONFIG_FILE) -> ConfigResult:
	inverted = dict.fromkeys (KEYS, False)
	unknown_sections = list ()
	unknown_inputs = list ()
	invalid = dict ()

	config = configparser.ConfigParser ()
	try:
		# an unreadable file is skipped like a missing one
		found = bool (config.read (path, encoding="utf-8"))
	except (configparser.Error, UnicodeDecodeError) as e:
		return ConfigResult (path, inverted, True, str (e),
		                     unknown_sections, unknown_inputs, invalid)

	if not found:
		return ConfigResult (path, inverted, False, None,
		                     unknown_sections, unknown_inputs, invalid)

	for section in config.sections ():
		if section not in SECTIONS:
			unknown_sections.append (section)

	if config.has_section ("inverted"):
		for key in config["inverted"]:
			if key not in inverted:
				unknown_inputs.append (key)
				continue

			try:
				inverted[key] = config.getboolean ("inverted", key)
			except ValueError:
				invalid[key] = config["inverted"][key]

	return ConfigResult (path, inverted, True, None,
	                     unknown_sections, unknown_inputs, invalid)


# which pins of this phone are inverted, as {key: bool} (the inputs and
# the speaker relay); a missing file, section or entry and invalid
# values mean not inverted (the original wiring), so a broken file
# never stops the phone
def read_inverted (path:str=CONFIG_FILE) -> dict:
	result = load_inverted (path)

	if result.error:
		log.error ("%s is invalid, no pin is inverted: %s",
		           path, result.error)
		return result.inverted

	if not result.found:
		log.info ("%s not found or not readable, no pin is inverted",
		          path)
		return result.inverted

	for section in result.unknown_sections:
		log.warning ("%s: unknown section [%s] is ignored",
		             path, section)

	for key in result.unknown_inputs:
		log.warning ("%s: unknown key \"%s\" is ignored"
		             " (known: %s)",
		             path, key, ", ".join (KEYS))

	for key, value in result.invalid.items ():
		log.error ("%s: \"%s = %s\" is neither yes nor no,"
		           " %s is not inverted",
		           path, key, value, key)

	inverted = result.inverted
	log.info ("inverted pins (%s): %s", path,
	          ", ".join (k for k in KEYS if inverted[k]) or "none")
	return inverted
