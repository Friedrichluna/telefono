#!/usr/bin/python3

from flask import Flask, redirect, url_for, render_template, request
from os import listdir
import os
from os.path import isfile, join
import pickle
import numpy
import psutil


BASE_DIR = "/home/pi/telefono"

RECORD_DIR = BASE_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RECORD_LIST_FILE = BASE_DIR + "/relevant/recording_names"

SERVER_QUEUE_FILE = BASE_DIR + "/relevant/queFile.txt"

UPLOAD_DIR = BASE_DIR

LOG_FILE = BASE_DIR + "/relevant/telefonoCrashLog.txt"


def overWriteFile(fileName, writtenText):
	file1 = open(fileName,"w")
	file1.write(str(writtenText))
	file1.close()

def fileNumbers():
	fileNameList = [f for f in listdir(RECORD_DIR) if isfile(join(RECORD_DIR, f))]
	fileNameList = [i.replace(RECORD_PREFIX, "") for i in fileNameList]
	fileNameList = [i.replace(RECORD_SUFFIX, "") for i in fileNameList]
	fileNumberList = [eval(i) for i in fileNameList]
	fileNumberList.sort()

	return fileNumberList

messageNameList = []
def initMessageNames():
	fileNumberList = fileNumbers()
	global messageNameList
	messageNameList = dePickleData()

	if len(messageNameList) < max(fileNumberList):
		for i in range(max(fileNumberList)):
			messageNameList.append("")



def getMessageNames():
	global messageNameList
	return messageNameList

def pickleData(data):
	file = open(RECORD_LIST_FILE, "wb")
	pickle.dump(data, file)
	file.close()

def dePickleData():
	file = open(RECORD_LIST_FILE, "rb")
	data = pickle.load(file)
	file.close()
	return data

def number_already_exists(requested_number):
	fileNumberList = fileNumbers()
	for i in fileNumbers():
		if str(i) == str(requested_number):
			return True
	return False

def getFreeDiskSpace():
	hdd = psutil.disk_usage("/")
	return round(hdd.free / (2**30), 2)


def home():
	if request.method == "POST":
		requested_number = request.form["nm"]
		print(requested_number)
		overWriteFile(SERVER_QUEUE_FILE, requested_number)
		return render_template("index.html", content = requested_number)
	else:
		return render_template("index.html")

def list():

	testlist = fileNumbers()
	messageNamesList = getMessageNames()

	return render_template("list.html", testlist = testlist, messageNamesList = messageNamesList, str = str)

def edit_value(index):
	if request.method == "POST":
		new_value = request.form["new_value"]
		messageNameList[index] = new_value

		pickleData(messageNameList)

		return redirect("/list")
	return render_template("edit.html", index=index, value=messageNameList[index])

def get_value():
	# Get the selected button value from the frontend
	requested_number = request.form["selected_value"]
	# Process the selected value as needed
	overWriteFile(SERVER_QUEUE_FILE, requested_number)
	return redirect("/list") #jsonify({"message": "Value received successfully"})



def upload_page():
	diskSpace = getFreeDiskSpace()
	return render_template("upload.html", diskSpace = diskSpace)


def upload_file():
	uploaded_file = request.files["file"]
	requested_number = request.form["requestedNumber"]


	if number_already_exists(requested_number):
		return render_template("upload.html", content ="Nummer {} existiert bereits!".format(requested_number))
	if uploaded_file.filename.endswith(".wav") == False:
		return render_template("upload.html", content = "Bitte nur .wav hochladen!")

	if (uploaded_file.filename != "") and (requested_number != ""):
		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(requested_number) + RECORD_SUFFIX
		uploaded_file.save(file_path)
		print("test")
		return render_template("upload.html", content ="erfolgreich unter {} gespeichert!".format(file_path))
	return redirect("/upload")

def main ():
	initMessageNames()

	app = Flask(__name__)
	app.add_url_rule ("/", "home", home, methods=["POST", "GET"])
	app.add_url_rule ("/list", "list", list)
	app.add_url_rule ("/edit/<int:index>", "edit_value", edit_value, methods=["GET", "POST"])
	app.add_url_rule ("/get_value", "get_value", get_value, methods=["POST"])
	app.add_url_rule ("/upload", "upload_page", upload_page)
	app.add_url_rule ("/upload", "upload_file", upload_file, methods=["POST"])

	app.run(debug=True, host="0.0.0.0")

if __name__ == "__main__":
	try:
		main ()

	except Exception as Argument:
		# creating/opening a file
		f = open(LOG_FILE, "a")

		# writing in the file
		f.write(str(Argument))

		# closing the file
		f.close()
