#!/usr/bin/python3


try:
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
    
    pygame.mixer.init()
    def playFile(fileName, breakButton):
        if fileExists(fileName) == True:
            pygame.mixer.music.load(fileName)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                    if breakButton.is_pressed:
                        pygame.mixer.music.stop()
        else: 
            ttsEngine("Diese Aufnahme existiert noch nicht.")

    #playFile("audio.wav", ButtonLeft)

    def playFile2(fileName, breakButton1, breakButton2): #zwei abbruch Bedingungen
        pygame.mixer.music.load(fileName)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
                if breakButton1.is_pressed or breakButton2.is_pressed:
                    pygame.mixer.music.stop()
    def playFile0(fileName): #keine Abbruchbedingung (muss seperat gesetzt werden)
        pygame.mixer.music.load(fileName)
        pygame.mixer.music.play()

        
    def playFileNeg(fileName, contButton):
        if fileExists(fileName) == True:
            pygame.mixer.music.load(fileName)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                sleep(0.01)
                if contButton.is_pressed == False:
                    pygame.mixer.music.stop()
        else: 
            ttsEngine("Diese Aufnahme existiert noch nicht.")
            
    #playFileNeg("audio.wav", PickUp)

    #--------------------------File Name Generatot----------------------------------

    def newWavName(_nudeWavName, _newWavNumber):
        newWavName = _nudeWavName + str(_newWavNumber) + ".wav"
        return newWavName

    #--------------------------File management-----------------------------------------

    import os

    from os.path import exists as fileExists

    def delFile(_fileName):
        os.remove(_fileName)

    #--------------------------FindNewFile-----------------------------------------
    def findNewFileName(nudeWavName):
        counter = 0
        while True:
            counter = counter + 1
            myNewWavName = newWavName(nudeWavName, counter)
            if (fileExists(myNewWavName)) == False:
                break
        return myNewWavName
        
    #--------------------------Text to Speech--------------------------------------
    #import sys
    #    sys.path.append('/home/pi/.local/lib/python3.9/site-packages')
    
    import pyttsx3
    _ttsEngine = pyttsx3.init()
    _ttsEngine.setProperty('rate', 140)    # Speed percent (can go over 100)
    _ttsEngine.setProperty('volume', 1)  # Volume 0-1
    _ttsEngine.setProperty('voice', "german+f2") #sprache auf Deutsch ändern

    def ttsEngine(textToSay):
        print(textToSay)
        _ttsEngine.say(textToSay)
        #_ttsEngine.startLoop(False)
        _ttsEngine.runAndWait()
    #--------------------------Relay-----------------------------------------------
    import RPi.GPIO as GPIO
    from threading import Thread
    from threading import Event

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
        
    #---------------------------Ringing------------------------------------
    #from time import sleep
    ringTone = "/home/pi/telefono/relevant/telephone-ring-02.wav"

    def ringing(callingFile_):
        activateSpeaker()
        playFile(ringTone, PickUp) #hört auf wenn PickUp == True
        idleSpeaker()
        sleep(1) #test
        playFileNeg(callingFile_, PickUp) #hört auf wenn PickUp == False
        
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
    
    def callInQue(queFileAdress, nudeWavName):
        callingFileNumber = returnFileText(queFileAdress)
        callingFile = newWavName(nudeWavName, callingFileNumber)
        
        if callingFileNumber != "":
            print("ringing Que!!")
            ringing(callingFile)
            overWriteFile(queFileAdress, "")
        
    
    def getWeekDayInt():
        now = datetime.now()
        return now.weekday()
            

    #---------------------------acuteMessage-----------------------------------------------
    def findHighestMessage(nudeWavName): #gibt den Namen der höchsten existierenden Datei zurück
        counter = 0
        while True:
            countedWavName = newWavName(nudeWavName, counter)
            if fileExists(countedWavName) == False: #sucht die erste Datei die nicht existiert
                print("Höchste Nachricht: " + newWavName(nudeWavName, counter - 1))
                return newWavName(nudeWavName, counter - 1)  
            counter = counter + 1

    def findHighestMessageNumber(nudeWavName): #gibt den Namen der höchsten existierenden Datei zurück
        counter = 0
        while True:
            countedWavName = newWavName(nudeWavName, counter)
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
    
    
    def shout(wavName):
        activateSpeaker()
        sleep(2)
        playFile(wavName, PickUp) #hört auf wenn PickUp == True
        idleSpeaker()
        

    #---------------------------Menu-------------------------------------------------------
        
        
        
    def uhrzeitAnsagen():
        now = datetime.now()
        tag = str(now.strftime("%d"))
        monat = str(now.strftime("%m"))
        jahr = str(now.strftime("%Y"))
        stunde = str(now.strftime("%H"))
        minute = str(now.strftime("%M"))
        timeInWords = "Es ist " + stunde + "Uhr " + minute + " am " + tag + "." + monat + "." + jahr + "."
        
        ttsEngine(timeInWords)
        
    supperPrayers = [101, 102, 103, 104, 105]
    def zufaelligesGebet(nudeWavName):
        now = datetime.now()
        second = now.strftime("%S")
        seed(second)
        maxPrayer = len(supperPrayers) - 1
        randPrayerNumber = randint(0, maxPrayer)

        print("playing: " + str(randPrayerNumber))
        supperPrayerNumber = supperPrayers[randPrayerNumber]
        
        supperPrayerName = newWavName(nudeWavName, supperPrayerNumber)
        #print(supperPrayerName)
        playFileNeg(supperPrayerName, PickUp)
    
    gebetswuerfelListe = [201, 202, 203, 204, 205, 206]
    def gebetswuerfel(nudeWavName):
        now = datetime.now()
        second = now.strftime("%S")
        seed(second)
        maxPrayer = len(gebetswuerfelListe) - 1
        randPrayerNumber = randint(0, maxPrayer)

        print("playing: " + str(randPrayerNumber))
        supperPrayerNumber = gebetswuerfelListe[randPrayerNumber]
        
        supperPrayerName = newWavName(nudeWavName, supperPrayerNumber)
        #print(supperPrayerName)
        playFileNeg(supperPrayerName, PickUp)
        
        
    paterListe = [2, 10, 11, 19, 22, 26, 30, 88]
    def randomPater(nudeWavName):
        now = datetime.now()
        second = now.strftime("%S")
        seed(second)
        maxPrayer = len(paterListe) - 1
        randPrayerNumber = randint(0, maxPrayer)

        print("playing: " + str(randPrayerNumber))
        supperPrayerNumber = paterListe[randPrayerNumber]
        
        supperPrayerName = newWavName(nudeWavName, supperPrayerNumber)
        #print(supperPrayerName)
        playFileNeg(supperPrayerName, PickUp)
        
    #______________________________________________________________________________________
    #---------------------------Program----------------------------------------------------


    DialCounter = Button(2) #Zähler für die gewählte Zahl (rot)
    DialInUse = Button(26) #Wählscheibe wird benutzt (grau)(weiß im Tel)
    PickUp = Button(18) #wenn der Hörer aufgenommen ist (Orange, mit Blauem Kabel aus dem Telefon)
    ButtonLeft = Button(3) #Linker knopf (violett)red = Button(2) #Zähler für die gewählte Zahl (rot)(grün Gestr.)
    ButtonMiddle = Button(27) #Mittlerer Knopf
    SpeakerSwich = Button(17) #Rechter Kippschalter (grüner Anschluss)
    led = LED(20)
    
    

    nudeWavName = "/home/pi/telefono/recording"       #WavDateiname ohne nummer und .wav
    queFileAdress = "/home/pi/telefono/relevant/queFile.txt"
    
    essenIstFertig1830 = newWavName(nudeWavName, 1830)
    wucher1930 = newWavName(nudeWavName, 1930)
    tagesschau2000 = newWavName(nudeWavName, 2014)
    
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
                        #ttsEngine("Spiele Aufnahme Nr.: " + dialedNumber)
                        oldWavName = newWavName(nudeWavName, dialedNumber)
                        playFileNeg(oldWavName, PickUp) #hört auf wenn PickUp == False
                
            if ButtonLeft.is_pressed:          #Aufnahme Starten
                pygame.mixer.music.stop() #Freiton wird unterbrochen
                myNewWavName = findNewFileName(nudeWavName)

                rec = Recorder(channels=2)
                newRecordingNumber = findHighestMessageNumber(nudeWavName) + 1
                with rec.open(myNewWavName, 'wb') as recfile2:
                    ttsEngine("Aufnahme Nr.: " + str(newRecordingNumber) + " wird gestartet") #ansage welche Aufnahme es ist
                    recfile2.start_recording()
                    recordingTime = 0
                    led.on()
                    while True: 
                        time.sleep(0.1)
                        recordingTime = recordingTime + 1
                        if recordingTime > maxRecordingTime:    # beenden wenn mehr als 2min aufgenommen wurde
                            led.off()
                            recfile2.stop_recording()
                            ttsEngine("Aufnahme Nr.: " + str(newRecordingNumber) + "wegen overtime beendet.")
                            break
                        if (PickUp.is_pressed == False) or ButtonLeft.is_pressed:
                            led.off()
                            print("Aufnahme Nr.: " + str(newRecordingNumber) + " beendet.")
                            recfile2.stop_recording()
                            sleep(2) #button release Time
                            break
                        if ButtonMiddle.is_pressed:      #alte Aufnahme auswählen
                            led.off()
                            ttsEngine("Aufnahme Nr.: " + str(newRecordingNumber) + " abgebrochen")
                            recfile2.stop_recording()
                            delFile(myNewWavName)
                            sleep(2) #button release Time
                            break
            
            if ButtonMiddle.is_pressed:    
                pygame.mixer.music.stop() #Freiton wird unterbrochen
                ttsEngine("Menü wird geöffnet.")
                dialedOption = wait_for_digit(PickUp)
                if dialedOption == 0:
                    print("uhrzeit ansagen")
                    uhrzeitAnsagen()
                elif dialedOption == 1:
                    zufaelligesGebet(nudeWavName)
                elif dialedOption == 2:
                    gebetswuerfel(nudeWavName)
                elif dialedOption == 3:
                    randomPater(nudeWavName)
                else:
                    ttsEngine("Das habe ich nicht verstanden. Auf wiederhören")
                    
            
            if pygame.mixer.music.get_busy() == False: #wenn der Freiton noch nicht spielt
                playFile0("/home/pi/telefono/relevant/US_dial_tone.ogg.wav")  #Freiton 
            
        pygame.mixer.music.stop() #Freiton wird unterbrochen

        
        
        #-------------------------Klingelroutine-------------------------------------------
        if callRoutine() == True:
            print("ringing!!!!!!!")
            callingFile = findRandomMessage() #zufällige Datei die anruft
            ringing(callingFile) 
            
        callInQue(queFileAdress, nudeWavName)
        
        weekDayInt = getWeekDayInt()
        if weekDayInt > 0 and weekDayInt < 4: #von Dienstag bis Freitag Wahr
            if getTimeInt() == 183000:
                shout(essenIstFertig1830)
            if getTimeInt() == 193000:
                shout(wucher1930) 
        if getTimeInt() == 200000:
            shout(tagesschau2000)
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
except Exception as Argument:
 
     # creating/opening a file
     f = open("home/pi/telefono/relevant/telefonoCrashLog.txt", "a")
 
     # writing in the file
     f.write(str(Argument))
      
     # closing the file
     f.close()
