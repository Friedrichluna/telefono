#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import logging
import random
import signal
import subprocess
import time

import gpiozero

from . import *

from .CONSTANTS import DEBUG
from .CONSTANTS import VCS_VERSION
from .CONSTANTS import LOG_FORMAT

from .CONSTANTS import STARTUP_FILE
from .CONSTANTS import SHUTDOWN_FILE

from .CONSTANTS import WEBAPP_EXEC

from .CONSTANTS import DIAL_IMMEDIATE
from .CONSTANTS import MAINLOOP_DELAY
from .CONSTANTS import MENU_DELAY
from .CONSTANTS import OFF_HOOK_DELAY
from .CONSTANTS import SHUTDOWN_BUTTON_DELAY

from .CONSTANTS import DIAGNOSE_LED_BLINKS
from .CONSTANTS import DIAGNOSE_LED_BLINK_TIME

from .CONSTANTS import VOLUME_TEST_HANDSET_TEXT
from .CONSTANTS import VOLUME_TEST_SPEAKER_TEXT

from .audio import convert_legacy_recordings
from .config import LED_PIN
from .config import PINS
from .config import read_inverted
from .dial import DIAL_END
from .history import history
from .ipc import IPC_OUTPUT
from .ipc import IPC_Server
from .player import Player
from .volume import VolumeSettings


def turn_off (button, log):
	if not button.is_pressed:
		return False

	time_pressed = 0
	while button.is_pressed and time_pressed < 10:
		if 0 == time_pressed:
			log.debug ("started shutdown press")

		time.sleep (SHUTDOWN_BUTTON_DELAY)
		time_pressed += 1

	if time_pressed >= 10:
		log.debug ("shutdown press")
		return True

	log.debug ("released shutdown press prematurely")
	return False

def do_dial_call (off_hook, ButtonLeft, dial, network, player, led, log):
	log.debug ("start dialing")

	# which one aborted dialing (for the history)
	aborted = []

	def abort ():
		if ButtonLeft.is_released:
			aborted.append ("button")
			return True

		if not off_hook ():
			aborted.append ("hangup")
			return True

		return False

	# call a number as soon as it is unique, stop at once when no
	# number starts with the digits (else: left button or timeout)
	numbers = network.callable_numbers if DIAL_IMMEDIATE else None

	number = dial.get_number (abort, led, player, numbers)
	if not number:
		# started dialling, but didn't dial anything
		history.add ("dial_empty")
		return player.play_busy_tone ()

	if DIAL_END.ABORTED == dial.end and aborted:
		dialed = aborted[-1]
	else:
		dialed = dial.end.value

	# a rejected number gets the SIT tone of an unassigned one
	if network[number].outbound_call (player, dialed=dialed):
		# still off-hook
		player.play_busy_tone ()
	return

def do_recording (off_hook, ButtonLeft, ButtonMiddle, network, player, led):

	def end ():
		return ButtonLeft.is_released or not off_hook ()

	def abort ():
		return ButtonMiddle.is_released

	subscriber = network.find_assignable ()

	if not player.notify_recording_start (subscriber.number):
		# hang up
		return

	recorder = Recorder (subscriber, led)
	started = time.monotonic ()
	result = recorder.record (end, abort)

	history.add ("recording", number=subscriber.number,
	             result=result.name.lower (),
	             seconds=round (time.monotonic () - started, 1))

	if not player.notify_recording_end (subscriber.number, result):
		# hang up
		return

	player.play_busy_tone ()
	return

def do_menu (off_hook, dial, network, player, led, log):
	log.debug ("opening menu")

	def abort ():
		return not off_hook ()

	if not player.notify_menu_start ():
		# hang up
		return

	player.start_secondary_dial_tone ()

	while not dial.is_used ():
		if not running or not off_hook ():
			# hang up
			player.stop_tone ()
			return

		time.sleep (MENU_DELAY)

	player.stop_tone ()
	option = dial.get_digit (abort, led, player)
	history.add ("menu", option=option)
	# aborted
	if option is None:
		log.info ("aborted menu selection")
		pass
	elif option == 0:
		log.info ("menu: selected 0")
		if not network["0"].outbound_call (player, "menu"):
			# hang up
			return
	elif option == 1:
		log.info ("menu: selected 1")
		if not network["100"].outbound_call (player, "menu"):
			# hang up
			return
	elif option == 2:
		log.info ("menu: selected 2")
		if not network["200"].outbound_call (player, "menu"):
			# hang up
			return
	elif option == 3:
		log.info ("menu: selected 3")
		if not network["300"].outbound_call (player, "menu"):
			# hang up
			return
	elif option == 4:
		log.info ("menu: selected 4")
		if not network["400"].outbound_call (player, "menu"):
			# hang up
			return
	else:
		log.info ("error in menu selection")
		if not player.notify_menu_error ():
			# hang up
			return

	player.play_busy_tone ()
	return

def off_hook_loop (network, player, off_hook, dial, ButtonLeft, ButtonMiddle, led, log):
	log.debug ("entering off-hook loop")

	player.start_dial_tone ()

	global running
	while running and off_hook ():

		if dial.is_used ():
			player.stop_tone ()
			return do_dial_call (off_hook, ButtonLeft,
			                     dial, network, player, led,
			                     log)

		if ButtonLeft.is_pressed:
			player.stop_tone ()
			return do_recording (off_hook,
			                     ButtonLeft, ButtonMiddle,
			                     network, player, led)

		if ButtonMiddle.is_pressed:
			player.stop_tone ()
			return do_menu (off_hook, dial, network, player,
			                led, log)

		time.sleep (OFF_HOOK_DELAY)

	player.stop_tone ()
	return

def run_webapp (fd, log):
	log.info ("starting webapp")

	command = ([*WEBAPP_EXEC, str (fd)])
	log.debug ("webapp invocation: %s", repr (command))

	return subprocess.Popen (command, pass_fds=(fd, ))

def signal_handler (signo, frame):
	global running
	running = False
	return

def main ():
	if DEBUG:
		log_level = logging.DEBUG
	else:
		log_level = logging.INFO

	logging.basicConfig (level=log_level, format=LOG_FORMAT)

	log = logging.getLogger (__name__)
	log.info ("started telefono (%s)", VCS_VERSION)

	# initialize random module
	random.seed ()

	ipc = IPC_Server ()

	# older versions recorded wav, all recordings are mp3 now
	convert_legacy_recordings ()

	# initialize recording data
	network = Network ()
	network.sync_fs ()
	# say current time
	network["0"].callback = Player.say_time
	# supper prayer songs
	network["100"].list = ["101", "102", "103", "104", "105", "106"]
	# supper prayers
	network["200"].list = ["201", "202", "203", "204", "205", "206"]
	# pater quotes
	network["300"].list = ["2", "10", "11", "19", "22", "26", "30", "88"]
	# say the address of the webapp
	network["400"].callback = Player.say_address

	# the wiring differs between the phones, see telefono.conf
	inverted = read_inverted ()

	DialCounter = Button(PINS["dial_counter"], inverted=inverted["dial_counter"]) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(PINS["dial_in_use"], inverted=inverted["dial_in_use"]) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	Hook = Button(PINS["hook"], inverted=inverted["hook"]) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(PINS["left"], inverted=inverted["left"]) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(PINS["middle"], inverted=inverted["middle"]) #Mittlerer Knopf
	SpeakerSwitch = Button(PINS["speaker_switch"], inverted=inverted["speaker_switch"]) #Rechter Kippschalter (grüner Anschluss)
	led = gpiozero.LED (LED_PIN)

	dial = Dial (DialInUse, DialCounter)

	# the relay of the loudspeaker (its polarity is in telefono.conf too)
	speakerThread = SpeakerThread (SpeakerSwitch,
	                               inverted=inverted["speaker_relay"])
	speakerThread.start()

	player = Player (Hook, ButtonLeft, ButtonMiddle, speakerThread)

	# the volume of handset, loudspeaker and ring (webapp page /volume):
	# set in the card now (before the startup sound), and again when
	# the webapp changed the file (it sets the card itself as well, so
	# that works while the phone is busy), logged in the history
	volume = VolumeSettings ()
	volume.update (apply=True)
	player.ring_volume = volume.ring

	def update_volume ():
		if volume.update ():
			player.ring_volume = volume.ring
		return

	# initialize call queue
	queue = EventQueue (network)

	def dinner_weekday (_datetime:datetime.datetime):
		weekday = _datetime.isoweekday () % 7
		return (1 < weekday < 5)

	def every_weekday (_datetime:datetime.datetime):
		return True

	queue.add_shout (network["1830"], dinner_weekday, datetime.time (18, 30))
	queue.add_shout (network["1930"], dinner_weekday, datetime.time (19, 30))
	queue.add_shout (network["2014"], every_weekday, datetime.time (20, 00))
	queue.add_shout (network["59"], every_weekday, datetime.time (22, 00))

	# start webapp
	webAppProcess = run_webapp (ipc.get_client_fd (), log)

	global running
	running = True

	# a shout plays to the end, unless telefono is stopped
	player.stopping = lambda: not running

	signal.signal (signal.SIGINT, signal_handler)
	signal.signal (signal.SIGTERM, signal_handler)

	player.play_system_sound (STARTUP_FILE)

	def off_hook ():
		return Hook.is_pressed

	# the webapp's hardware test (only when idle, like all requests)
	def test_speaker ():
		# switched on for SPEAKER_POWERON_DELAY
		speakerThread.activate ()
		speakerThread.deactivate ()

	test_outputs = {
		IPC_OUTPUT.LED: lambda: led.blink (on_time=DIAGNOSE_LED_BLINK_TIME,
		                                   off_time=DIAGNOSE_LED_BLINK_TIME,
		                                   n=DIAGNOSE_LED_BLINKS,
		                                   background=True),
		IPC_OUTPUT.SPEAKER: test_speaker,
		IPC_OUTPUT.HANDSET_SOUND: lambda: player.play_test_text (
		                                VOLUME_TEST_HANDSET_TEXT, aloud=False),
		IPC_OUTPUT.SPEAKER_SOUND: lambda: player.play_test_text (
		                                VOLUME_TEST_SPEAKER_TEXT, aloud=True),
		IPC_OUTPUT.RING_SOUND: player.play_ring_test,
	}

	log.info ("startup finished")
	history.add ("start", version=VCS_VERSION)

	while running and not turn_off (ButtonMiddle, log):

		if off_hook ():
			history.add ("off_hook")
			lifted = time.monotonic ()

			off_hook_loop (network, player, off_hook, dial,
			               ButtonLeft, ButtonMiddle, led,
			               log)
			log.debug ("leaving off-hook loop")

			history.add ("on_hook", seconds=round (time.monotonic ()
			                                       - lifted, 1))

		# before a request (e.g. the ring test) or a call rings
		update_volume ()

		ipc.handle_message (queue, network, test_outputs)

		queue.process (player)

		ipc.wait (MAINLOOP_DELAY)

	log.info ("shutting down")
	# SIGTERM (systemctl stop/restart) or the middle button
	history.add ("stop", reason="signal" if not running else "button")

	player.play_system_sound (SHUTDOWN_FILE)

	webAppProcess.terminate ()
	speakerThread.join ()

	DialCounter.close ()
	DialInUse.close ()
	Hook.close ()
	ButtonLeft.close ()
	ButtonMiddle.close ()
	SpeakerSwitch.close ()
	led.close ()

	log.info ("bye.")
	return 0


if __name__ == '__main__':
	main ()
