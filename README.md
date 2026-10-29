# telefono
Ein wählscheibentelefon zu einer interaktiven Maschine umgebaut.
!!!wurde im Juli 2024 zu https://gitlab.mn.tu-dresden.de/josc941e/telefono geschoben und dort verbessert!!!

## Hint
Please install the git hooks under hooks/ for a working build.


## Funktionsweise
Wenn der Hörer abgenommen wird ist ein Freiton hörbar. Hier hat man mehrere Optionen:

Aufnahme:
Drückt man den linken Knopf wird eine Aufnahme gestartet, die Stimme sagt einem um welche Aufnahme es sich handelt. Wird der linke Knopf nochmal gedrückt oder der Hörer aufgelegt wird die Aufnahme gespeichert. Drückt man stattdessen den mittleren Knopf wird die Aufnahme Gelöscht.

Alte Aufnahme abspielen:
Fängt man an die Nummernscheibe zu bedienen wird der Freiton unterbrochen und man kann beliebig viele Zahlen wählen. Drückt man dann den linken Knopf wird die Aufnahme mit der entsprechenden Nummer abgespielt, sonst 4 Sekunden nach der letzten Ziffer. Ist die Nummer eindeutig (keine andere Nummer fängt mit diesen Ziffern an, z. B. 88), wird sofort nach der letzten Ziffer gewählt; fängt keine Nummer mit den gewählten Ziffern an, kommt sofort der Ton für eine nicht vergebene Nummer. Abschalten lässt sich das mit `DIAL_IMMEDIATE = False` in `src/CONSTANTS.py.in`.

Lautsprecher:
Mit dem Kippschalter rechts, kann man das Telefon auf laut oder leise schalten. Die Klingel ist immer Laut.

## Hardware-Konfiguration
Die Telefone sind unterschiedlich verdrahtet, bei manchen sind einzelne Eingänge (Hörer, Knöpfe, ...) invertiert. Das wird pro Telefon in `/etc/telefono.conf` eingestellt (bei `../configure --sysconfdir=/etc`, sonst `<prefix>/etc/telefono.conf`), nicht im Code:

```
sudo cp /etc/telefono.conf.example /etc/telefono.conf
sudo nano /etc/telefono.conf
sudo systemctl restart telefono
```

Ein Eingang muss invertiert werden (`yes`), wenn er in Ruhe (Hörer aufgelegt, Knöpfe losgelassen) als gedrückt gelesen wird. Der Ausgang zum Lautsprecher-Relais (GPIO 4, schaltet den Verstärker des Lautsprechers) ist ohne Einstellung bei low an; `speaker_relay = yes` dreht das um (high ist an), wenn der Lautsprecher bei aufgelegtem Hörer und Schalter auf leise an ist (bzw. beim Relais-Test aus). Ohne die Datei ist nichts invertiert. Das Journal zeigt, was gelesen wurde: `journalctl -u telefono | grep inverted` (z. B. `inverted pins (/etc/telefono.conf): hook, left, middle, speaker_relay`).

Einfacher geht es mit der Seite **Hardware-Test** der Webapp (`http://<telefon>:5000/diagnose`): Sie zeigt live für jeden Eingang den Pegel am GPIO, die Einstellung aus `telefono.conf` und was telefono daraus liest (beim Relais, ob es mit der Einstellung an oder aus ist), und sagt, welche Zeile zu ändern ist, wenn ein Eingang in Ruhe falsch gelesen wird. Sie liest die GPIO-Register direkt (`/dev/gpiomem`, nur lesend), funktioniert also auch bei abgehobenem Hörer. Die gewählte Ziffer zeigt, ob die Wählscheibe richtig zählt; LED und Lautsprecher-Relais lassen sich testen, wenn das Telefon frei ist.

## Lautstärke
Auf der Seite **Lautstärke** der Webapp (`http://<telefon>:5000/volume`) stellt man Hörer, Lautsprecher und Klingeln ein und kann je einen Testton abspielen (nur wenn das Telefon frei ist). Laut Schaltplan geht der linke Kanal der USB-Soundkarte zum Verstärker des Lautsprechers (den das Relais an GPIO 4 einschaltet), der rechte zum Hörer; die Regler setzen die beiden Kanäle des Lautstärke-Reglers der Karte (`amixer`, hier `Speaker Playback Volume`), sofort und auch während telefoniert wird. Das Klingeln ist zusätzlich ein Anteil (ffplay, ohne Einstellung 70 %). Die Werte (Prozent) stehen in `/var/telefono/volume.json`, telefono setzt sie beim Start; ohne die Datei bleibt die Karte so, wie `alsactl` sie beim Booten wiederhergestellt hat. Ist ein Telefon anders verdrahtet (Testton im falschen Ausgang), `MIXER_SPEAKER_CHANNEL` und `MIXER_HANDSET_CHANNEL` in `src/CONSTANTS.py.in` tauschen.

## Aufnehmen im Browser (https)
Auf der Seite **Aufnehmen** der Webapp nimmt man mit dem Mikrofon von Laptop oder Handy auf. Browser erlauben das Mikrofon nur über https (oder auf localhost), deshalb läuft die Webapp zusätzlich auf `https://<telefon>:5443` mit einem selbst ausgestellten Zertifikat. `sudo make install` erzeugt es einmalig mit `openssl` (`/etc/telefono.crt`, `/etc/telefono.key`, nur für root und die Gruppe des Dienst-Benutzers lesbar); ohne Zertifikat gibt es nur http. Neues Zertifikat (z. B. nach Änderung des Hostnamens): beide Dateien löschen, `sudo make install`, `sudo systemctl restart telefono`. Ohne https kann man auf dem Handy mit dessen Aufnahme-App aufnehmen und die Datei speichern. Hochgeladene Dateien (.m4a, .ogg, .opus, .webm, .3gp, .amr, .flac, .wav, ...) wandelt `ffmpeg` in .mp3 um.

## Webapp finden (telefono.local, eigenes WLAN)
Im Heimnetz ist die Webapp unter `http://telefono.local:5000` (und `https://telefono.local:5443`) erreichbar, zusätzlich wie bisher unter `http://<hostname>.local:5000`; der Hostname bleibt unverändert. Das macht der Dienst `telefono-mdns` (`tools/telefono-net.in`, braucht `avahi-daemon` und `python3-dbus`): Er meldet den Namen über avahi mit der IPv4-Adresse jeder Schnittstelle an (eth0 und wlan0 je mit ihrer eigenen) und folgt Adressänderungen. Hat ein anderes Gerät den Namen schon, wird es `telefono-2.local` usw. Feste Namen für mehrere Telefone im selben Netz: in `/etc/telefono.conf` im Abschnitt `[network]` `name = kueche` (→ `kueche.local`), wird nach wenigen Sekunden übernommen. Für Dienst-Browser gibt es außerdem `/etc/avahi/services/telefono.service` (`_http._tcp` Port 5000, `_https._tcp` Port 5443).

Ohne bekanntes WLAN (z. B. an einem anderen Ort, ohne Ethernet) macht der Dienst `telefono-hotspot` nach 90 s ein eigenes WLAN auf: SSID `telefono-<hostname>` (`hotspot_ssid = …` in `[network]`), WPA2, das Passwort wird beim ersten Start erzeugt und steht in `/etc/telefono-hotspot.conf` (nur root; `sudo cat /etc/telefono-hotspot.conf`, eigenes Passwort dort eintragen und `sudo systemctl restart telefono-hotspot`). Das Telefon ist dann `10.42.0.1` (`http://10.42.0.1:5000`, auch `telefono.local`, ssh `pi@10.42.0.1`) und verteilt Adressen per DHCP. Bekannt ist jedes WLAN, mit dem sich NetworkManager selbst verbindet (WLAN-Verbindung mit autoconnect). Es gilt immer:
- Ist ein bekanntes WLAN in Reichweite, kommt kein Hotspot; NetworkManager verbindet sich wie bisher selbst.
- Im Hotspot wird alle 3 Minuten nach bekannten WLANs gesucht, aber nur, wenn kein Gerät mit dem Hotspot verbunden ist (niemand wird mitten in der Benutzung getrennt). Ist eins in Reichweite, wechselt das Telefon zurück; sonst ist der Hotspot nach wenigen Sekunden wieder da.
- Die Hotspot-Verbindung liegt nur im Speicher von NetworkManager (nichts in `/etc/netplan` oder `/etc/NetworkManager`), hat kein autoconnect und wird nur von diesem Dienst gestartet. Ethernet wird nie angefasst. Ohne NetworkManager oder ohne WLAN-Gerät tut der Dienst nichts.

Neues WLAN am anderen Ort einrichten: mit dem Hotspot verbinden, `ssh pi@10.42.0.1`, `sudo nmcli connection add type wifi ifname wlan0 con-name <name> ssid <SSID> wifi-sec.key-mgmt wpa-psk wifi-sec.psk <Passwort>`, dann vom Hotspot trennen: Höchstens 3 Minuten später wechselt das Telefon in das neue WLAN.

Abschalten: `hotspot = no` in `[network]` (beendet einen laufenden Hotspot innerhalb von 15 s) oder `sudo systemctl disable --now telefono-hotspot` (bzw. `telefono-mdns`). Der Status der Webapp zeigt beides an („Name im Netzwerk“, „WLAN-Hotspot“), das Journal die Wechsel: `journalctl -u telefono-hotspot -u telefono-mdns`. `sudo make install` installiert und aktiviert beide Dienste (danach einmal `sudo systemctl start telefono-mdns telefono-hotspot` oder neu starten).

## Schaltplan
![image](https://gitlab.mn.tu-dresden.de/josc941e/telefono/-/raw/master/docs/circuit_diagram.png)
