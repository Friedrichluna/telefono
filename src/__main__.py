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

from .CONSTANTS import MAINLOOP_DELAY
from .CONSTANTS import MENU_DELAY
from .CONSTANTS import OFF_HOOK_DELAY
from .CONSTANTS import SHUTDOWN_BUTTON_DELAY

from .audio import convert_legacy_recordings
from .config import read_inverted
from .ipc import IPC_Server
from .player import Player


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

	def abort ():
		return ButtonLeft.is_released or not off_hook ()

	number = dial.get_number (abort, led, player)
	if not number:
		# started dialling, but didn't dial anything
		return player.play_busy_tone ()

	if network[number].outbound_call (player):
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

	result = Recorder (subscriber, led).record (end, abort)

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
	# aborted
	if option is None:
		log.info ("aborted menu selection")
		pass
	elif option == 0:
		log.info ("menu: selected 0")
		if not network["0"].outbound_call (player):
			# hang up
			return
	elif option == 1:
		log.info ("menu: selected 1")
		if not network["100"].outbound_call (player):
			# hang up
			return
	elif option == 2:
		log.info ("menu: selected 2")
		if not network["200"].outbound_call (player):
			# hang up
			return
	elif option == 3:
		log.info ("menu: selected 3")
		if not network["300"].outbound_call (player):
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

	# the wiring differs between the phones, see telefono.conf
	inverted = read_inverted ()

	DialCounter = Button(2, inverted=inverted["dial_counter"]) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(26, inverted=inverted["dial_in_use"]) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	Hook = Button(18, inverted=inverted["hook"]) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(3, inverted=inverted["left"]) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(27, inverted=inverted["middle"]) #Mittlerer Knopf
	SpeakerSwitch = Button(17, inverted=inverted["speaker_switch"]) #Rechter Kippschalter (grüner Anschluss)
	led = gpiozero.LED (20)

	dial = Dial (DialInUse, DialCounter)

	speakerThread = SpeakerThread (SpeakerSwitch)
	speakerThread.start()

	player = Player (Hook, ButtonLeft, ButtonMiddle, speakerThread)

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

	signal.signal (signal.SIGINT, signal_handler)
	signal.signal (signal.SIGTERM, signal_handler)

	player.play_system_sound (STARTUP_FILE)

	def off_hook ():
		return Hook.is_pressed

	log.info ("startup finished")
	while running and not turn_off (ButtonMiddle, log):

		if off_hook ():
			off_hook_loop (network, player, off_hook, dial,
			               ButtonLeft, ButtonMiddle, led,
			               log)
			log.debug ("leaving off-hook loop")

		ipc.handle_message (queue, network)

		queue.process (player)

		ipc.wait (MAINLOOP_DELAY)

	log.info ("shutting down")
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
