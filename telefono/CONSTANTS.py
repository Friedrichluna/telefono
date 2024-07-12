#!/usr/bin/python3
# -*- coding: utf-8 -*-

BASE_DIR = "/home/pi/telefono"
DATA_DIR = BASE_DIR + "/data"

RECORD_DIR = DATA_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RING_FILE = DATA_DIR + "/ring.wav"
DIAL_FILE = DATA_DIR + "/dial.wav"
STARTUP_FILE = DATA_DIR + "/startup.wav"
SHUTDOWN_FILE = DATA_DIR + "/shutdown.wav"

RECORD_LIST_FILE = DATA_DIR + "/records.list"
BACKUP_EXT = ".bak"

UPLOAD_DIR = DATA_DIR

WEBAPP_EXEC = ("python3", "-m", "telefono.webapp")

FLASK_DEBUG = True
FLASK_IP = "0.0.0.0"
FLASK_PORT = 5000

MIN_HOUR = 15
MAX_HOUR = 21

MOAN_PROPABILITY = 0.1
