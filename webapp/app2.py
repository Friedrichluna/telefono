#!/usr/bin/python3

import os
import time

from flask import Flask, redirect, render_template, request

import linkat
import psutil


BASE_DIR = "/home/pi/telefono/telefono"

FLASK_DEBUG = True
FLASK_IP = "0.0.0.0"
FLASK_PORT = 5000

RECORD_DIR = BASE_DIR
RECORD_PREFIX = "recording"
RECORD_SUFFIX = ".wav"

RECORD_LIST_FILE = BASE_DIR + "/relevant/records.list"
BACKUP_EXT = ".bak"

SERVER_QUEUE_FILE = BASE_DIR + "/relevant/queFile.txt"

UPLOAD_DIR = BASE_DIR

LOG_FILE = BASE_DIR + "/relevant/webapp.log"


class RecordIndexFile ():
	def __init__ (self, filename:str):
		self.__data = dict ()
		self.__prevent_sync = False

		self.__filename = filename

		# previously crashed while writing
		# restore backup
		if not os.path.exists (self.__filename) \
		and os.path.exists (self.__filename + BACKUP_EXT):
			print ("restoring backup file")
			os.rename (self.__filename + BACKUP_EXT,
			           self.__filename)

		# load file
		if os.path.exists (self.__filename):
			with open (self.__filename, "rt") as f:
				self.__load (f)
		else:
			os.mknod (self.__filename)

		return None

	def __contains__ (self, key):
		return self.__data.get (key, (..., False))[1]

	def __getitem__ (self, key):
		return self.__data.__getitem__ (key)[0]

	def __setitem__ (self, key, value):
		if int != type (key):
			raise TypeError (
			      "Invalid key %s, must be int not %s."
			      % (repr(key), type (key)))

		if str != type (value):
			raise TypeError (
			      "Invalid value %s, must be str not %s."
			      % (repr(value), type (value)))

		ret = self.__data.__setitem__ (key, (value, False))

		self.sync_data ()
		return ret

	def __delitem__ (self, key):
		ret = self.__data.__delitem__ (key)

		self.sync_data ()
		return ret


	def __iter__ (self):
		l = list(self.keys())
		l.sort()
		return iter(l)

	def __len__ (self):
		length = 0
		for key, (value, exists) in self.__data.items ():
			if exists:
				length += 1
		return length

	def __reversed__ (self):
		raise NotImplementedError


	def clear (self):
		ret = self.__data.clear ()

		self.sync_data ()
		return ret

	def copy (self):
		c = RecordIndexFile ()
		c.__data = self.__data.copy ()
		return c

	def get (self, key, default=""):
		return self.__data.get (key, (default, ))[0]

	def items (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield (key, value)

	def keys (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield key

	def pop (self, key, *args, **kwargs):
		ret = self.__data.pop (key, *args, **kwargs)[0]

		self.sync_data ()
		return ret

	def popitem (self):
		ret = self.__data.popitem ()[0]

		self.sync_data ()
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

		ret = self.__data.setdefault (key, (default, False))

		self.sync_data ()
		return ret

	def update (self, *args, **kwargs):
		raise NotImplementedError

	def values (self):
		for key, (value, exists) in self.__data.items ():
			if exists:
				yield value

	def __load (self, _file):
		self.__prevent_sync = True

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

			# ignore empty names
			if not name:
				continue

			self[number] = name

		self.__prevent_sync = False
		return

	def __store (self, _file):

		_file.truncate ()

		keys = self.__data.keys ()
		keys = list (keys)
		keys.sort ()

		for key in keys:
			name = self[key].strip ()

			# ignore empty names
			if not name:
				continue

			_file.write (str (key))
			_file.write (": ")
			_file.write (name)
			_file.write ("\n")

		_file.flush ()
		return

	def __invalidate_fs (self):
		for key, (value, exists) in self.__data.items ():
			self.__data[key] = (value, False)
		return

	def __validate (self, key):
		self.setdefault (key)
		self.__data[key] = (self.__data[key][0], True)
		return

	def sync_data (self):
		if self.__prevent_sync:
			return

		# create temporary file
		fd = os.open (os.path.dirname (self.__filename),
		              os.O_TMPFILE | os.O_WRONLY,
		              mode=0o600)

		# create backup file
		if os.path.exists (self.__filename):
			os.rename (self.__filename,
			           self.__filename + BACKUP_EXT)

		# store into temporary file
		f = os.fdopen (fd, "wt")
		self.__store (f)

		# atomically link file
		linkat.link_at (linkat.AT_FDCWD, b"/proc/self/fd/%d" % fd,
		                linkat.AT_FDCWD, self.__filename.encode(),
		                linkat.AT_SYMLINK_FOLLOW)

		f.close ()

		return

	def sync_fs (self, directory:str=RECORD_DIR):
		self.__invalidate_fs ()

		for file in os.listdir (directory):
			path = os.path.join (directory, file)

			if os.path.isfile (path) \
			and file.startswith (RECORD_PREFIX) \
			and file.endswith (RECORD_SUFFIX):
				file = file[len(RECORD_PREFIX) :]
				file = file[: -len(RECORD_SUFFIX)]
				record = int (file)

				self.__validate (record)
		return


def overWriteFile(fileName, writtenText):
	file1 = open(fileName,"w")
	file1.write(str(writtenText))
	file1.close()

def getFreeDiskSpace():
	hdd = psutil.disk_usage (UPLOAD_DIR)
	return round(hdd.free / (2**30), 2)


class TelefonoWebApp (Flask):
	def __init__ (self, records):
		super ().__init__ (__name__)

		self.records = records

		self.add_url_rule ("/", "home", self.home, methods=["POST", "GET"])
		self.add_url_rule ("/list", "list", self.list)
		self.add_url_rule ("/edit/<int:index>", "edit_value", self.edit_value, methods=["GET", "POST"])
		self.add_url_rule ("/get_value", "get_value", self.get_value, methods=["POST"])
		self.add_url_rule ("/upload", "upload_page", self.upload_page)
		self.add_url_rule ("/upload", "upload_file", self.upload_file, methods=["POST"])
		return

	def home(self):
		if request.method == "POST":
			requested_number = request.form["nm"]
			print(requested_number)
			overWriteFile(SERVER_QUEUE_FILE, requested_number)
			return render_template("index.html", content = requested_number)
		else:
			return render_template("index.html")

	def list(self):
		self.records.sync_fs ()
		return render_template("list.html", records=self.records)

	def edit_value(self, index):
		if request.method == "POST":
			new_value = request.form["new_value"]
			self.records[index] = new_value

			return redirect("/list")
		return render_template("edit.html", index=index, value=self.records[index])

	def get_value(self):
		# Get the selected button value from the frontend
		requested_number = request.form["selected_value"]
		# Process the selected value as needed
		overWriteFile(SERVER_QUEUE_FILE, requested_number)
		return redirect("/list") #jsonify({"message": "Value received successfully"})



	def upload_page(self):
		diskSpace = getFreeDiskSpace()
		return render_template("upload.html", diskSpace = diskSpace)


	def upload_file(self):
		uploaded_file = request.files["file"]
		requested_number = request.form["requestedNumber"]

		if (not uploaded_file.filename) or (not requested_number):
			return redirect ("/upload")

		if not requested_number.isdecimal ():
			return render_template("upload.html", content ="Keine Nummer angegeben!".format(requested_number))

		requested_number = int(requested_number)

		if requested_number in self.records:
			return render_template("upload.html", content ="Nummer {} existiert bereits!".format(requested_number))
		if not uploaded_file.filename.endswith(".wav"):
			return render_template("upload.html", content = "Bitte nur .wav hochladen!")

		file_path = UPLOAD_DIR + "/" + RECORD_PREFIX + str(requested_number) + RECORD_SUFFIX
		uploaded_file.save(file_path)

		self.records.sync_fs ()
		print("test")
		return render_template("upload.html", content ="erfolgreich unter {} gespeichert!".format(file_path))

def main ():
	records = RecordIndexFile (RECORD_LIST_FILE)
	records.sync_fs ()

	app = TelefonoWebApp (records)
	app.run(host=FLASK_IP, port=FLASK_PORT, debug=FLASK_DEBUG)

if __name__ == "__main__":
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
