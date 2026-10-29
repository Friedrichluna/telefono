#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import ssl
import sys
import threading

from werkzeug.serving import ThreadedWSGIServer

from ..CONSTANTS import FLASK_DEBUG
from ..CONSTANTS import FLASK_IP
from ..CONSTANTS import FLASK_PORT

from ..CONSTANTS import FLASK_HTTPS_PORT
from ..CONSTANTS import FLASK_HTTPS_CERT
from ..CONSTANTS import FLASK_HTTPS_KEY
from ..CONSTANTS import FLASK_HTTPS_TIMEOUT

from ..CONSTANTS import UPLOAD_DIR

from ..ipc import IPC_Client

from .webapp import TelefonoWebApp


# werkzeug's https server does the TLS handshake in accept (), so one
# client that connects and sends nothing would block it for everyone;
# here the handshake runs on the first read in the connection's thread
class HTTPSServer (ThreadedWSGIServer):
	def __init__ (self, host:str, port:int, app, context:ssl.SSLContext):
		super ().__init__ (host, port, app)

		self.socket = context.wrap_socket (self.socket,
		                                   server_side=True,
		                                   do_handshake_on_connect=False)

		# wsgi.url_scheme https, and werkzeug logs TLS errors
		# (e.g. a browser that does not accept the certificate)
		# instead of raising them
		self.ssl_context = context
		return

	def get_request (self):
		connection, address = self.socket.accept ()
		connection.settimeout (FLASK_HTTPS_TIMEOUT)
		return connection, address


# the https server in a thread, None if there is no certificate
# (see Makefile.am) or it can not be used; http works without it
def start_https (app, log):
	if not os.path.exists (FLASK_HTTPS_CERT):
		log.warning ("no certificate %s, no https (recording in the"
		             " browser only works on localhost)", FLASK_HTTPS_CERT)
		return None

	try:
		context = ssl.SSLContext (ssl.PROTOCOL_TLS_SERVER)
		context.load_cert_chain (FLASK_HTTPS_CERT, FLASK_HTTPS_KEY)
		server = HTTPSServer (FLASK_IP, FLASK_HTTPS_PORT, app, context)

	except (OSError, ssl.SSLError) as error:
		log.error ("https on port %d failed: %s", FLASK_HTTPS_PORT, error)
		return None

	thread = threading.Thread (target=server.serve_forever,
	                           name="https", daemon=True)
	thread.start ()

	log.info ("https on port %d", FLASK_HTTPS_PORT)
	return server


def main ():
	if len(sys.argv) < 2:
		print ("no communication socket provided")
		sys.exit (1)

	if not sys.argv[1].isdecimal ():
		print ("invalid fileno")
		sys.exit (1)

	# setup connection to server
	ipc = IPC_Client (int(sys.argv[1]))

	app = TelefonoWebApp (ipc)

	# the debug reloader would start a second process (and port)
	if not FLASK_DEBUG and start_https (app, app.logger):
		app.https_port = FLASK_HTTPS_PORT

	app.run(host=FLASK_IP, port=FLASK_PORT, debug=FLASK_DEBUG)

if __name__ == "__main__":
	main ()
