#!/usr/bin/python3
# -*- coding: utf-8 -*-

import configparser
import logging

from .CONSTANTS import CONFIG_FILE


log = logging.getLogger ("Config")


# the inputs of the [inverted] section in CONFIG_FILE
INPUTS = ("hook", "left", "middle",
          "dial_counter", "dial_in_use", "speaker_switch")


# which inputs of this phone are inverted, as {input: bool}; a missing
# file, section or entry and invalid values mean not inverted (the
# original wiring), so a broken file never stops the phone
def read_inverted (path:str=CONFIG_FILE) -> dict:
	inverted = dict.fromkeys (INPUTS, False)

	config = configparser.ConfigParser ()
	try:
		# an unreadable file is skipped like a missing one
		found = config.read (path, encoding="utf-8")
	except (configparser.Error, UnicodeDecodeError) as e:
		log.error ("%s is invalid, no input is inverted: %s", path, e)
		return inverted

	if not found:
		log.info ("%s not found or not readable, no input is inverted",
		          path)
		return inverted

	for section in config.sections ():
		if "inverted" != section:
			log.warning ("%s: unknown section [%s] is ignored",
			             path, section)

	if config.has_section ("inverted"):
		for key in config["inverted"]:
			if key not in inverted:
				log.warning ("%s: unknown input \"%s\" is ignored"
				             " (known: %s)",
				             path, key, ", ".join (INPUTS))
				continue

			try:
				inverted[key] = config.getboolean ("inverted", key)
			except ValueError:
				log.error ("%s: \"%s = %s\" is neither yes nor no,"
				           " %s is not inverted",
				           path, key, config["inverted"][key], key)

	log.info ("inverted inputs (%s): %s", path,
	          ", ".join (k for k in INPUTS if inverted[k]) or "none")
	return inverted
