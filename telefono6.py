#!/usr/bin/python3


import sys

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
			return in_data, pyaudio.paContinue
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


def wait_for_number(StopDialButton, contButton):
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
			if (DialCounter.is_pressed == False) and (switch != True):
				switch = True
				dialedDigit = dialedDigit + 1
				#print("+1")
			elif DialCounter.is_pressed == True:
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
		if contButton.is_pressed == False:
			break
	led.off()
	return dialedNumber

#NeueZahl = wait_for_number(ButtonLeft, Pickup)
#print(NeueZahl)

def wait_for_digit(contButton):
	led.blink(on_time=0.1, off_time=0.1, n=None, background=True)
	dialedDigit = 0
	switch = False
	timeCounter = 0
	while True:
		sleep(0.001)
		timeCounter = timeCounter + 1
		dialedDigit = 0
		dialWasActive = False
		if DialInUse.is_pressed:
			sleep(0.2)
			while DialInUse.is_pressed:
				sleep(0.01)
				if (DialCounter.is_pressed == False) and (switch != True):
					switch = True
					dialedDigit = dialedDigit + 1
					#print("+1")
				elif DialCounter.is_pressed == True:
					switch = False
					#print("test")
				dialWasActive = True
		if dialWasActive:
			timeCounter = 0
			if dialedDigit > 9:
				dialedDigit = 0
			print(dialedDigit)
			break
		if timeCounter > 200000:    #wird in Argument definiert
			break
		if contButton.is_pressed == False:
			break
	led.off()
	return dialedDigit

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
	if fileExists(fileName) == True:
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
	if fileExists(fileName) == True:
		pygame.mixer.music.load(fileName)
		pygame.mixer.music.play()

		while pygame.mixer.music.get_busy():
			sleep(0.01)
			if contButton.is_pressed == False:
				pygame.mixer.music.stop()
	else:
		tts.say("Diese Aufnahme existiert noch nicht.")

#playFileNeg(tts, "audio.wav", PickUp)

#--------------------------File Name Generator----------------------------------

def newWavName(_newWavNumber):
	_nudeWavName = "/home/pi/telefono/recording"       #WavDateiname ohne nummer und .wav
	newWavName = _nudeWavName + str(_newWavNumber) + ".wav"
	return newWavName

#--------------------------File management-----------------------------------------

import os

from os.path import exists as fileExists

def delFile(_fileName):
	os.remove(_fileName)

#--------------------------FindNewFile-----------------------------------------
def findNewFileName():
	counter = 0
	while True:
		counter = counter + 1
		myNewWavName = newWavName(counter)
		if (fileExists(myNewWavName)) == False:
			break
	return myNewWavName

#--------------------------Text to Speech--------------------------------------
#import sys
#    sys.path.append('/home/pi/.local/lib/python3.9/site-packages')

import datetime
import pyttsx3

class TTS():
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



#--------------------------Relay-----------------------------------------------
import RPi.GPIO as GPIO
from threading import Thread
from threading import Event



#---------------------------Ringing------------------------------------
#from time import sleep
ringTone = "/home/pi/telefono/relevant/telephone-ring-02.wav"

def ringing(tts, callingFile_):
	activateSpeaker()
	playFile(tts, ringTone, PickUp) #hört auf wenn PickUp == True
	idleSpeaker()
	sleep(1) #test
	playFileNeg(tts, callingFile_, PickUp) #hört auf wenn PickUp == False


#--------------------------CallingRoutine----------------------------
from datetime import datetime
from random import seed
from random import randint

minHour = 15
maxHour = 21
needNewTime = None

def getTimeInt():
	now = datetime.now()
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
	if ((currentTimeInt > maxHour*10000) or (currentTimeInt < minHour*10000)) and needNewTime:  #wenn nach Anrufszeit und no k>
		randTimeInt = newRandTimeInt()  #dann neue Zeit erstellen
		needNewTime = False
		print("new Random Time:") #Test
		print(randTimeInt) #test
	if currentTimeInt == randTimeInt:
		needNewTime = True
		return True

def callInQue(tts, queFileAdress):
	callingFileNumber = returnFileText(queFileAdress)
	callingFile = newWavName(callingFileNumber)

	if callingFileNumber != "":
		print("ringing Que!!")
		ringing(tts, callingFile)
		overWriteFile(queFileAdress, "")


def getWeekDayInt():
	now = datetime.now()
	return now.weekday()


#---------------------------acuteMessage-----------------------------------------------
def findHighestMessage(): #gibt den Namen der höchsten existierenden Datei zurück
	counter = 0
	while True:
		countedWavName = newWavName(counter)
		if fileExists(countedWavName) == False: #sucht die erste Datei die nicht existiert
			print("Höchste Nachricht: " + newWavName(counter - 1))
			return newWavName(counter - 1)
		counter = counter + 1

def findHighestMessageNumber(): #gibt den Namen der höchsten existierenden Datei zurück
	counter = 0
	while True:
		countedWavName = newWavName(counter)
		if fileExists(countedWavName) == False: #sucht die erste Datei die nicht existiert
			return counter - 1
		counter = counter + 1


#---------------------------random old Message-----------------------------------------
#from random import randint
from os import listdir
from os.path import isfile, join

def fileNumbers():
	fileNameList = [f for f in listdir("/home/pi/telefono") if isfile(join("/home/pi/telefono", f))]
	#print(fileNameList)
	return fileNameList

def findRandomMessage():
	fileNames = fileNumbers()
	maxMessageNumber = len(fileNames) - 1
	randomMessageNumber = randint(0, maxMessageNumber)
	newWavName = "/home/pi/telefono/" + str(fileNames[randomMessageNumber])
	print("Random Nachricht: " + newWavName)
	return newWavName
#---------------------------Shout------------------------------------------------------


def shout(tts, wavName):
	activateSpeaker()
	sleep(2)
	playFile(tts, wavName, PickUp) #hört auf wenn PickUp == True
	idleSpeaker()


#---------------------------Menu-------------------------------------------------------

supperPrayers = [101, 102, 103, 104, 105]
def zufaelligesGebet(tts):
	now = datetime.now()
	second = now.strftime("%S")
	seed(second)
	maxPrayer = len(supperPrayers) - 1
	randPrayerNumber = randint(0, maxPrayer)

	print("playing: " + str(randPrayerNumber))
	supperPrayerNumber = supperPrayers[randPrayerNumber]

	supperPrayerName = newWavName(supperPrayerNumber)
	#print(supperPrayerName)
	playFileNeg(tts, supperPrayerName, PickUp)

gebetswuerfelListe = [201, 202, 203, 204, 205, 206]
def gebetswuerfel(tts):
	now = datetime.now()
	second = now.strftime("%S")
	seed(second)
	maxPrayer = len(gebetswuerfelListe) - 1
	randPrayerNumber = randint(0, maxPrayer)

	print("playing: " + str(randPrayerNumber))
	supperPrayerNumber = gebetswuerfelListe[randPrayerNumber]

	supperPrayerName = newWavName(supperPrayerNumber)
	#print(supperPrayerName)
	playFileNeg(tts, supperPrayerName, PickUp)


paterListe = [2, 10, 11, 19, 22, 26, 30, 88]
def randomPater(tts):
	now = datetime.now()
	second = now.strftime("%S")
	seed(second)
	maxPrayer = len(paterListe) - 1
	randPrayerNumber = randint(0, maxPrayer)

	print("playing: " + str(randPrayerNumber))
	supperPrayerNumber = paterListe[randPrayerNumber]

	supperPrayerName = newWavName(supperPrayerNumber)
	#print(supperPrayerName)
	playFileNeg(tts, supperPrayerName, PickUp)


def main ():
	# setup pygame
	pygame.mixer.init()

	# setup text to speech
	tts = TTS ()

	# setup Relay
	GPIO.setmode(GPIO.BCM) # GPIO Numbers instead of board numbers
	RELAIS_1_GPIO = 4
	GPIO.setup(RELAIS_1_GPIO, GPIO.OUT) # GPIO Assign mode


	spkEvent = Event()
	spkStopEvent = Event()

	class SpeakerThreadClass(Thread):
		def run(self):
			while True:
				if spkEvent.is_set() or SpeakerSwich.is_pressed:
					GPIO.output(RELAIS_1_GPIO, GPIO.LOW) # on
				else:
					GPIO.output(RELAIS_1_GPIO, GPIO.HIGH) # off
				sleep(0.2)
				if spkStopEvent.is_set():
					break

	speakerThread = SpeakerThreadClass()


	def activateSpeaker():
		spkEvent.set()
	def idleSpeaker():
		spkEvent.clear()


	#______________________________________________________________________________________
	#---------------------------Program----------------------------------------------------


	DialCounter = Button(2) #Zähler für die gewählte Zahl (rot)
	DialInUse = Button(26) #Wählscheibe wird benutzt (grau)(weiß im Tel)
	PickUp = Button(18) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
	ButtonLeft = Button(3) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
	ButtonMiddle = Button(27) #Mittlerer Knopf
	SpeakerSwich = Button(17) #Rechter Kippschalter (grüner Anschluss)
	led = LED(20)


	queFileAdress = "/home/pi/telefono/relevant/queFile.txt"

	essenIstFertig1830 = newWavName(1830)
	wucher1930 = newWavName(1930)
	tagesschau2000 = newWavName(2014)

	maxRecordingTime = 1200     #in 0.1 sek
	pygame.init()

	acuteMessagePlayed = True   #True: by default not acute
	speakerThread.start()     #Thread für Lautsprecher

	#os.system('python3 /home/pi/webapp/app2.py &') #webApp start
	webAppProcess = subprocess.Popen(['python3', '/home/pi/webapp/app2.py'])

	now = datetime.now()
	second = now.strftime("%S%M")
	seed(second) #den seed für die Zufallsfunktionen

	noInterrupt = True
	while noInterrupt:

		phoneWasHungUp = True #wird für acute Message gebraucht
		#-------------------------Hörer Abgenommen--------------------------------------------
		while PickUp.is_pressed: #während der Hörer abgenommen ist
			if DialInUse.is_pressed:           #wählt Nummer
				sleep(0.1)
				if DialInUse.is_pressed:
					pygame.mixer.music.stop() #Freiton wird unterbrochen
					dialedNumber = str(wait_for_number(ButtonLeft, PickUp))
					if PickUp.is_pressed: #falls er beim Wählen aufgelegt hat
						#tts.say("Spiele Aufnahme Nr.: " + dialedNumber)
						oldWavName = newWavName(dialedNumber)
						playFileNeg(tts, oldWavName, PickUp) #hört auf wenn PickUp == False

			if ButtonLeft.is_pressed:          #Aufnahme Starten
				pygame.mixer.music.stop() #Freiton wird unterbrochen
				myNewWavName = findNewFileName()

				rec = Recorder(channels=2)
				newRecordingNumber = findHighestMessageNumber() + 1
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
						if (PickUp.is_pressed == False) or ButtonLeft.is_pressed:
							led.off()
							print("Aufnahme Nr.: " + str(newRecordingNumber) + " beendet.")
							recfile2.stop_recording()
							sleep(2) #button release Time
							break
						if ButtonMiddle.is_pressed:      #alte Aufnahme auswählen
							led.off()
							tts.say("Aufnahme Nr.: " + str(newRecordingNumber) + " abgebrochen")
							recfile2.stop_recording()
							delFile(myNewWavName)
							sleep(2) #button release Time
							break

			if ButtonMiddle.is_pressed:
				pygame.mixer.music.stop() #Freiton wird unterbrochen
				tts.say("Menü wird geöffnet.")
				dialedOption = wait_for_digit(PickUp)
				if dialedOption == 0:
					tts.say_time ()
				elif dialedOption == 1:
					zufaelligesGebet(tts)
				elif dialedOption == 2:
					gebetswuerfel(tts)
				elif dialedOption == 3:
					randomPater(tts)
				else:
					tts.say("Das habe ich nicht verstanden. Auf wiederhören")


			if pygame.mixer.music.get_busy() == False: #wenn der Freiton noch nicht spielt
				playFile0("/home/pi/telefono/relevant/US_dial_tone.ogg.wav")  #Freiton

		pygame.mixer.music.stop() #Freiton wird unterbrochen



		#-------------------------Klingelroutine-------------------------------------------
		if callRoutine() == True:
			print("ringing!!!!!!!")
			callingFile = findRandomMessage() #zufällige Datei die anruft
			ringing(tts, callingFile)

		callInQue(tts, queFileAdress)

		weekDayInt = getWeekDayInt()
		if weekDayInt > 0 and weekDayInt < 4: #von Dienstag bis Freitag Wahr
			if getTimeInt() == 183000:
				shout(tts, essenIstFertig1830)
			if getTimeInt() == 193000:
				shout(tts, wucher1930)
		if getTimeInt() == 200000:
			shout(tts, tagesschau2000)
		#-------------------------Ausschalten-----------------------------------------------
		interruptCounter = 0
		while ButtonMiddle.is_pressed:
			sleep(0.5)
			interruptCounter = interruptCounter + 1
			if ButtonMiddle.is_pressed == False:
				interruptCounter = 0
			if interruptCounter >= 10:
				noInterrupt = False
				break
		sleep(0.5)
	spkStopEvent.set()
	speakerThread.join()
	webAppProcess.terminate()
	#GPIO.close()
	#GPIOZero.close()

if __name__ == '__main__':
	try:
		main ()

	except Exception as Argument:

		# creating/opening a file
		f = open("home/pi/telefono/relevant/telefonoCrashLog.txt", "a")

		# writing in the file
		f.write(str(Argument))

		# closing the file
		f.close()
