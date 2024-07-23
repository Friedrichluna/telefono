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
from .CONSTANTS import LOG_FORMAT

from .CONSTANTS import STARTUP_FILE
from .CONSTANTS import SHUTDOWN_FILE

from .CONSTANTS import WEBAPP_EXEC

from .CONSTANTS import MAINLOOP_DELAY
from .CONSTANTS import SHUTDOWN_BUTTON_DELAY

from .ipc import IPC_Server
from .player import Player
from .records import Subscriber


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

def do_dial_call (off_hook, ButtonLeft, dial, records, player, led, log):
	log.debug ("start dialing")

	def abort ():
		return ButtonLeft.is_released or not off_hook ()

	number = dial.get_number (abort, led, player)
	if None is number or player.play_recording (records[number]):
		# still off-hook
		player.play_busy_tone ()
	return

def do_recording (off_hook, ButtonLeft, ButtonMiddle, records, player, led, log):

	def end ():
		return ButtonLeft.is_released or not off_hook ()

	def abort ():
		return ButtonMiddle.is_released

	record = records.find_assignable ()

	log.info ("start recording %s", record.number)
	if not player.say ("Aufnahme Nr.: %s wird gestartet"
	                   % record.number):
		# hang up
		return

	result = Recorder (record.filename,
	                   records, led).record (end, abort)

	if RECORDER_RESULT.ABORT == result:
		log.info ("recording %s aborted", record.number)
		player.say ("Aufnahme Nr.: %s abgebrochen" % record.number,
		            interruptible=False)

	elif RECORDER_RESULT.MIN_TIME == result:
		log.info ("recording %s to short", record.number)
		player.say ("Aufnahme zu kurz", interruptible=False)

	elif RECORDER_RESULT.MAX_TIME == result:
		log.info ("recording %s terminated after max. time",
		              record.number)
		player.say ("Aufnahme Nr.: %s wegen overtime beendet."
		            % record.number, interruptible=False)
	else:
		log.info ("finished recording %s", record.number)

	player.play_busy_tone ()
	return

def do_menu (off_hook, dial, records, player, led, log):
	log.debug ("opening menu")

	def abort ():
		return not off_hook ()

	if not player.say ("Menü wird geöffnet."):
		# hang up
		return

	player.start_secondary_dial_tone ()

	while not dial.is_used ():
		pass

	player.stop_tone ()
	option = dial.get_digit (abort, led, player)
	# aborted
	if option is None:
		log.info ("aborted menu selection")
		pass
	elif option == 0:
		log.info ("menu: selected 0")
		if not player.say_time ():
			# hang up
			return
	elif option == 1:
		log.info ("menu: selected 1")
		if not player.random_prayer (records):
			# hang up
			return
	elif option == 2:
		log.info ("menu: selected 2")
		if not player.random_dice_prayer (records):
			# hang up
			return
	elif option == 3:
		log.info ("menu: selected 3")
		if not player.random_pater (records):
			# hang up
			return
	else:
		log.info ("error in menu selection")
		player.say ("Das habe ich nicht verstanden. Auf Wiederhörn!",
		            interruptible=False)

	player.play_busy_tone ()
	return

def off_hook_loop (records, player, off_hook, dial, ButtonLeft, ButtonMiddle, led, log):
	log.debug ("entering off-hook loop")

	player.start_dial_tone ()

	global running
	while running and off_hook ():

		if dial.is_used ():
			player.stop_tone ()
			return do_dial_call (off_hook, ButtonLeft,
			                     dial, records, player, led,
			                     log)

		if ButtonLeft.is_pressed:
			player.stop_tone ()
			return do_recording (off_hook,
			                     ButtonLeft, ButtonMiddle,
			                     records, player, led, log)

		if ButtonMiddle.is_pressed:
			player.stop_tone ()
			return do_menu (off_hook, dial, records, player,
			                led, log)

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
	log.info ("started telefono")

	# initialize random module
	random.seed ()

	ipc = IPC_Server ()

	# initialize recording data
	records = Records ()
	records.sync_fs ()

	DialCounter = Button(2) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(26) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	Hook = Button(18) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(3) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(27) #Mittlerer Knopf
	SpeakerSwich = Button(17) #Rechter Kippschalter (grüner Anschluss)
	led = gpiozero.LED (20)

	dial = Dial (DialInUse, DialCounter)

	speakerThread = SpeakerThread (SpeakerSwich)
	speakerThread.start()

	player = Player (Hook, ButtonLeft, ButtonMiddle, speakerThread)

	# initialize call queue
	queue = EventQueue (records)

	def dinner_weekday (_datetime:datetime.datetime):
		weekday = _datetime.isoweekday () % 7
		return (1 < weekday < 5)

	def every_weekday (_datetime:datetime.datetime):
		return True

	queue.add_shout (records[1830], dinner_weekday, datetime.time (18, 30))
	queue.add_shout (records[1930], dinner_weekday, datetime.time (19, 30))
	queue.add_shout (records[2014], every_weekday, datetime.time (20, 00))

	# start webapp
	webAppProcess = run_webapp (ipc.get_client_fd (), log)

	global running
	running = True

	signal.signal (signal.SIGINT, signal_handler)
	signal.signal (signal.SIGTERM, signal_handler)

	player.play_aloud (STARTUP_FILE)

	def off_hook ():
		return Hook.is_pressed

	log.info ("startup finished")
	while running and not turn_off (ButtonMiddle, log):

		if off_hook ():
			off_hook_loop (records, player, off_hook, dial,
			               ButtonLeft, ButtonMiddle, led,
			               log)
			log.debug ("leaving off-hook loop")

		ipc.handle_message (queue, records)

		queue.process (player)

		time.sleep (MAINLOOP_DELAY)

	log.info ("shutting down")
	player.play_aloud (SHUTDOWN_FILE)

	webAppProcess.terminate ()
	speakerThread.join ()

	DialCounter.close ()
	DialInUse.close ()
	Hook.close ()
	ButtonLeft.close ()
	ButtonMiddle.close ()
	SpeakerSwich.close ()
	led.close ()

	log.info ("bye.")
	return 0


if __name__ == '__main__':
	main ()
