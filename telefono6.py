#!/usr/bin/python3


import sys

WAV_BASE_PATH = "/home/pi/telefono/recording"
WAV_EXT = ".wav"

RING_FILE = "/home/pi/telefono/relevant/telephone-ring-02.wav"
DIAL_FILE = "/home/pi/telefono/relevant/US_dial_tone.ogg.wav"

RECORD_DIR = "/home/pi/telefono"

SERVER_QUEUE_FILE = "/home/pi/telefono/relevant/queFile.txt"

WEBAPP_EXEC = '/home/pi/webapp/app2.py'

LOG_FILE = "home/pi/telefono/relevant/telefonoCrashLog.txt"


#-----------------------------recorder---------------------------------------
import pyaudio
import wave
import time
import subprocess

class Recorder(object):
	def __init__(self, channels=1, rate=44100, frames_per_buffer=512):
		self.channels = channels
		self.rate = rate
		self.frames_per_buffer = frames_per_buffer

	def open(self, fname, mode='wb'):
		return RecordingFile(fname, mode, self.channels, self.rate,
		                     self.frames_per_buffer)

class RecordingFile(object):
	def __init__(self, fname, mode, channels,
		     rate, frames_per_buffer):
		self.fname = fname
		self.mode = mode
		self.channels = channels
		self.rate = rate
		self.frames_per_buffer = frames_per_buffer
		self._pa = pyaudio.PyAudio()
		self.wavefile = self._prepare_file(self.fname, self.mode)
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

	def _prepare_file(self, fname, mode='wb'):
		wavefile = wave.open(fname, mode)
		wavefile.setnchannels(self.channels)
		wavefile.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
		wavefile.setframerate(self.rate)
		return wavefile

#rec = Recorder(channels=2)
#with rec.open('nonblocking.wav', 'wb') as recfile2:
#        recfile2.start_recording()
#        time.sleep(5.0)
#        recfile2.stop_recording()



#---------------------- Dial ---------------------------------------------------------------------

from gpiozero import Button, LED
from time import sleep


def wait_for_number (DialInUse, DialCounter, StopDialButton, contButton, led):
	led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
	dialedNumber = 0
	switch = False
	timeCounter = 0
	tureZero = False
	while True:
		sleep(0.001)
		timeCounter = timeCounter + 1
		dialedDigit = 0
		dialWasActive = False
		while DialInUse.is_pressed:
			sleep(0.01)
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
				tureZero = True
				dialedDigit = 0
			if (dialedDigit == 0 and tureZero) or dialedDigit != 0:
				dialedNumber = dialedNumber*10 + dialedDigit
				tureZero = False
				print(dialedDigit)
		if StopDialButton.is_pressed or timeCounter > 200000:    #wird in Argument definiert
			break
		if not contButton.is_pressed:
			break
	led.off()
	return dialedNumber

#NeueZahl = wait_for_number(ButtonLeft, Pickup)
#print(NeueZahl)

def wait_for_digit (DialInUse, DialCounter, contButton, led):
	led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
	dialedDigit = 0
	switch = False
	timeCounter = 0
	trueZero = False
	while True:
		sleep(0.001)
		timeCounter = timeCounter + 1
		dialedDigit = 0
		dialWasActive = False
		if DialInUse.is_pressed:
			sleep(0.2)
			while DialInUse.is_pressed:
				sleep(0.01)
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
			sleep(0.01)
			if not contButton.is_pressed:
				pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")

#playFileNeg(tts, "audio.wav", PickUp)

#--------------------------File Name Generator----------------------------------

def newWavName(wav_number):
	return WAV_BASE_PATH + str(wav_number) + WAV_EXT

#--------------------------File management-----------------------------------------

import os

def delFile(_fileName):
	os.remove(_fileName)

#--------------------------FindNewFile-----------------------------------------
def findNewFileName ():
	counter = 1
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
			sleep (0.2)

	def activate (self):
		self.__event.set ()

	def deactivate (self):
		self.__event.clear ()

	def join (self, timeout=None):
		self.__stop.set ()
		super ().join (timeout)


#---------------------------Ringing------------------------------------
#from time import sleep

def ringing (tts, callingFile_, speaker, PickUp):
	speaker.activate ()
	playFile(tts, RING_FILE, PickUp) #hört auf wenn PickUp == True
	speaker.deactivate ()
	sleep(1) #test
	playFileNeg(tts, callingFile_, PickUp) #hört auf wenn PickUp == False


#--------------------------CallingRoutine----------------------------
import datetime
from random import seed
from random import randint

minHour = 15
maxHour = 21
needNewTime = None

def getTimeInt():
	now = datetime.datetime.now()
	current_time = now.strftime("%H%M%S")
	return(int(current_time))

#seed(5) #ein Seed der 19:00Uhr als erstes ausspuckt

def newRandTimeInt():
	randHour = randint(minHour, maxHour) #es klingelt zwischen 15 und 20Uhr
	randTimeInt_ = randHour * 10000
	return randTimeInt_


def callRoutine():  #returns True for 1 sek per day
	global needNewTime
	global randTimeInt
	currentTimeInt = getTimeInt()
	if needNewTime == None:
		randTimeInt = currentTimeInt  #dann jetzige Zeit nehmen
		needNewTime = False
		print("ring Time: " + str(randTimeInt))  #Test
		print("current Time: " + str(currentTimeInt))
		return False

	if ((currentTimeInt > maxHour*10000) or (currentTimeInt < minHour*10000)) and needNewTime:  #wenn nach Anrufszeit und no k>
		randTimeInt = newRandTimeInt()  #dann neue Zeit erstellen
		needNewTime = False
		print("new Random Time:") #Test
		print(randTimeInt) #test
		return False

	if currentTimeInt == randTimeInt:
		needNewTime = True
		return True

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
#from random import randint
from os import listdir
from os.path import isfile, join

def fileNumbers():
	fileNameList = [f for f in listdir(RECORD_DIR) if isfile(join(RECORD_DIR, f))]
	#print(fileNameList)
	return fileNameList

def findRandomMessage():
	fileNames = fileNumbers()
	maxMessageNumber = len(fileNames) - 1
	randomMessageNumber = randint(0, maxMessageNumber)
	newWavName = RECORD_DIR + "/" + str(fileNames[randomMessageNumber])
	print("Random Nachricht: " + newWavName)
	return newWavName
#---------------------------Shout------------------------------------------------------


def shout (tts, wavName, speaker, PickUp):
	speaker.activate ()
	sleep(2)
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

	acuteMessagePlayed = True   #True: by default not acute

	# Thread for Speaker
	speakerThread = SpeakerThread (SpeakerSwich)
	speakerThread.start()

	#os.system('python3 /home/pi/webapp/app2.py &') #webApp start
	webAppProcess = subprocess.Popen(['python3', WEBAPP_EXEC])

	# initialize random module
	random.seed ()

	noInterrupt = True
	while noInterrupt:

		phoneWasHungUp = True #wird für acute Message gebraucht
		#-------------------------Hörer Abgenommen--------------------------------------------
		while PickUp.is_pressed: #während der Hörer abgenommen ist
			if DialInUse.is_pressed:           #wählt Nummer
				sleep(0.1)
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

				rec = Recorder(channels=2)
				with rec.open(myNewWavName, 'wb') as recfile2:
					tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " wird gestartet") #ansage welche Aufnahme es ist
					recfile2.start_recording()
					recordingTime = 0
					led.on()
					while True:
						time.sleep(0.1)
						recordingTime = recordingTime + 1
						if recordingTime > maxRecordingTime:    # beenden wenn mehr als 2min aufgenommen wurde
							led.off()
							recfile2.stop_recording()
							tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + "wegen overtime beendet.")
							break
						if (not PickUp.is_pressed) or ButtonLeft.is_pressed:
							led.off()
							recfile2.stop_recording()
							if recordingTime > minRecordingTime:
								print ("Aufnahme Nr.: " + str(newRecordingNumber) + " beendet.")
							else:
								tts.say ("Aufnahme zu kurz")
								delFile (myNewWavName)
							sleep(2) #button release Time
							break
						if ButtonMiddle.is_pressed:
							led.off()
							tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " abgebrochen")
							recfile2.stop_recording()
							delFile(myNewWavName)
							sleep(2) #button release Time
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
		if callRoutine():
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
			sleep(0.5)
			interruptCounter = interruptCounter + 1
			if not ButtonMiddle.is_pressed:
				interruptCounter = 0
			if interruptCounter >= 10:
				noInterrupt = False
				break
		sleep(0.5)


	speakerThread.join()
	webAppProcess.terminate()
	#GPIO.close()
	#GPIOZero.close()

if __name__ == '__main__':
	try:
		main ()

	except Exception as Argument:

		# creating/opening a file
		f = open(LOG_FILE, "a")

		# writing in the file
		f.write(str(Argument))

		# closing the file
		f.close()
