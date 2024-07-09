#!/usr/bin/python3
# -*- coding: utf-8 -*-

BASE_DIR = "/home/pi/telefono/data"

RECORD_DIR = BASE_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RING_FILE = BASE_DIR + "/relevant/telephone-ring-02.wav"
DIAL_TONE_FILE = BASE_DIR + "/relevant/US_dial_tone.ogg.wav"

RECORD_LIST_FILE = BASE_DIR + "/relevant/records.list"
BACKUP_EXT = ".bak"

UPLOAD_DIR = BASE_DIR

WEBAPP_EXEC = BASE_DIR + '/../telefono/webapp.py'

FLASK_DEBUG = True
FLASK_IP = "0.0.0.0"
FLASK_PORT = 5000

TELEFONO_LOG_FILE = BASE_DIR + "/relevant/telefono.log"
WEBAPP_LOG_FILE = BASE_DIR + "/relevant/webapp.log"
