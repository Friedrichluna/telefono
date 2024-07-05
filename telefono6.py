#!/usr/bin/python3


import sys

BASE_DIR = "/home/pi/telefono/telefono"

RECORD_DIR = BASE_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RING_FILE = BASE_DIR + "/relevant/telephone-ring-02.wav"
DIAL_FILE = BASE_DIR + "/relevant/US_dial_tone.ogg.wav"

SERVER_QUEUE_FILE = BASE_DIR + "/relevant/queFile.txt"

WEBAPP_EXEC = BASE_DIR + '/../webapp/app2.py'

LOG_FILE = BASE_DIR + "/relevant/telefono.log"


#-----------------------------recorder---------------------------------------
import subprocess
import time
import wave

import linkat
import pyaudio

class Recorder ():
	def __init__(self, fname,
	             channels=1, rate=44100, frames_per_buffer=512):

		self.channels = channels
		self.rate = rate
		self.frames_per_buffer = frames_per_buffer

		self.fname = fname
		self._pa = pyaudio.PyAudio()

		self._prepare_file ()

		self._stream = None

	def __enter__(self):
		return self

	def __exit__(self, exception, value, traceback):
		self.close()

	def record(self, duration):
		# Use a stream with no callback function in blocking mode
		self._stream = self._pa.open(format=pyaudio.paInt16,
		                             channels=self.channels,
		                             rate=self.rate,
		                             input=True,
		                             frames_per_buffer=self.frames_per_buffer)

		for _ in range(int(self.rate / self.frames_per_buffer * duration)):
			audio = self._stream.read(self.frames_per_buffer)
			self.wavefile.writeframes(audio)

		return None

	def start_recording(self):
		# Use a stream with a callback in non-blocking mode
		self._stream = self._pa.open(format=pyaudio.paInt16,
		                             channels=self.channels,
		                             rate=self.rate,
		                             input=True,
		                             frames_per_buffer=self.frames_per_buffer,
		                             stream_callback=self.get_callback())
		self._stream.start_stream()
		return self

	def stop_recording(self):
		self._stream.stop_stream()
		return self

	def get_callback(self):
		def callback(in_data, frame_count, time_info, status):
			self.wavefile.writeframes(in_data)
			return None, pyaudio.paContinue
		return callback


	def close(self):
		self._stream.close()
		self._pa.terminate()
		self.wavefile.close()

	def _prepare_file (self):

		# create temporary file
		self.fd = os.open (os.path.dirname (self.fname),
		                   os.O_TMPFILE | os.O_WRONLY,
		                   mode=0o600)

		self.wavefile = wave.open (os.fdopen (self.fd, "wb"), "w")
		self.wavefile.setnchannels (self.channels)
		self.wavefile.setsampwidth (self._pa.get_sample_size (pyaudio.paInt16))
		self.wavefile.setframerate (self.rate)
		return

	def save (self):
		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % self.fd,
		                linkat.AT_FDCWD, self.fname.encode(),
		                linkat.AT_SYMLINK_FOLLOW)

		self.wavefile.close ()

#rec = Recorder(channels=2)
#with rec.open('nonblocking.wav', 'wb') as recfile2:
#        recfile2.start_recording()
#        time.sleep(5.0)
#        recfile2.stop_recording()



#---------------------- Dial ---------------------------------------------------------------------

from gpiozero import Button, LED
import time


DIAL_TIMEOUT = 200000
def wait_for_number (DialInUse, DialCounter, StopDialButton, contButton, led):
	led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
	number = 0

	while not StopDialButton.is_pressed and contButton.is_pressed:

		# timeout while idle
		timeCounter = 0
		while timeCounter <= DIAL_TIMEOUT \
		and (not StopDialButton.is_pressed \
		     and contButton.is_pressed):

			if DialInUse.is_pressed:
				break
			time.sleep (0.001)
			timeCounter += 1
		else:
			break

		digit = 0
		while DialInUse.is_pressed:

			# wait for HIGH
			while DialInUse.is_pressed:
				time.sleep (0.01)
				if not DialCounter.is_pressed:
					break
			else:
				break

			digit += 1

			# wait for LOW
			while not DialCounter.is_pressed \
			and DialInUse.is_pressed:
				time.sleep (0.01)

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

#NeueZahl = wait_for_number(ButtonLeft, Pickup)
#print(NeueZahl)

def wait_for_digit (DialInUse, DialCounter, contButton, led):
	led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
	dialedDigit = 0
	switch = False
	timeCounter = 0
	trueZero = False
	while True:
		time.sleep (0.001)
		timeCounter = timeCounter + 1
		dialedDigit = 0
		dialWasActive = False
		if DialInUse.is_pressed:
			time.sleep (0.2)
			while DialInUse.is_pressed:
				time.sleep (0.01)
				if (not DialCounter.is_pressed) and (not switch):
					switch = True
					dialedDigit = dialedDigit + 1
					#print("+1")
				elif DialCounter.is_pressed:
					switch = False
					#print("test")
				dialWasActive = True
		if dialWasActive:
			timeCounter = 0
			if dialedDigit > 9:
				trueZero = True
				dialedDigit = 0
			print(dialedDigit)
			break
		if timeCounter > 200000:
			break
		if not contButton.is_pressed:
			break
	led.off()
	if (dialedDigit == 0 and trueZero) or dialedDigit != 0:
		return dialedDigit
	else:
		return None

#NeueZiffer = wait_for_Digit(ButtonLeft)
#print(NeueZIgger)



#-----------------------------Memory Handle-------------------------------------------------------

def returnFileText(fileName):
	file1 = open(str(fileName),"r")
	readText = file1.read()
	file1.close()
	return(readText)

def overWriteFile(fileName, writtenText):
	file1 = open(fileName,"w")
	file1.write(str(writtenText))
	file1.close()

#oldText = returnFileText("fileNumber.txt")
#overWriteFile("fileNumber.txt", str(int(oldText) + 1))
#NewText = returnFileText("fileNumber.txt")
#print(NewText)


#---------------------------Pygame AudioPlayer------------------------------------
#needs GPIOZero buttons
import pygame

def playFile(tts, fileName, breakButton):
	if os.path.exists (fileName):
		pygame.mixer.music.load(fileName)
		pygame.mixer.music.play()
		while pygame.mixer.music.get_busy():
				if breakButton.is_pressed:
					pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")

#playFile(tts, "audio.wav", ButtonLeft)

def playFile2(fileName, breakButton1, breakButton2): #zwei abbruch Bedingungen
	pygame.mixer.music.load(fileName)
	pygame.mixer.music.play()
	while pygame.mixer.music.get_busy():
			if breakButton1.is_pressed or breakButton2.is_pressed:
				pygame.mixer.music.stop()
def playFile0(fileName): #keine Abbruchbedingung (muss seperat gesetzt werden)
	pygame.mixer.music.load(fileName)
	pygame.mixer.music.play()


def playFileNeg(tts, fileName, contButton):
	if os.path.exists (fileName):
		pygame.mixer.music.load(fileName)
		pygame.mixer.music.play()

		while pygame.mixer.music.get_busy():
			time.sleep (0.01)
			if not contButton.is_pressed:
				pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")

#playFileNeg(tts, "audio.wav", PickUp)

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
		playFileNeg(self, filename, PickUp)

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
	speaker.activate ()
	playFile(tts, RING_FILE, PickUp) #hört auf wenn PickUp == True
	speaker.deactivate ()
	time.sleep (1) #test
	playFileNeg(tts, callingFile_, PickUp) #hört auf wenn PickUp == False


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

def callInQue(tts, queFileAdress, speaker, PickUp):
	callingFileNumber = returnFileText(queFileAdress)
	callingFile = newWavName(callingFileNumber)

	if callingFileNumber != "":
		print("ringing Que!!")
		ringing (tts, callingFile, speaker, PickUp)
		overWriteFile(queFileAdress, "")


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


def shout (tts, wavName, speaker, PickUp):
	speaker.activate ()
	time.sleep (2)
	playFile(tts, wavName, PickUp) #hört auf wenn PickUp == True
	speaker.deactivate ()


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
	led = LED(20)


	essenIstFertig1830 = newWavName(1830)
	wucher1930 = newWavName(1930)
	tagesschau2000 = newWavName(2014)

	maxRecordingTime = 1200     #in 0.1 sek
	minRecordingTime = 20
	pygame.init()


	# Thread for Speaker
	speakerThread = SpeakerThread (SpeakerSwich)
	speakerThread.start()

	webAppProcess = subprocess.Popen(['python3', WEBAPP_EXEC])

	# initialize random module
	random.seed ()

	noInterrupt = True
	while noInterrupt:

		#-------------------------Hörer Abgenommen--------------------------------------------
		while PickUp.is_pressed: #während der Hörer abgenommen ist
			if DialInUse.is_pressed:           #wählt Nummer
				time.sleep (0.1)
				if DialInUse.is_pressed:
					pygame.mixer.music.stop() #Freiton wird unterbrochen
					dialedNumber = str(wait_for_number(DialInUse, DialCounter, ButtonLeft, PickUp, led))
					if PickUp.is_pressed: #falls er beim Wählen aufgelegt hat
						#tts.say("Spiele Aufnahme Nr.: " + dialedNumber)
						oldWavName = newWavName(dialedNumber)
						playFileNeg(tts, oldWavName, PickUp) #hört auf wenn PickUp == False

			if ButtonLeft.is_pressed:          #Aufnahme Starten
				pygame.mixer.music.stop() #Freiton wird unterbrochen
				myNewWavName, newRecordingNumber = findNewFileName()

				with Recorder(myNewWavName, channels=2) as recfile2:
					tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " wird gestartet") #ansage welche Aufnahme es ist
					recfile2.start_recording()
					recordingTime = 0
					led.on()
					while True:
						time.sleep (0.1)
						recordingTime = recordingTime + 1
						if recordingTime > maxRecordingTime:    # beenden wenn mehr als 2min aufgenommen wurde
							led.off()
							recfile2.stop_recording()
							tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + "wegen overtime beendet.")
							recfile2.save ()
							break
						if (not PickUp.is_pressed) or ButtonLeft.is_pressed:
							led.off()
							recfile2.stop_recording()
							if recordingTime > minRecordingTime:
								print ("Aufnahme Nr.: " + str(newRecordingNumber) + " beendet.")
								recfile2.save ()
							else:
								tts.say ("Aufnahme zu kurz")
							time.sleep (2) #button release Time
							break
						if ButtonMiddle.is_pressed:
							led.off()
							tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " abgebrochen")
							recfile2.stop_recording()
							time.sleep (2) #button release Time
							break

			# open Menu
			if ButtonMiddle.is_pressed:
				pygame.mixer.music.stop() #Freiton wird unterbrochen
				tts.say("Menü wird geöffnet.")
				dialedOption = wait_for_digit (DialInUse, DialCounter, PickUp, led)
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


			if not pygame.mixer.music.get_busy(): #wenn der Freiton noch nicht spielt
				playFile0(DIAL_FILE)  #Freiton

		pygame.mixer.music.stop() #Freiton wird unterbrochen



		#-------------------------Klingelroutine-------------------------------------------
		if is_call_time ():
			print("ringing!!!!!!!")
			callingFile = findRandomMessage() #zufällige Datei die anruft
			ringing (tts, callingFile, speakerThread, PickUp)

		callInQue (tts, SERVER_QUEUE_FILE, speakerThread, PickUp)

		weekDayInt = getWeekDayInt()
		if weekDayInt > 0 and weekDayInt < 4: #von Dienstag bis Freitag Wahr
			if getTimeInt() == 183000:
				shout (tts, essenIstFertig1830, speakerThread, PickUp)
			if getTimeInt() == 193000:
				shout (tts, wucher1930, speakerThread, PickUp)
		if getTimeInt() == 200000:
			shout (tts, tagesschau2000, speakerThread, PickUp)
		#-------------------------Ausschalten-----------------------------------------------
		interruptCounter = 0
		while ButtonMiddle.is_pressed:
			time.sleep (0.5)
			interruptCounter = interruptCounter + 1
			if not ButtonMiddle.is_pressed:
				interruptCounter = 0
			if interruptCounter >= 10:
				noInterrupt = False
				break
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
