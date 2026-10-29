# telefono
Ein wählscheibentelefon zu einer interaktiven Maschine umgebaut.

## Hint
Please install the git hooks under hooks/ for a working build.


## Funktionsweise
Wenn der Hörer abgenommen wird ist ein Freiton hörbar. Hier hat man mehrere Optionen:

Aufnahme:
Drückt man den linken Knopf wird eine Aufnahme gestartet, die Stimme sagt einem um welche Aufnahme es sich handelt. Wird der linke Knopf nochmal gedrückt oder der Hörer aufgelegt wird die Aufnahme gespeichert. Drückt man stattdessen den mittleren Knopf wird die Aufnahme Gelöscht.

Alte Aufnahme abspielen:
Fängt man an die Nummernscheibe zu bedienen wird der Freiton unterbrochen und man kann beliebig viele Zahlen wählen. Drückt man dann den linken Knopf wird die Aufnahme mit der entsprechenden Nummer abgespielt.

Lautsprecher:
Mit dem Kippschalter rechts, kann man das Telefon auf laut oder leise schalten. Die Klingel ist immer Laut.

## Hardware-Konfiguration
Die Telefone sind unterschiedlich verdrahtet, bei manchen sind einzelne Eingänge (Hörer, Knöpfe, ...) invertiert. Das wird pro Telefon in `/etc/telefono.conf` eingestellt (bei `../configure --sysconfdir=/etc`, sonst `<prefix>/etc/telefono.conf`), nicht im Code:

```
sudo cp /etc/telefono.conf.example /etc/telefono.conf
sudo nano /etc/telefono.conf
sudo systemctl restart telefono
```

Ein Eingang muss invertiert werden (`yes`), wenn er in Ruhe (Hörer aufgelegt, Knöpfe losgelassen) als gedrückt gelesen wird. Ohne die Datei ist nichts invertiert. Das Journal zeigt, was gelesen wurde: `journalctl -u telefono | grep inverted`.

Einfacher geht es mit der Seite **Hardware-Test** der Webapp (`http://<telefon>:5000/diagnose`): Sie zeigt live für jeden Eingang den Pegel am GPIO, die Einstellung aus `telefono.conf` und was telefono daraus liest, und sagt, welche Zeile zu ändern ist, wenn ein Eingang in Ruhe falsch gelesen wird. Sie liest die GPIO-Register direkt (`/dev/gpiomem`, nur lesend), funktioniert also auch bei abgehobenem Hörer. Die gewählte Ziffer zeigt, ob die Wählscheibe richtig zählt; LED und Lautsprecher-Relais lassen sich testen, wenn das Telefon frei ist.

## Aufnehmen im Browser (https)
Auf der Seite **Aufnehmen** der Webapp nimmt man mit dem Mikrofon von Laptop oder Handy auf. Browser erlauben das Mikrofon nur über https (oder auf localhost), deshalb läuft die Webapp zusätzlich auf `https://<telefon>:5443` mit einem selbst ausgestellten Zertifikat. `sudo make install` erzeugt es einmalig mit `openssl` (`/etc/telefono.crt`, `/etc/telefono.key`, nur für root und die Gruppe des Dienst-Benutzers lesbar); ohne Zertifikat gibt es nur http. Neues Zertifikat (z. B. nach Änderung des Hostnamens): beide Dateien löschen, `sudo make install`, `sudo systemctl restart telefono`. Ohne https kann man auf dem Handy mit dessen Aufnahme-App aufnehmen und die Datei speichern. Hochgeladene Dateien (.m4a, .ogg, .opus, .webm, .3gp, .amr, .flac, .wav, ...) wandelt `ffmpeg` in .mp3 um.

## Schaltplan
![image](https://gitlab.mn.tu-dresden.de/josc941e/telefono/-/raw/master/docs/circuit_diagram.png)
