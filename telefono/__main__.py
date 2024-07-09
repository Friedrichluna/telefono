#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

import gpiozero

from . import *

from .CONSTANTS import RECORD_DIR
from .CONSTANTS import RECORD_PREFIX
from .CONSTANTS import RECORD_SUFFIX

from .CONSTANTS import RING_FILE
from .CONSTANTS import DIAL_TONE_FILE

from .CONSTANTS import WEBAPP_EXEC

from .CONSTANTS import TELEFONO_LOG_FILE


#---------------------------Pygame AudioPlayer------------------------------------
#needs GPIOZero buttons
import pygame
import time

def play_aloud (tts, fileName, speaker, breakButton):
	speaker.activate ()
	time.sleep (2)

	if os.path.exists (fileName):
		pygame.mixer.music.load(fileName)
		pygame.mixer.music.play()
		while pygame.mixer.music.get_busy():
				if breakButton.is_pressed:
					pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")

	speaker.deactivate ()

def start_dial_tone ():
	pygame.mixer.music.load (DIAL_TONE_FILE)
	pygame.mixer.music.play (loops=-1)

def stop_dial_tone ():
	pygame.mixer.music.stop ()

def play_recording (tts, recording, contButton):
	if not contButton.is_pressed:
		return

	if os.path.exists (recording):
		pygame.mixer.music.load(recording)
		pygame.mixer.music.play()

		while pygame.mixer.music.get_busy():
			time.sleep (0.01)
			if not contButton.is_pressed:
				pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")


#--------------------------File Name Generator----------------------------------

def newWavName(wav_number):
	return RECORD_DIR + "/" + RECORD_PREFIX + str(wav_number) + RECORD_SUFFIX


#--------------------------FindNewFile-----------------------------------------
import os

def findNewFileName ():
	counter = 0
	filename = newWavName (counter)
	while os.path.exists (filename):
		counter += 1
		filename = newWavName (counter)
	return filename, counter


#---------------------------Ringing------------------------------------
import time

def ringing (tts, callingFile_, speaker, PickUp):
	play_aloud (tts, RING_FILE, speaker, PickUp) #hört auf wenn PickUp == True
	time.sleep (1) #test
	play_recording (tts, callingFile_, PickUp) #hört auf wenn PickUp == False


#--------------------------CallingRoutine----------------------------
import datetime
import random
import time

MIN_HOUR = 15
MAX_HOUR = 21
SECONDS_PER_DAY = 86400
call_minute = None

def getTimeInt():
	now = datetime.datetime.now()
	current_time = now.strftime("%H%M%S")
	return(int(current_time))

# minutes since midnight
def current_day_minute ():
	# this is only approximately,
	# because the number of seconds per day isn't constant.
	return (time.time () % SECONDS_PER_DAY) // 60

def get_random_call_minute ():
	return random.randint (MIN_HOUR * 60, MAX_HOUR * 60)


def is_call_time ():
	global call_minute
	global schedule_call

	# ring at startup
	if (call_minute is None):
		schedule_call = False
		call_minute = get_random_call_minute ()
		print ("call scheduled for: %02d:%02d Uhr"
		       % (call_minute // 60, call_minute % 60))
		return True

	current_time = current_day_minute ()
	# ring at scheduled time
	if current_time == call_minute and not schedule_call:
		# schedule next call
		schedule_call = True
		return True

	# schedule outside allowed call time -> call only once per day
	current_time //= 60
	if schedule_call and current_time not in range (MIN_HOUR, MAX_HOUR):
		schedule_call = False
		call_minute = get_random_call_minute ()
		print ("call scheduled for: %02d:%02d Uhr"
		       % (call_minute // 60, call_minute % 60))

	return False

IPC_MAX_DATA = 1024
IPC_BYTEORDER = "big"
IPC_INT_SIZE = 4

IPC_CALL = 0
IPC_MESSAGE = 1

def handle_queued_call (connection, tts, speaker, PickUp):
	try:
		data = connection.recv (IPC_MAX_DATA, socket.MSG_DONTWAIT)

	# no queued call
	except BlockingIOError:
		return

	if data[0] == IPC_CALL:
		data = data[1:]
		recording = int.from_bytes (data[:IPC_INT_SIZE],
		                            IPC_BYTEORDER, signed=False)

		recording = newWavName (recording)
		print ("call in queue: %s" % recording)
		ringing (tts, recording, speaker, PickUp)

	if data[0] == IPC_MESSAGE:
		data = data[1:]

		index = data.find (b"\0")

		# silently drop to long or malformed messages
		if index != -1:
			data = data[:index]
			tts.say (data.decode ())



def getWeekDayInt():
	now = datetime.datetime.now()
	return now.weekday()


#---------------------------random old Message-----------------------------------------
import os

def fileNumbers():
	fileNameList = [f for f in os.listdir(RECORD_DIR) if os.path.isfile(os.path.join(RECORD_DIR, f))]
	#print(fileNameList)
	return fileNameList

def findRandomMessage():
	fileNames = fileNumbers()
	newWavName = RECORD_DIR + "/" + random.choice (fileNames)
	print("Random Nachricht: " + newWavName)
	return newWavName
#---------------------------Shout------------------------------------------------------

import socket
import subprocess

def shout (tts, wavName, speaker, PickUp):
	play_aloud (tts, wavName, speaker, PickUp) #hört auf wenn PickUp == True


def turn_off (button):
	time_pressed = 0
	while button.is_pressed and time_pressed < 10:
		time.sleep (0.5)
		time_pressed += 1

	if time_pressed >= 10:
		return True

	return False

def off_hook_loop (PickUp, dial, ButtonLeft, ButtonMiddle, tts, led):

	maxRecordingTime = 1200     #in 0.1 sek
	minRecordingTime = 20

	def dial_number_abort ():
		return ButtonLeft.is_pressed or not PickUp.is_pressed

	def dial_digit_abort ():
		return not PickUp.is_pressed


	start_dial_tone ()

	while PickUp.is_pressed:
		# dialing
		if dial.is_used ():
			stop_dial_tone ()

			dialedNumber = dial.get_number (dial_number_abort, led)
			oldWavName = newWavName(dialedNumber)
			play_recording (tts, oldWavName, PickUp) #hört auf wenn PickUp == False

			start_dial_tone ()

		# recording
		if ButtonLeft.is_pressed:
			stop_dial_tone ()

			myNewWavName, newRecordingNumber = findNewFileName()
			tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " wird gestartet") #ansage welche Aufnahme es ist

			aborted = False
			recordingTime = 0
			with Recorder (myNewWavName, led) as recorder:

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

			if recordingTime > maxRecordingTime:
				tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + "wegen overtime beendet.")
			elif aborted:
				tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " abgebrochen")
			elif recordingTime <= minRecordingTime:
				tts.say ("Aufnahme zu kurz")
			else:
				print ("Aufnahme Nr.: " + str(newRecordingNumber) + " beendet.")

			start_dial_tone ()


		# open Menu
		if ButtonMiddle.is_pressed:
			stop_dial_tone ()

			tts.say("Menü wird geöffnet.")
			dialedOption = dial.get_digit (dial_digit_abort, led)
			# aborted
			if dialedOption is None:
				pass
			if dialedOption == 0:
				tts.say_time ()
			elif dialedOption == 1:
				tts.random_prayer (PickUp)
			elif dialedOption == 2:
				tts.random_dice_prayer (PickUp)
			elif dialedOption == 3:
				tts.random_pater (PickUp)
			else:
				tts.say("Das habe ich nicht verstanden. Auf wiederhören")

			start_dial_tone ()

	stop_dial_tone ()
	return

def run_webapp ():
	# setup connection to webapp
	server, client = socket.socketpair (socket.AF_UNIX,
	                                    socket.SOCK_DGRAM, 0)

	# pass file descriptor to webapp
	client_fd = client.fileno ()

	# start webapp
	process = subprocess.Popen ([WEBAPP_EXEC, str (client_fd)],
	                            pass_fds=(client_fd, ))

	return process, server

def main ():
	# setup pygame
	pygame.mixer.init()

	# setup text to speech
	tts = TTS ()


	DialCounter = Button(2) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(26) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	PickUp = Button(18) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(3) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(27) #Mittlerer Knopf
	SpeakerSwich = Button(17) #Rechter Kippschalter (grüner Anschluss)
	led = gpiozero.LED (20)

	dial = Dial (DialInUse, DialCounter)

	essenIstFertig1830 = newWavName(1830)
	wucher1930 = newWavName(1930)
	tagesschau2000 = newWavName(2014)

	pygame.init()


	# Thread for Speaker
	speakerThread = SpeakerThread (SpeakerSwich)
	speakerThread.start()

	# start webapp
	webAppProcess, connection = run_webapp ()

	# initialize random module
	random.seed ()

	while not turn_off (ButtonMiddle):

		if PickUp.is_pressed:
			off_hook_loop (PickUp, dial,
			               ButtonLeft, ButtonMiddle,
			               tts, led)

		#-------------------------Klingelroutine-------------------------------------------
		if is_call_time ():
			print("ringing!!!!!!!")
			callingFile = findRandomMessage() #zufällige Datei die anruft
			ringing (tts, callingFile, speakerThread, PickUp)

		handle_queued_call (connection, tts, speakerThread, PickUp)

		weekDayInt = getWeekDayInt()
		if weekDayInt > 0 and weekDayInt < 4: #von Dienstag bis Freitag Wahr
			if getTimeInt() == 183000:
				shout (tts, essenIstFertig1830, speakerThread, PickUp)
			if getTimeInt() == 193000:
				shout (tts, wucher1930, speakerThread, PickUp)
		if getTimeInt() == 200000:
			shout (tts, tagesschau2000, speakerThread, PickUp)

		time.sleep (0.5)


	speakerThread.join()
	webAppProcess.terminate()
	#GPIO.close()
	#GPIOZero.close()

if __name__ == '__main__':
	try:
		main ()

	except Exception as error:

		# creating/opening a file
		f = open(TELEFONO_LOG_FILE, "a")

		# writing in the file
		f.write (time.asctime ())
		f.write (": ")
		f.write (str (error))
		f.write ("\n")

		# closing the file
		f.close()
