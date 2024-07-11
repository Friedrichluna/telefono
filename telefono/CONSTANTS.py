#!/usr/bin/python3
# -*- coding: utf-8 -*-

BASE_DIR = "/home/pi/telefono"
DATA_DIR = BASE_DIR + "/data"

RECORD_DIR = DATA_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RING_FILE = DATA_DIR + "/telephone-ring-02.wav"
DIAL_TONE_FILE = DATA_DIR + "/US_dial_tone.ogg.wav"

RECORD_LIST_FILE = DATA_DIR + "/records.list"
BACKUP_EXT = ".bak"

UPLOAD_DIR = DATA_DIR

WEBAPP_EXEC = ("python3", "-m", "telefono.webapp")

FLASK_DEBUG = True
FLASK_IP = "0.0.0.0"
FLASK_PORT = 5000

TELEFONO_LOG_FILE = DATA_DIR + "/telefono.log"
WEBAPP_LOG_FILE = DATA_DIR + "/webapp.log"
