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

from .CONSTANTS import MOAN_PROPABILITY

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

def off_hook_loop (records, player, PickUp, dial, ButtonLeft, ButtonMiddle, tts, led):

	maxRecordingTime = 1200     #in 0.1 sek
	minRecordingTime = 20

	def dial_number_abort ():
		return ButtonLeft.is_pressed or not PickUp.is_pressed

	def dial_digit_abort ():
		return not PickUp.is_pressed


	player.start_dial_tone ()

	while PickUp.is_pressed:
		# dialing
		if dial.is_used ():
			player.stop_tone ()

			dialedNumber = dial.get_number (dial_number_abort, led, player)
			if player.play_recording (dialedNumber):
				# still off-hook
				player.play_busy_tone ()
			break

		# recording
		if ButtonLeft.is_pressed:
			player.stop_tone ()

			record = records.add_next ()
			tts.say("Aufnahme Nr.: " + str(record.number) + " wird gestartet")

			aborted = False
			recordingTime = 0
			with Recorder (record.filename, led) as recorder:

				while recordingTime <= maxRecordingTime \
				and PickUp.is_pressed \
				and not ButtonLeft.is_released \
				and not aborted:
					time.sleep (0.1)
					recordingTime += 1

					if ButtonMiddle.is_released:
						aborted = True

				if recordingTime > minRecordingTime and not aborted:
					recorder.save ()
					records.sync_fs ()

			if recordingTime > maxRecordingTime:
				tts.say("Aufnahme Nr.: " + str(record.number) + "wegen overtime beendet.")
			elif aborted:
				tts.say("Aufnahme Nr.: " + str(record.number) + " abgebrochen")
			elif recordingTime <= minRecordingTime:
				tts.say ("Aufnahme zu kurz")
			else:
				print ("Aufnahme Nr.: " + str(record.number) + " beendet.")

			player.play_busy_tone ()
			break

		# open Menu
		if ButtonMiddle.is_pressed:
			player.stop_tone ()

			tts.say("Menü wird geöffnet.")
			dialedOption = dial.get_digit (dial_digit_abort, led, player)
			# aborted
			if dialedOption is None:
				pass
			if dialedOption == 0:
				tts.say_time ()
			elif dialedOption == 1:
				if not player.random_prayer ():
					# hang up
					break
			elif dialedOption == 2:
				if not player.random_dice_prayer ():
					# hang up
					break
			elif dialedOption == 3:
				if not player.random_pater ():
					# hang up
					break
			else:
				tts.say("Das habe ich nicht verstanden. Auf wiederhören")

			player.play_busy_tone ()
			break
	else:
		player.stop_tone ()

	# moan
	if random.random () < MOAN_PROPABILITY:
		tts.say ("Ahhhhh!")

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
	player = Player (PickUp, tts, speakerThread)

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

	player.quit ()

	return 0


if __name__ == '__main__':
	main ()
