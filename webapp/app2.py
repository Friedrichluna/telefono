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


class RecordIndexFile ():
	def __init__ (self, filename:str, legacy:bool=False):
		self.__data = dict ()
		self.__filename = filename
		self.__legacy = legacy

		if not legacy:
			if os.path.exists (self.__filename):
				with open (self.__filename, "rt") as f:
					self.__load (f)
			else:
				os.mknod (self.__filename)

		else:
			if os.path.exists (self.__filename):
				with open (self.__filename, "rb") as f:
					self.__load_legacy (f)

		return None

	def __contains__ (self, key):
		return self.__data.__contains__ (key)

	def __getitem__ (self, key):
		return self.__data.__getitem__ (key)

	def __setitem__ (self, key, value):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (value):
			raise TypeError (
			      "Invalid value %s, must be str not %s."
			      % (repr(value), type (value)))

		ret = self.__data.__setitem__ (key, value)

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret

	def __delitem__ (self, key):
		ret = self.__data.__delitem__ (key)

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret


	def __iter__ (self):
		return self.__data.__iter__ ()

	def __len__ (self):
		return self.__data.__len__ ()

	def __reversed__ (self):
		return self.__data.__reversed__ ()


	def clear (self):
		ret = self.__data.clear ()

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret

	def copy (self):
		c = RecordIndexFile ()
		c.__data = self.__data.copy ()
		return c

	def get (self, key, default=""):
		return self.__data.get (key, default)

	def items (self):
		return self.__data.items ()

	def keys (self):
		return self.__data.keys ()

	def pop (self, key, *args, **kwargs):
		ret = self.__data.pop (key, *args, **kwargs)

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret

	def popitem (self):
		ret = self.__data.popitem ()

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret

	def setdefault (self, key, default=""):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (default):
			raise TypeError (
			      "Invalid default %s, must be str not %s."
			      % (repr(default), type (default)))

		ret = self.__data.setdefault (key, default)

		if not self.__legacy:
			with open (self.__filename, "wt") as f:
				self.__store (f)

		else:
			with open (self.__filename, "wb") as f:
				self.__store_legacy (f)

		return ret

	# TODO: implement update

	def values (self):
		return self.__data.values ()

	def __load (self, _file):
		for lineno, line in enumerate (_file.readlines ()):

			# ignore commented lines
			index = line.find ("#")
			if (-1 != index):
				line = line[:index]

			# ignore empty lines
			if not line:
				continue

			index = line.find (":")
			if (-1 == index):
				print ("ignoring malformed line %d"
				       % (lineno+1))
				continue

			number = line[:index]
			name = line[index+1:]

			number = number.strip ()
			name = name.strip ()

			try:
				number = int (number)
			except ValueError:
				print ("Key is not a number!",
				       "Ignoring line")
				continue

			self[number] = name

		return

	def __load_legacy (self, _file):
		data = pickle.load (_file)

		for index, name in enumerate (data):

			# don't store empty values
			if name:
				# There are valid names with
				# a single space, so strip
				# can't be called earlier.
				self[index] = name.strip ()

		return

	def __store (self, _file):

		_file.truncate ()

		keys = self.keys ()
		keys = list (keys)
		keys.sort ()

		for key in keys:
			_file.write (str (key))
			_file.write (": ")
			_file.write (self[key])
			_file.write ("\n")

		_file.flush ()
		return

	def __store_legacy (self, _file):
		_file.truncate ()

		data = list ()

		last_key = max (self.keys (), default=None)
		if last_key is not None:
			for key in range (last_key+1):
				value = self.get (key, default=None)

				# existing empty key
				if "" == value:
					value = " "
				# nonexisting key
				elif None is value:
					value = ""

				data.append (value)

		pickle.dump (data, _file)
		_file.flush ()
		return


def overWriteFile(fileName, writtenText):
	file1 = open(fileName,"w")
	file1.write(str(writtenText))
	file1.close()

def fileNumbers():
	fileNameList = [f for f in listdir(RECORD_DIR) if isfile(join(RECORD_DIR, f))]
	fileNameList = [i.replace(RECORD_PREFIX, "") for i in fileNameList]
	fileNameList = [i.replace(RECORD_SUFFIX, "") for i in fileNameList]
	fileNumberList = [int(i) for i in fileNameList]
	fileNumberList.sort()

	return fileNumberList

def initMessageNames():
	fileNumberList = fileNumbers()

	global messageNameList
	messageNameList = RecordIndexFile (RECORD_LIST_FILE, legacy=True)

	# ensure that a name exists for each file
	for number in fileNumberList:
		messageNameList.setdefault (number)

def number_already_exists(requested_number):
	fileNumberList = fileNumbers()
	for i in fileNumbers():
		if str(i) == str(requested_number):
			return True
	return False

def getFreeDiskSpace():
	hdd = psutil.disk_usage (UPLOAD_DIR)
	return round(hdd.free / (2**30), 2)


def home():
	if request.method == "POST":
		requested_number = request.form["nm"]
		print(requested_number)
		overWriteFile(SERVER_QUEUE_FILE, requested_number)
		return render_template("index.html", content = requested_number)
	else:
		return render_template("index.html")

def _list():
	testlist = fileNumbers()

	return render_template("list.html", testlist = testlist, messageNamesList = messageNameList, str = str)

def edit_value(index):
	if request.method == "POST":
		new_value = request.form["new_value"]
		messageNameList[index] = new_value

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
	app.add_url_rule ("/list", "list", _list)
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
