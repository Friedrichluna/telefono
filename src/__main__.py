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

from .CONSTANTS import STARTUP_FILE
from .CONSTANTS import SHUTDOWN_FILE

from .CONSTANTS import WEBAPP_EXEC

from .CONSTANTS import MAINLOOP_DELAY
from .CONSTANTS import SHUTDOWN_BUTTON_DELAY

from .ipc import IPC_Server
from .player import Player


def turn_off (button):
	if not button.is_pressed:
		return False

	time_pressed = 0
	while button.is_pressed and time_pressed < 10:
		if 0 == time_pressed:
			logging.debug ("started shutdown press")

		time.sleep (SHUTDOWN_BUTTON_DELAY)
		time_pressed += 1

	if time_pressed >= 10:
		logging.debug ("shutdown press")
		return True

	logging.debug ("released shutdown press prematurely")
	return False

def do_dial_call (off_hook, ButtonLeft, dial, player, led):
	logging.debug ("start dialing")

	def abort ():
		return ButtonLeft.is_released or not off_hook ()

	number = dial.get_number (abort, led, player)
	if None is number or player.play_recording (number):
		# still off-hook
		player.play_busy_tone ()
	return

def do_recording (off_hook, ButtonLeft, ButtonMiddle, records, player, led):

	def end ():
		return ButtonLeft.is_released or not off_hook ()

	def abort ():
		return ButtonMiddle.is_released

	record = records.add_next ()

	logging.info ("start recording %d", record.number)
	if not player.say ("Aufnahme Nr.: %d wird gestartet"
	                   % record.number):
		# hang up
		return

	result = Recorder (record.filename,
	                   records, led).record (end, abort)

	if RECORDER_RESULT.ABORT == result:
		logging.info ("recording %d aborted", record.number)
		player.say ("Aufnahme Nr.: %d abgebrochen" % record.number,
		            interruptible=False)

	elif RECORDER_RESULT.MIN_TIME == result:
		logging.info ("recording %d to short", record.number)
		player.say ("Aufnahme zu kurz", interruptible=False)

	elif RECORDER_RESULT.MAX_TIME == result:
		logging.info ("recording %d terminated after max. time",
		              record.number)
		player.say ("Aufnahme Nr.: %d wegen overtime beendet."
		            % record.number, interruptible=False)
	else:
		logging.info ("finished recording %d", record.number)

	player.play_busy_tone ()
	return

def do_menu (off_hook, dial, player, led):
	logging.debug ("opening menu")

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
		logging.info ("aborted menu selection")
		pass
	elif option == 0:
		logging.info ("menu: selected 0")
		if not player.say_time ():
			# hang up
			return
	elif option == 1:
		logging.info ("menu: selected 1")
		if not player.random_prayer ():
			# hang up
			return
	elif option == 2:
		logging.info ("menu: selected 2")
		if not player.random_dice_prayer ():
			# hang up
			return
	elif option == 3:
		logging.info ("menu: selected 3")
		if not player.random_pater ():
			# hang up
			return
	else:
		logging.info ("error in menu selection")
		player.say ("Das habe ich nicht verstanden. Auf Wiederhörn!",
		            interruptible=False)

	player.play_busy_tone ()
	return

def off_hook_loop (records, player, off_hook, dial, ButtonLeft, ButtonMiddle, led):
	logging.debug ("entering off-hook loop")

	player.start_dial_tone ()

	global running
	while running and off_hook ():

		if dial.is_used ():
			player.stop_tone ()
			return do_dial_call (off_hook, ButtonLeft,
			                     dial, player, led)

		if ButtonLeft.is_pressed:
			player.stop_tone ()
			return do_recording (off_hook,
			                     ButtonLeft, ButtonMiddle,
			                     records, player, led)

		if ButtonMiddle.is_pressed:
			player.stop_tone ()
			return do_menu (off_hook, dial, player, led)

	player.stop_tone ()
	return

def run_webapp (fd):
	logging.info ("starting webapp")

	command = ([*WEBAPP_EXEC, str (fd)])
	logging.debug ("webapp invocation: %s", repr (command))

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

	logging.basicConfig (level=log_level)
	logging.info ("started telefono")

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

	queue.add_shout (1830, dinner_weekday, datetime.time (18, 30))
	queue.add_shout (1930, dinner_weekday, datetime.time (19, 30))
	queue.add_shout (2014, every_weekday, datetime.time (20, 00))

	# start webapp
	webAppProcess = run_webapp (ipc.get_client_fd ())

	global running
	running = True

	signal.signal (signal.SIGINT, signal_handler)
	signal.signal (signal.SIGTERM, signal_handler)

	player.play_aloud (STARTUP_FILE)

	def off_hook ():
		return Hook.is_pressed

	logging.info ("startup finished")
	while running and not turn_off (ButtonMiddle):

		if off_hook ():
			off_hook_loop (records, player, off_hook, dial,
			               ButtonLeft, ButtonMiddle, led)
			logging.debug ("leaving off-hook loop")

		ipc.handle_message (queue, records)

		queue.process (player)

		time.sleep (MAINLOOP_DELAY)

	logging.info ("shutting down")
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

	logging.info ("bye.")
	return 0


if __name__ == '__main__':
	main ()
