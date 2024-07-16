#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

from ..CONSTANTS import FLASK_DEBUG
from ..CONSTANTS import FLASK_IP
from ..CONSTANTS import FLASK_PORT

from ..CONSTANTS import UPLOAD_DIR

from .records import Records
from ..ipc import IPC_Client

from .webapp import TelefonoWebApp


def main ():
	if len(sys.argv) < 2:
		print ("no communication socket provided")
		sys.exit (1)

	if not sys.argv[1].isdecimal ():
		print ("invalid fileno")
		sys.exit (1)

	records = Records ()
	records.sync_fs ()

	# setup connection to server
	ipc = IPC_Client (int(sys.argv[1]))

	app = TelefonoWebApp (records, ipc)
	app.run(host=FLASK_IP, port=FLASK_PORT, debug=FLASK_DEBUG)

if __name__ == "__main__":
	main ()
