#!/usr/bin/python3
# -*- coding: utf-8 -*-

# hardware test (the webapp's page /diagnose): the GPIO levels are read
# straight from the GPIO registers of the BCM283x/BCM2711 (read-only
# mapping of /dev/gpiomem), so nothing is claimed (the main process owns
# the lines through lgpio), no pin mode or pull is changed, and it
# works while the phone is in use (the main process does not answer
# the webapp then)

import collections
import mmap
import os
import threading
import time

from .CONSTANTS import DIAGNOSE_GPIO_MEM
from .CONSTANTS import DIAGNOSE_COMPATIBLE_FILE
from .CONSTANTS import DIAGNOSE_SAMPLE_DELAY
from .CONSTANTS import DIAGNOSE_SAMPLE_IDLE

from .config import LED_PIN
from .config import PINS
from .config import SPEAKER_RELAY_PIN


# boards with the BCM2835 GPIO block (Pi 1 to 4, Zero, Zero 2), the
# Pi 5 (RP1) has other registers
SUPPORTED_SOCS = (b"brcm,bcm2835", b"brcm,bcm2836", b"brcm,bcm2837",
                  b"brcm,bcm2711")

GPIO_MAP_SIZE = 4096
# GPFSEL0..2: 3 bits per pin (0 input, 1 output, else alternative
# function), GPLEV0: one bit per pin (GPIO 0-31)
GPFSEL0 = 0x00
GPLEV0 = 0x34

FUNCTION_INPUT = 0
FUNCTION_OUTPUT = 1


# shown on the page, German
class GpioError (Exception):
	pass


# one reading of the GPIO registers
Snapshot = collections.namedtuple ("Snapshot", ("levels", "functions"))


class GpioRegisters:
	def __init__ (self, path:str=DIAGNOSE_GPIO_MEM,
	              compatible:str=DIAGNOSE_COMPATIBLE_FILE):
		self.__path = path
		self.__compatible = compatible
		self.__lock = threading.Lock ()
		self.__registers = None
		return

	def __check_board (self):
		try:
			with open (self.__compatible, "rb") as f:
				names = f.read ().split (b"\0")
		except OSError as error:
			raise GpioError ("Board unbekannt (%s nicht lesbar: %s)."
			                 % (self.__compatible, error.strerror))

		if not any (soc in names for soc in SUPPORTED_SOCS):
			model = b", ".join (n for n in names if n).decode (errors="replace")
			raise GpioError ("Dieses Board (%s) wird nicht unterstützt, "
			                 "nur Raspberry Pi 1 bis 4 und Zero." % model)
		return

	# mapped on the first use (and again after a failure), read-only
	def __open (self):
		self.__check_board ()

		try:
			fd = os.open (self.__path,
			              os.O_RDONLY | os.O_SYNC | os.O_CLOEXEC)
		except OSError as error:
			raise GpioError ("%s kann nicht geöffnet werden: %s "
			                 "(der Benutzer muss in der Gruppe gpio sein)."
			                 % (self.__path, error.strerror))

		try:
			memory = mmap.mmap (fd, GPIO_MAP_SIZE, mmap.MAP_SHARED,
			                    mmap.PROT_READ)
		except (OSError, ValueError) as error:
			raise GpioError ("%s kann nicht gelesen werden: %s."
			                 % (self.__path, error))
		finally:
			os.close (fd)

		# 32 bit words: each register is read with one load
		return memoryview (memory).cast ("I")

	def __get (self):
		with self.__lock:
			if self.__registers is None:
				self.__registers = self.__open ()

			return self.__registers

	# GPLEV0, bit n = level of GPIO n
	def levels (self) -> int:
		return self.__get ()[GPLEV0 // 4]

	def read (self, pins) -> Snapshot:
		registers = self.__get ()

		functions = dict ()
		for pin in pins:
			word = registers[GPFSEL0 // 4 + pin // 10]
			functions[pin] = (word >> (3 * (pin % 10))) & 7

		return Snapshot (registers[GPLEV0 // 4], functions)


def level (levels:int, pin:int) -> int:
	return (levels >> pin) & 1

# all inputs have a pull-up: a closed contact is low, which is
# "pressed" for telefono (gpiozero.Button), unless it is inverted
def is_pressed (levels:int, pin:int, inverted:bool) -> bool:
	return (0 == level (levels, pin)) != inverted


# name: shown on the page
# pressed, released: what telefono makes of it
# rest: whether it is pressed at rest (nobody touches the phone),
#       None if there is no rest position (the loudspeaker switch)
# condition: "if <condition>, the setting is wrong"
Input = collections.namedtuple ("Input", ("key", "name", "pressed",
                                          "released", "rest",
                                          "condition"))

INPUTS = (
	Input ("hook", "Hörer", "abgehoben", "aufgelegt", False,
	       "der Hörer aufliegt"),
	Input ("left", "Linker Knopf", "gedrückt", "losgelassen", False,
	       "der Knopf nicht gedrückt ist"),
	Input ("middle", "Mittlerer Knopf", "gedrückt", "losgelassen", False,
	       "der Knopf nicht gedrückt ist"),
	Input ("dial_in_use", "Wählscheibe gedreht", "gedreht", "nicht gedreht",
	       False, "die Wählscheibe nicht gedreht ist"),
	# src/dial.py counts the "released" times while the dial
	# runs back, the contact is closed at rest and between pulses
	Input ("dial_counter", "Wählscheibe Impulse", "kein Impuls",
	       "Impuls", True, "die Wählscheibe nicht gedreht ist"),
	Input ("speaker_switch", "Lautsprecherschalter", "laut", "leise",
	       None, None),
)


# the state of each input; config: config.ConfigResult
def evaluate_inputs (snapshot:Snapshot, config) -> list:
	inputs = list ()

	for spec in INPUTS:
		pin = PINS[spec.key]
		inverted = config.inverted[spec.key]
		pressed = is_pressed (snapshot.levels, pin, inverted)

		item = {
			"key": spec.key,
			"pin": pin,
			"level": "high" if level (snapshot.levels, pin) else "low",
			"inverted": inverted,
			"pressed": pressed,
			"state": spec.pressed if pressed else spec.released,
			"at_rest": None,
			"fix": None,
			"is_input": FUNCTION_INPUT == snapshot.functions.get (pin),
		}

		if spec.rest is not None:
			item["at_rest"] = (pressed == spec.rest)

			# what to set if this reading is the rest position
			if not item["at_rest"]:
				item["fix"] = "%s = %s" % (spec.key,
				                           "no" if inverted else "yes")

		inputs.append (item)

	return inputs


Output = collections.namedtuple ("Output", ("key", "name", "pin",
                                            "active_high"))

OUTPUTS = (
	Output ("led", "LED", LED_PIN, True),
	Output ("speaker", "Lautsprecher-Relais", SPEAKER_RELAY_PIN, False),
)

def evaluate_outputs (snapshot:Snapshot) -> list:
	outputs = list ()

	for spec in OUTPUTS:
		high = bool (level (snapshot.levels, spec.pin))
		outputs.append ({
			"key": spec.key,
			"pin": spec.pin,
			"level": "high" if high else "low",
			"on": high == spec.active_high,
			"is_output": FUNCTION_OUTPUT == snapshot.functions.get (spec.pin),
		})

	return outputs


def all_pins () -> list:
	return [*PINS.values (), *(spec.pin for spec in OUTPUTS)]


# the dial pulses (10 per second, 60 ms long) are too fast for the
# page's updates: while the page is open (polled), a thread samples the
# inputs every DIAGNOSE_SAMPLE_DELAY, counts the changes and decodes
# the digits like src/dial.py; it ends DIAGNOSE_SAMPLE_IDLE after the
# last poll, so a closed or hidden page costs nothing
class Sampler:
	def __init__ (self, registers:GpioRegisters,
	              delay:float=DIAGNOSE_SAMPLE_DELAY,
	              idle:float=DIAGNOSE_SAMPLE_IDLE,
	              clock=time.monotonic):
		self.__registers = registers
		self.__delay = delay
		self.__idle = idle
		self.__clock = clock

		self.__lock = threading.Lock ()
		self.__thread = None
		self.__last_poll = 0
		self.__inverted = dict.fromkeys (PINS, False)
		self.__reset ()
		return

	def __reset (self):
		self.__previous = None
		self.__changes = dict.fromkeys (PINS, 0)
		self.__last_change = dict.fromkeys (PINS, None)
		self.__dialing = False
		self.__pulses = 0
		self.__last_pulses = None
		self.__digits = 0
		return

	# called by each update of the page: (re)starts the sampling and
	# returns what was seen since it started
	def poll (self, inverted:dict) -> dict:
		with self.__lock:
			now = self.__clock ()
			self.__last_poll = now
			self.__inverted = dict (inverted)

			if self.__thread is None:
				self.__reset ()
				self.__thread = threading.Thread (target=self.__run,
				                                  name="diagnose",
				                                  daemon=True)
				self.__thread.start ()

			return self.__summary (now)

	def __summary (self, now:float) -> dict:
		changes = dict ()
		for key in PINS:
			last = self.__last_change[key]
			changes[key] = {
				"count": self.__changes[key],
				"ago": None if last is None else round (now - last, 1),
			}

		return {
			"changes": changes,
			"dialing": self.__dialing,
			"pulses": self.__pulses,
			"last_pulses": self.__last_pulses,
			"last_digit": dial_digit (self.__last_pulses),
			"digits": self.__digits,
		}

	def __run (self):
		while True:
			with self.__lock:
				if self.__clock () - self.__last_poll > self.__idle:
					self.__thread = None
					return

				inverted = self.__inverted

			try:
				levels = self.__registers.levels ()
			except GpioError:
				# the page shows the error of its own reading
				with self.__lock:
					self.__thread = None
				return

			with self.__lock:
				self.sample (levels, inverted, self.__clock ())

			time.sleep (self.__delay)

	# one sample (lock held, or no thread: the tests)
	def sample (self, levels:int, inverted:dict, now:float):
		previous = self.__previous
		self.__previous = levels

		if previous is not None:
			changed = previous ^ levels
			for key, pin in PINS.items ():
				if level (changed, pin):
					self.__changes[key] += 1
					self.__last_change[key] = now

		dialing = is_pressed (levels, PINS["dial_in_use"],
		                      inverted["dial_in_use"])
		counter = is_pressed (levels, PINS["dial_counter"],
		                      inverted["dial_counter"])

		if dialing and not self.__dialing:
			# like src/dial.py: "released" counts as soon as
			# the dial is turned
			self.__pulses = 0 if counter else 1

		elif dialing and previous is not None:
			was = is_pressed (previous, PINS["dial_counter"],
			                  inverted["dial_counter"])
			if was and not counter:
				self.__pulses += 1

		elif not dialing and self.__dialing:
			self.__last_pulses = self.__pulses
			self.__digits += 1
			self.__pulses = 0

		self.__dialing = dialing
		return


# the digit src/dial.py makes of the pulses, None if nothing was dialed
def dial_digit (pulses):
	if not pulses:
		return None

	if pulses > 9:
		return 0

	return pulses
