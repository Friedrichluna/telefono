try:
	#!/usr/bin/python3

	from flask import Flask, redirect, url_for, render_template, request
	from os import listdir
	import os
	from os.path import isfile, join
	import pickle
	import numpy
	import psutil




	def overWriteFile(fileName, writtenText):
		file1 = open(fileName,"w")
		file1.write(str(writtenText))
		file1.close()

	def fileNumbers():
		fileNameList = [f for f in listdir("/home/pi/telefono") if isfile(join("/home/pi/telefono", f))]
		fileNameList = [i.replace('recording', '') for i in fileNameList]
		fileNameList = [i.replace('.wav', '') for i in fileNameList]
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
		file = open('/home/pi/telefono/relevant/recording_names', 'wb')
		pickle.dump(data, file)
		file.close()

	def dePickleData():
		file = open('/home/pi/telefono/relevant/recording_names', 'rb')
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
		hdd = psutil.disk_usage('/')
		return round(hdd.free / (2**30), 2)



	queFileAdress = "/home/pi/telefono/relevant/queFile.txt"


	def home():
		if request.method == "POST":
			requested_number = request.form["nm"]
			print(requested_number)
			overWriteFile(queFileAdress, requested_number)
			return render_template("index.html", content = requested_number)
		else:
			return render_template("index.html")

	def list():

		testlist = fileNumbers()
		messageNamesList = getMessageNames()

		return render_template("list.html", testlist = testlist, messageNamesList = messageNamesList, str = str)

	def edit_value(index):
		if request.method == 'POST':
			new_value = request.form['new_value']
			messageNameList[index] = new_value

			pickleData(messageNameList)

			return redirect('/list')
		return render_template('edit.html', index=index, value=messageNameList[index])

	def get_value():
		# Get the selected button value from the frontend
		requested_number = request.form['selected_value']
		# Process the selected value as needed
		overWriteFile(queFileAdress, requested_number)
		return redirect('/list') #jsonify({'message': 'Value received successfully'})



	def upload_page():
		diskSpace = getFreeDiskSpace()
		return render_template('upload.html', diskSpace = diskSpace)

	UPLOAD_FOLDER = "/home/pi/telefono"

	def upload_file():
		uploaded_file = request.files['file']
		requested_number = request.form["requestedNumber"]


		if number_already_exists(requested_number):
			return render_template("upload.html", content ='Nummer {} existiert bereits!'.format(requested_number))
		if uploaded_file.filename.endswith(".wav") == False:
			return render_template("upload.html", content = 'Bitte nur .wav hochladen!')

		if (uploaded_file.filename != '') and (requested_number != ""):
			file_path = UPLOAD_FOLDER + "/recording" + str(requested_number) + ".wav"
			uploaded_file.save(file_path)
			print("test")
			return render_template("upload.html", content ='erfolgreich unter {} gespeichert!'.format(file_path))
		return redirect("/upload")

	def main ():
		initMessageNames()

		app = Flask(__name__)
		app.add_url_rule ("/", "home", home, methods=["POST", "GET"])
		app.add_url_rule ("/list", "list", list)
		app.add_url_rule ("/edit/<int:index>", "edit_value", edit_value, methods=["GET", "POST"])
		app.add_url_rule ("/get_value", "get_value", get_value, methods=['POST'])
		app.add_url_rule ("/upload", "upload_page", upload_page)
		app.add_url_rule ("/upload", "upload_file", upload_file, methods=["POST"])

		app.run(debug=True, host='0.0.0.0')

	if __name__ == "__main__":
		main ()

except Exception as Argument:

	# creating/opening a file
	f = open("home/pi/telefono/relevant/telefonoCrashLog.txt", "a")

	# writing in the file
	f.write(str(Argument))

	# closing the file
	f.close()
