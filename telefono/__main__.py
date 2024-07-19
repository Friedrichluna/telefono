#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import random
import socket
import subprocess
import sys
import time

import gpiozero

from . import *

from .CONSTANTS import RECORD_DIR
from .CONSTANTS import RECORD_PREFIX
from .CONSTANTS import RECORD_SUFFIX

from .CONSTANTS import STARTUP_FILE
from .CONSTANTS import SHUTDOWN_FILE

from .CONSTANTS import WEBAPP_EXEC

from .ipc import IPC_Server
from .player import Player


def turn_off (button):
	time_pressed = 0
	while button.is_pressed and time_pressed < 10:
		time.sleep (0.5)
		time_pressed += 1

	if time_pressed >= 10:
		return True

	return False

def do_dial_call (hook, ButtonLeft, dial, player, led):
	def abort ():
		return ButtonLeft.is_released or not hook.is_pressed

	number = dial.get_number (abort, led, player)
	if player.play_recording (number):
		# still off-hook
		player.play_busy_tone ()
	return

def do_recording (hook, ButtonLeft, ButtonMiddle, records, player, tts, led):

	def end ():
		return ButtonLeft.is_released or not hook.is_pressed

	def abort ():
		return ButtonMiddle.is_released

	record = records.add_next ()
	tts.say("Aufnahme Nr.: " + str(record.number) + " wird gestartet")

	result = Recorder (record.filename,
	                   records, led).record (end, abort)

	if RECORDER_RESULT.ABORT == result:
		tts.say("Aufnahme Nr.: " + str(record.number) + " abgebrochen")
	elif RECORDER_RESULT.MIN_TIME == result:
		tts.say ("Aufnahme zu kurz")
	elif RECORDER_RESULT.MAX_TIME == result:
		tts.say("Aufnahme Nr.: " + str(record.number) + "wegen overtime beendet.")
	else:
		print ("Aufnahme Nr.: " + str(record.number) + " beendet.")

	player.play_busy_tone ()
	return

def do_menu (hook, dial, player, tts, led):

	def abort ():
		return not hook.is_pressed

	tts.say("Menü wird geöffnet.")
	option = dial.get_digit (abort, led, player)
	# aborted
	if option is None:
		pass
	elif option == 0:
		tts.say_time ()
	elif option == 1:
		if not player.random_prayer ():
			# hang up
			return
	elif option == 2:
		if not player.random_dice_prayer ():
			# hang up
			return
	elif option == 3:
		if not player.random_pater ():
			# hang up
			return
	else:
		tts.say("Das habe ich nicht verstanden. Auf wiederhören")

	player.play_busy_tone ()
	return

def off_hook_loop (records, player, hook, dial, ButtonLeft, ButtonMiddle, tts, led):

	player.start_dial_tone ()

	while hook.is_pressed:

		if dial.is_used ():
			player.stop_tone ()
			return do_dial_call (hook, ButtonLeft,
			                     dial, player, led)

		if ButtonLeft.is_pressed:
			player.stop_tone ()
			return do_recording (hook,
			                     ButtonLeft, ButtonMiddle,
			                     records, player, tts, led)

		if ButtonMiddle.is_pressed:
			player.stop_tone ()
			return do_menu (hook, dial, player, tts, led)

	player.stop_tone ()
	return

def run_webapp (fd):
	return subprocess.Popen ([*WEBAPP_EXEC, str (fd)],
	                         pass_fds=(fd, ))

def main ():
	# initialize random module
	random.seed ()

	ipc = IPC_Server ()

	# initialize recording data
	records = Records ()
	records.sync_fs ()

	DialCounter = Button(2) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(26) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	PickUp = Button(18) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(3) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(27) #Mittlerer Knopf
	SpeakerSwich = Button(17) #Rechter Kippschalter (grüner Anschluss)
	led = gpiozero.LED (20)

	dial = Dial (DialInUse, DialCounter)

	speakerThread = SpeakerThread (SpeakerSwich)
	speakerThread.start()

	tts = TTS ()
	player = Player (PickUp, ButtonLeft, ButtonMiddle, tts, speakerThread)

	# initialize call queue
	queue = EventQueue (records)

	def dinner_weekday (_datetime:datetime.datetime):
		weekday = _datetime.isoweekday () % 7
		return (1 < weekday < 5)

	def every_weekday (_datetime:datetime.datetime):
		return True

	queue.add_shout (1830, dinner_weekday, datetime.time (18, 30))
	queue.add_shout (1930, dinner_weekday, datetime.time (19, 30))
	queue.add_shout (2014, every_weekday, datetime.time (20, 00))

	# start webapp
	webAppProcess = run_webapp (ipc.get_client_fd ())

	player.play_aloud (STARTUP_FILE)

	while not turn_off (ButtonMiddle):

		if PickUp.is_pressed:
			off_hook_loop (records, player, PickUp, dial,
			               ButtonLeft, ButtonMiddle,
			               tts, led)

		ipc.handle_message (queue, records)

		queue.process (tts, player)

		time.sleep (0.5)

	player.play_aloud (SHUTDOWN_FILE)

	webAppProcess.terminate ()
	speakerThread.join ()

	DialCounter.close ()
	DialInUse.close ()
	PickUp.close ()
	ButtonLeft.close ()
	ButtonMiddle.close ()
	SpeakerSwich.close ()
	led.close ()

	return 0


if __name__ == '__main__':
	main ()
