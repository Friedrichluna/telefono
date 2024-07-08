#!/usr/bin/python3


import sys

BASE_DIR = "/home/pi/telefono/telefono"

RECORD_DIR = BASE_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RING_FILE = BASE_DIR + "/relevant/telephone-ring-02.wav"
DIAL_TONE_FILE = BASE_DIR + "/relevant/US_dial_tone.ogg.wav"

WEBAPP_EXEC = BASE_DIR + '/../webapp/app2.py'

LOG_FILE = BASE_DIR + "/relevant/telefono.log"


#-----------------------------recorder---------------------------------------
import subprocess
import time
import wave

import linkat
import pyaudio


CHANNELS = 2
RATE = 44100
FRAME_PER_BUFFER = 512

class Recorder ():
	def __init__ (self, fname, indicator,
	              channels=CHANNELS, rate=RATE,
	              frames_per_buffer=FRAME_PER_BUFFER):

		self.fname = fname
		self.indicator = indicator
		self._pa = pyaudio.PyAudio ()

		# Use a stream with a callback in non-blocking mode
		self._stream = self._pa.open (format=pyaudio.paInt16,
		                              channels=channels,
		                              rate=rate,
		                              input=True,
		                              frames_per_buffer=frames_per_buffer,
		                              stream_callback=self.__on_data)

		# create temporary file
		self.fd = os.open (os.path.dirname (self.fname),
		                   os.O_TMPFILE | os.O_WRONLY,
		                   mode=0o600)

		self.wavefile = wave.open (os.fdopen (self.fd, "wb"), "w")
		self.wavefile.setnchannels (channels)
		self.wavefile.setsampwidth (self._pa.get_sample_size (pyaudio.paInt16))
		self.wavefile.setframerate (rate)
		return

	def __on_data (self, in_data, frame_count, time_info, status):
		self.wavefile.writeframes (in_data)
		return None, pyaudio.paContinue

	def save (self):
		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % self.fd,
		                linkat.AT_FDCWD, self.fname.encode(),
		                linkat.AT_SYMLINK_FOLLOW)
		return

	def __enter__ (self):
		self.indicator.on ()
		self._stream.start_stream ()

		return self

	def __exit__ (self, exception, value, traceback):
		self._stream.stop_stream ()
		self.indicator.off ()

		self._stream.close ()
		self._pa.terminate ()
		self.wavefile.close ()
		return


#---------------------- Dial ---------------------------------------------------------------------

import gpiozero
import time

class Button (gpiozero.Button):
	def __init__ (self, *args, **kwargs):
		super ().__init__ (*args, **kwargs)

	@property
	def is_released (self) -> bool:
		if not self.is_pressed:
			return False

		while self.is_pressed:
			pass

		return True


DIAL_TIMEOUT = 200000
DIAL_TIMEOUT_SLEEP = 0.001
DIAL_SLEEP = 0.01

class Dailer ():
	def __init__ (self, DialInUse, DialCounter):
		self.__flag = DialInUse
		self.__counter = DialCounter
		return

	def is_used (self):
		if not self.dialing:
			return False

		time.sleep (0.1)

		return self.dialing

	@property
	def dialing (self):
		return self.__flag.is_pressed

	@property
	def digit_moved (self):
		return self.__counter.is_pressed

	def get_number (self, abort, led):
		led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
		number = 0

		while not abort():

			# timeout while idle
			timeCounter = 0
			while timeCounter <= DIAL_TIMEOUT \
			and not abort ():

				if self.dialing:
					break
				time.sleep (DIAL_TIMEOUT_SLEEP)
				timeCounter += 1
			else:
				break

			digit = 0
			while self.dialing:

				# wait for HIGH
				while self.dialing:
					time.sleep (DIAL_SLEEP)
					if not self.digit_moved:
						break
				else:
					break

				digit += 1

				# wait for LOW
				while not self.digit_moved \
				and self.dialing:
					time.sleep (DIAL_SLEEP)

			# not dialed
			if digit == 0:
				continue

			# 0 dialed
			if digit > 9:
				digit = 0

			number *= 10
			number += digit
			print(digit)

		led.off()
		return number

	def get_digit (self, abort, led):
		led.blink(on_time=0.1, off_time=0.1, n=None, background=True)

		# timeout while idle
		timeCounter = 0
		while timeCounter <= DIAL_TIMEOUT \
		and not abort():
			if self.dialing:
				break

			time.sleep (DIAL_TIMEOUT_SLEEP)
			timeCounter += 1
		else:
			led.off()
			return None


		dialedDigit = 0
		while self.dialing:

			# wait for LOW
			while self.dialing:
				if not self.digit_moved:
					break

				time.sleep (DIAL_SLEEP)
			else:
				break

			dialedDigit += 1

			# wait for HIGH
			while not self.digit_moved \
			and self.dialing:
				time.sleep (DIAL_SLEEP)

		# not dialed
		if dialedDigit == 0:
			dialedDigit = None

		# 0 dialed
		elif dialedDigit > 9:
			dialedDigit = 0
			print(dialedDigit)

		else:
			print(dialedDigit)

		led.off()
		return dialedDigit


#---------------------------Pygame AudioPlayer------------------------------------
#needs GPIOZero buttons
import pygame

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

#--------------------------Text to Speech--------------------------------------
#import sys
#    sys.path.append('/home/pi/.local/lib/python3.9/site-packages')

import datetime
import pyttsx3
import random

class TTS():
	supperPrayers = [101, 102, 103, 104, 105]
	dicePrayers = [201, 202, 203, 204, 205, 206]
	pater = [2, 10, 11, 19, 22, 26, 30, 88]

	def __init__ (self):
		self.__engine = pyttsx3.init()
		self.__engine.setProperty('rate', 140)    # Speed percent (can go over 100)
		self.__engine.setProperty('volume', 1)  # Volume 0-1
		self.__engine.setProperty('voice', "german+f2") #sprache auf Deutsch ändern

		return

	def say (self, text):
		print(text)
		self.__engine.say(text)
		#self.__engine.startLoop(False)
		self.__engine.runAndWait()

	def say_time (self):
		print("uhrzeit ansagen")

		FORMAT = "Es ist %H Uhr %M am %d.%m.%Y."
		now = datetime.datetime.now()
		timeInWords = now.strftime (FORMAT)

		self.say(timeInWords)

	def _random (self, _list, PickUp):
		filename = newWavName (random.choice (_list))
		print("playing: " + filename)
		play_recording (self, filename, PickUp)

	def random_prayer (self, PickUp):
		self._random (self.supperPrayers, PickUp)

	def random_dice_prayer (self, PickUp):
		self._random (self.dicePrayers, PickUp)

	def random_pater (self, PickUp):
		self._random (self.pater, PickUp)



#--------------------------Relay-----------------------------------------------
import RPi.GPIO as GPIO
from threading import Thread
from threading import Event

RELAIS_1_GPIO = 4

class SpeakerThread (Thread):
	def __init__ (self, switch, gpio=RELAIS_1_GPIO):
		super ().__init__ ()

		self.__switch = switch
		self.__gpio = gpio

		# GPIO Numbers instead of board numbers
		GPIO.setmode(GPIO.BCM)
		# GPIO Assign mode
		GPIO.setup (self.__gpio, GPIO.OUT)

		self.__event = Event ()
		self.__stop = Event ()

	def run (self):
		while not self.__stop.is_set ():
			if self.__event.is_set () or self.__switch.is_pressed:
				GPIO.output (self.__gpio, GPIO.LOW) # on
			else:
				GPIO.output (self.__gpio, GPIO.HIGH) # off
			time.sleep (0.2)

	def activate (self):
		self.__event.set ()

	def deactivate (self):
		self.__event.clear ()

	def join (self, timeout=None):
		self.__stop.set ()
		super ().join (timeout)


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

def off_hook_loop (PickUp, dialer, ButtonLeft, ButtonMiddle, tts, led):

	maxRecordingTime = 1200     #in 0.1 sek
	minRecordingTime = 20

	def dial_number_abort ():
		return ButtonLeft.is_pressed or not PickUp.is_pressed

	def dial_digit_abort ():
		return not PickUp.is_pressed


	start_dial_tone ()

	while PickUp.is_pressed:
		# dialing
		if dialer.is_used ():
			stop_dial_tone ()

			dialedNumber = dialer.get_number (dial_number_abort, led)
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
			dialedOption = dialer.get_digit (dial_digit_abort, led)
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

	dialer = Dailer (DialInUse, DialCounter)

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
			off_hook_loop (PickUp, dialer,
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
		f = open(LOG_FILE, "a")

		# writing in the file
		f.write (time.asctime ())
		f.write (": ")
		f.write (str (error))
		f.write ("\n")

		# closing the file
		f.close()
