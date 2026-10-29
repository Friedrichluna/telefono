## Process this file with automake to produce Makefile.in

pkgpython_PYTHON =
pkgpython_PYTHON += src/__init__.py
pkgpython_PYTHON += src/__main__.py
pkgpython_PYTHON += src/audio.py
pkgpython_PYTHON += src/button.py
pkgpython_PYTHON += src/config.py
pkgpython_PYTHON += src/diagnose.py
pkgpython_PYTHON += src/dial.py
pkgpython_PYTHON += src/event_queue.py
pkgpython_PYTHON += src/history.py
pkgpython_PYTHON += src/ipc.py
pkgpython_PYTHON += src/network.py
pkgpython_PYTHON += src/number.py
pkgpython_PYTHON += src/player.py
pkgpython_PYTHON += src/recorder.py
pkgpython_PYTHON += src/speaker.py
pkgpython_PYTHON += src/volume.py

webappdir = $(pkgpythondir)/webapp
webapp_PYTHON =
webapp_PYTHON += src/webapp/__init__.py
webapp_PYTHON += src/webapp/__main__.py
webapp_PYTHON += src/webapp/status.py
webapp_PYTHON += src/webapp/webapp.py

nodist_pkgpython_PYTHON =
nodist_pkgpython_PYTHON += CONSTANTS.py

noinst_PYTHON =
noinst_PYTHON += src/CONSTANTS.py.in


edit = sed -e 's|@pkgdatadir[@]|$(pkgdatadir)|g' \
           -e 's|@pkglocalstatedir[@]|$(pkglocalstatedir)|g' \
           -e 's|@templatedir[@]|$(templatedir)|g' \
           -e 's|@staticdir[@]|$(staticdir)|g' \
           -e 's|@sysconfdir[@]|$(sysconfdir)|g' \
           -e 's|@pkglibexecdir[@]|$(pkglibexecdir)|g' \
           -e 's|@vcs_version[@]|'`cat vcs_version`'|g'

all: CONSTANTS.py

CONSTANTS.py: $(srcdir)/src/CONSTANTS.py.in Makefile vcs_version
	$(MKDIR_P) src
	rm -f $@ $@.tmp
	$(edit) $< >$@.tmp

	chmod +x $@.tmp
	chmod a-w $@.tmp
	mv $@.tmp $@

vcs_version:
	git describe --long --tags --dirty --always > vcs_version

CLEANFILES = CONSTANTS.py vcs_version


# finding the webapp: telefono.local (mDNS) and a WLAN hotspot when no
# known WLAN is in range, see tools/telefono-net.in; run by
# telefono-mdns.service and telefono-hotspot.service (below)
nodist_pkglibexec_SCRIPTS = telefono-net

telefono-net: $(srcdir)/tools/telefono-net.in Makefile vcs_version
	rm -f $@ $@.tmp
	$(edit) $(srcdir)/tools/telefono-net.in >$@.tmp
	chmod +x $@.tmp
	chmod a-w $@.tmp
	mv $@.tmp $@

telefono-mdns.service: $(srcdir)/telefono-mdns.service.in Makefile vcs_version
	rm -f $@ $@.tmp
	$(edit) $(srcdir)/telefono-mdns.service.in >$@.tmp
	mv $@.tmp $@

telefono-hotspot.service: $(srcdir)/telefono-hotspot.service.in Makefile vcs_version
	rm -f $@ $@.tmp
	$(edit) $(srcdir)/telefono-hotspot.service.in >$@.tmp
	mv $@.tmp $@

CLEANFILES += telefono-net telefono-mdns.service telefono-hotspot.service
EXTRA_DIST = tools/telefono-net.in telefono-mdns.service.in telefono-hotspot.service.in

# the webapp in service browsers (avahi reads it at once)
avahiservicedir = $(sysconfdir)/avahi/services
dist_avahiservice_DATA = data/avahi/telefono.service


dist_pkgdata_DATA =
dist_pkgdata_DATA += data/startup.wav
dist_pkgdata_DATA += data/shutdown.wav
dist_pkgdata_DATA += data/ring.wav

templatedir = $(pkgdatadir)/templates
dist_template_DATA =
dist_template_DATA += src/webapp/templates/base.html
dist_template_DATA += src/webapp/templates/diagnose.html
dist_template_DATA += src/webapp/templates/edit.html
dist_template_DATA += src/webapp/templates/help.html
dist_template_DATA += src/webapp/templates/index.html
dist_template_DATA += src/webapp/templates/list.html
dist_template_DATA += src/webapp/templates/message.html
dist_template_DATA += src/webapp/templates/say.html
dist_template_DATA += src/webapp/templates/status.html
dist_template_DATA += src/webapp/templates/upload.html
dist_template_DATA += src/webapp/templates/volume.html

staticdir = $(pkgdatadir)/static
dist_static_DATA =
dist_static_DATA += src/webapp/static/favicon.ico

pkglocalstatedir = $(localstatedir)/$(PACKAGE)
dist_pkglocalstate_DATA =
dist_pkglocalstate_DATA += data/records.list.example

# the hardware configuration of a phone is $(sysconfdir)/telefono.conf,
# made from this example (only the example is installed, so updates
# never overwrite it)
dist_sysconf_DATA =
dist_sysconf_DATA += data/telefono.conf.example

# browsers only allow the microphone (recording in the webapp) on https
# pages, so the webapp is also served over https with a self-signed
# certificate of this phone; it is made at the first install (openssl,
# never in git, never replaced), the key is only readable by root and
# the group of the service's user (User= in telefono.service)
https_cert = $(sysconfdir)/telefono.crt
https_key = $(sysconfdir)/telefono.key

install-data-local:
	@if test -e "$(DESTDIR)$(https_key)"; then \
	  echo "keeping the https certificate $(DESTDIR)$(https_cert)"; \
	elif ! command -v openssl >/dev/null; then \
	  echo "WARNING: openssl is missing, the webapp has no https"; \
	else \
	  host=`hostname`; \
	  group=`sed -n 's/^User=//p' $(srcdir)/telefono.service`; \
	  $(MKDIR_P) "$(DESTDIR)$(sysconfdir)" && \
	  (umask 077 && openssl req -x509 -newkey ec \
	    -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 3650 \
	    -subj "/CN=$$host" \
	    -addext "subjectAltName=DNS:$$host,DNS:$$host.local" \
	    -keyout "$(DESTDIR)$(https_key).tmp" \
	    -out "$(DESTDIR)$(https_cert).tmp" 2>/dev/null) && \
	  chmod 644 "$(DESTDIR)$(https_cert).tmp" && \
	  { chgrp "$$group" "$(DESTDIR)$(https_key).tmp" && \
	    chmod 640 "$(DESTDIR)$(https_key).tmp" || \
	    echo "WARNING: $(DESTDIR)$(https_key) is not readable by $$group"; } && \
	  mv "$(DESTDIR)$(https_cert).tmp" "$(DESTDIR)$(https_cert)" && \
	  mv "$(DESTDIR)$(https_key).tmp" "$(DESTDIR)$(https_key)" && \
	  echo "made the https certificate $(DESTDIR)$(https_cert)" || \
	  { rm -f "$(DESTDIR)$(https_cert).tmp" "$(DESTDIR)$(https_key).tmp"; \
	    echo "WARNING: making the https certificate failed, the webapp has no https"; }; \
	fi

# the hotspot's password ($(sysconfdir)/telefono-hotspot.conf) is kept
uninstall-local:
	rm -f "$(DESTDIR)$(https_cert)" "$(DESTDIR)$(https_key)"
	rm -f "$(DESTDIR)/etc/NetworkManager/dnsmasq-shared.d/telefono.conf"

dist_doc_DATA =
dist_doc_DATA += README.md
dist_doc_DATA += todo.txt
dist_doc_DATA += docs/circuit_diagram.png



if HAVE_SYSTEMD
systemd_DATA = telefono.service
nodist_systemd_DATA = telefono-mdns.service telefono-hotspot.service

# the network services are restarted if they run (new version), telefono
# itself is not
if INSTALL_SYSTEMD_SERVICE
install-data-hook:
	systemctl daemon-reload
	systemctl enable telefono telefono-mdns telefono-hotspot
	systemctl try-restart telefono-mdns telefono-hotspot

# a running hotspot is ended (NetworkManager then connects a known WLAN)
uninstall-hook:
	systemctl disable --now telefono-mdns telefono-hotspot
	-nmcli connection delete id telefono-hotspot 2>/dev/null
	systemctl daemon-reload
	systemctl disable telefono
endif
endif

EXTRA_DIST += telefono.service

ACLOCAL_AMFLAGS = --install -I build-macro

AM_DISTCHECK_CONFIGURE_FLAGS = --with-systemddir=$$dc_install_base$(systemddir) --disable-service


run: install
	systemctl restart telefono

status: run
	sleep 3
	systemctl status telefono --full

.PHONY: run status
