#!/usr/bin/python3
# -*- coding: utf-8 -*-

import concurrent.futures
import errno
import json
import logging
import os
import subprocess

import linkat

from .CONSTANTS import RECORD_DIR
from .CONSTANTS import RECORD_PREFIX
from .CONSTANTS import RECORD_SUFFIX
from .CONSTANTS import LEGACY_RECORD_SUFFIX

from .CONSTANTS import MP3_ENCODE_CMD
from .CONSTANTS import MP3_ENCODE_TIMEOUT
from .CONSTANTS import MP3_PROBE_CMD
from .CONSTANTS import MP3_PROBE_TIMEOUT

from .CONSTANTS import AUDIO_INPUT_OPTIONS
from .CONSTANTS import AUDIO_PROBE_CMD

from .network import sync_dir


log = logging.getLogger ("Audio")


# the file can not be encoded or is no usable mp3 file
class EncodeError (Exception):
	pass


# the file is a supported container, but has no audio (e.g. a video)
class NoAudioError (EncodeError):
	pass


# ffmpeg or ffprobe took too long (e.g. a very long file)
class EncodeTimeout (EncodeError):
	pass


# a path other processes can open the file f through
# (also works for an unlinked O_TMPFILE)
def fd_path (f) -> str:
	return "/proc/self/fd/%d" % f.fileno ()


def check_result (result, what:str):
	if 0 == result.returncode:
		return

	errors = result.stderr.decode (errors="replace").strip ()

	# e.g. the SD card is full, not the file's fault
	if "No space left on device" in errors:
		raise OSError (errno.ENOSPC, os.strerror (errno.ENOSPC))

	raise EncodeError ("%s failed (%d): %s"
	                   % (what, result.returncode, errors))


# ffmpeg writes the mp3 into the file f, opened again through /proc,
# so it can seek back and write the VBR header; source is a path,
# or "pipe:0" to read stdin (which must be a real file or a pipe);
# pass_fds: more files ffmpeg opens through /proc (e.g. the source)
def encode_mp3 (source:str, f, stdin=subprocess.DEVNULL,
                timeout:int=MP3_ENCODE_TIMEOUT,
                input_options:tuple=(), output_options:tuple=(),
                pass_fds:tuple=()):
	try:
		result = subprocess.run ((*MP3_ENCODE_CMD (source,
		                                           input_options,
		                                           output_options),
		                          fd_path (f)),
		                         stdin=stdin,
		                         stdout=subprocess.DEVNULL,
		                         stderr=subprocess.PIPE,
		                         pass_fds=(f.fileno (), *pass_fds),
		                         timeout=timeout)

	except subprocess.TimeoutExpired:
		raise EncodeTimeout ("encoding took more than %d s" % timeout)

	check_result (result, "encoding")
	return


# runs the ffprobe command on the file f, returns its JSON output
def run_probe (command:tuple, f) -> dict:
	f.flush ()

	try:
		result = subprocess.run ((*command, fd_path (f)),
		                         stdin=subprocess.DEVNULL,
		                         capture_output=True,
		                         pass_fds=(f.fileno (), ),
		                         timeout=MP3_PROBE_TIMEOUT)

	except subprocess.TimeoutExpired:
		raise EncodeTimeout ("checking took more than %d s"
		                   % MP3_PROBE_TIMEOUT)

	check_result (result, "checking")

	try:
		info = json.loads (result.stdout)

	except ValueError as error:
		raise EncodeError ("checking failed: %r" % error)

	if not isinstance (info, dict):
		raise EncodeError ("checking failed: %r" % info)

	return info


# checks that the file f is mp3 and has audio frames (ffplay plays
# anything, but all recordings are mp3), returns the number of frames
# and the duration in s (0.0 if ffprobe does not know it)
def probe_mp3_details (f) -> (int, float):
	info = run_probe (MP3_PROBE_CMD, f)

	try:
		format_name = info["format"]["format_name"]
		stream = info["streams"][0]
		codec_name = stream["codec_name"]
		frames = int (stream["nb_read_packets"])

	except (ValueError, TypeError, KeyError, IndexError) as error:
		raise EncodeError ("no audio stream: %r" % error)

	if "mp3" != format_name or "mp3" != codec_name:
		raise EncodeError ("no mp3 file: %s, %s"
		                   % (format_name, codec_name))

	if 0 == frames:
		raise EncodeError ("no audio frames")

	try:
		duration = float (info["format"]["duration"])

	except (ValueError, TypeError, KeyError):
		duration = 0.0

	return frames, duration


def probe_mp3 (f) -> int:
	return probe_mp3_details (f)[0]


# checks that the file f is one of AUDIO_INPUT_FORMATS (else
# EncodeError) with an audio stream (else NoAudioError),
# returns its format and codec name
def probe_audio (f) -> (str, str):
	info = run_probe (AUDIO_PROBE_CMD, f)

	try:
		format_name = info["format"]["format_name"]

	except (TypeError, KeyError) as error:
		raise EncodeError ("unknown format: %r" % error)

	try:
		stream = info["streams"][0]
		if "audio" == stream["codec_type"]:
			return format_name, stream["codec_name"]

	except (TypeError, KeyError, IndexError):
		pass

	raise NoAudioError ("no audio stream in %s" % format_name)


# converts the first audio stream of the file source (one of
# AUDIO_INPUT_FORMATS; a file, not a pipe: mp4 needs seeking) to mp3
# into the file f; max_duration: only that many seconds are converted;
# returns the duration of the mp3 in s
def convert_audio (source, f, max_duration:float=None) -> float:
	format_name, codec_name = probe_audio (source)
	log.debug ("converting %s (%s) to mp3", format_name, codec_name)

	output_options = ()
	if max_duration is not None:
		output_options = ("-t", "%g" % max_duration)

	encode_mp3 (fd_path (source), f,
	            input_options=AUDIO_INPUT_OPTIONS,
	            output_options=output_options,
	            pass_fds=(source.fileno (), ))

	return probe_mp3_details (f)[1]


# like Recorder.save: the file only becomes visible once it is complete
# and on the disk, an existing file is never replaced (FileExistsError);
# write (f) fills the file, it may raise (e.g. InvalidUpload) to discard it;
# filename can also be a function that returns the name (in directory),
# called once the file is written (e.g. to choose a free number only
# then) and again, up to attempts times, while that name exists;
# returns the name of the file
def save_file (filename, write, directory:str=None,
               attempts:int=1) -> str:
	if callable (filename):
		next_name = filename
	else:
		next_name = lambda: filename
		directory = os.path.dirname (filename)

	# create temporary file, closing it without
	# linking it discards it, so errors leave nothing behind
	# (read and write: a converted file is checked before it is linked)
	fd = os.open (directory, os.O_TMPFILE | os.O_RDWR, mode=0o600)

	with os.fdopen (fd, "w+b") as f:
		write (f)
		f.flush ()

		# make sure the data is on the disk before the
		# file becomes visible (power loss)
		os.fsync (fd)

		for attempt in range (1, attempts +1):
			name = next_name ()

			# atomically link file
			try:
				linkat.link_at (linkat.AT_FDCWD,
				                b"/proc/self/fd/%d" % fd,
				                linkat.AT_FDCWD, name.encode (),
				                linkat.AT_SYMLINK_FOLLOW)
				break

			except FileExistsError:
				if attempt == attempts:
					raise

				log.warning ("%s exists, trying the next name",
				             name)

	# make the link durable
	sync_dir (directory)
	return name


def convert_legacy_recording (path:str) -> bool:
	target = path[: -len (LEGACY_RECORD_SUFFIX)] + RECORD_SUFFIX

	def write (f):
		encode_mp3 (path, f)
		probe_mp3 (f)

	try:
		# the mp3 is only linked once it is complete, so this is
		# a conversion that stopped before the old file was removed
		if os.path.exists (target):
			log.warning ("%s already exists, removing %s",
			             target, path)
		else:
			save_file (target, write)

		os.unlink (path)
		sync_dir (os.path.dirname (path))

	except (EncodeError, OSError) as error:
		log.error ("converting %s failed, it is not used: %s",
		           path, error)
		return False

	log.info ("converted %s -> %s", path, target)
	return True

# recordings of older versions (recording<number>.wav) are converted to
# mp3, the old file is removed afterwards; one ffmpeg per CPU core
def convert_legacy_recordings (directory:str=RECORD_DIR) -> int:
	paths = []
	for file in sorted (os.listdir (directory)):
		path = os.path.join (directory, file)

		if os.path.isfile (path) \
		and file.startswith (RECORD_PREFIX) \
		and file.endswith (LEGACY_RECORD_SUFFIX):
			paths.append (path)

	if not paths:
		return 0

	log.info ("converting %d recordings from %s to %s",
	          len (paths), LEGACY_RECORD_SUFFIX, RECORD_SUFFIX)

	with concurrent.futures.ThreadPoolExecutor (os.cpu_count ()) as pool:
		converted = sum (pool.map (convert_legacy_recording, paths))

	log.info ("converted %d of %d recordings", converted, len (paths))
	return converted


# MPEG audio layer III: sample rates and bit rates (kbit/s) by version
# (header bits: 3 = MPEG 1, 2 = MPEG 2, 0 = MPEG 2.5)
MP3_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000),
             0: (11025, 12000, 8000)}
MP3_BITRATES = {3: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224,
                    256, 320),
                2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144,
                    160)}
MP3_HEADER_READ = 4096

# length of an mp3 file in seconds without decoding it (for the status
# page, no ffprobe): from the frame count in the Xing/Info header that
# LAME writes (all recordings of the phone), otherwise estimated from
# the bit rate of the first frame (exact for CBR files); None if no
# frame is found at the start of the file
def mp3_duration (path:str):
	with open (path, "rb") as f:
		size = os.fstat (f.fileno ()).st_size
		data = f.read (10)

		# skip an ID3v2 tag (size: 4 x 7 bit, footer flag)
		start = 0
		if 10 == len (data) and data.startswith (b"ID3"):
			start = 10 + ((data[6] & 0x7f) << 21 | (data[7] & 0x7f) << 14
			              | (data[8] & 0x7f) << 7 | (data[9] & 0x7f))
			if data[5] & 0x10:
				start += 10

		f.seek (start)
		data = f.read (MP3_HEADER_READ)

	index = data.find (b"\xff")
	while -1 != index and index + 4 <= len (data):
		version = data[index + 1] >> 3 & 3
		layer = data[index + 1] >> 1 & 3
		bitrate = data[index + 2] >> 4
		rate = data[index + 2] >> 2 & 3

		# frame sync, layer III, valid rates
		if 0xe0 == data[index + 1] & 0xe0 and 1 == layer \
		and 1 != version and 3 != rate and bitrate not in (0, 15):
			break

		index = data.find (b"\xff", index + 1)
	else:
		return None

	rate = MP3_RATES[version][rate]
	samples = 1152 if 3 == version else 576
	mono = 3 == data[index + 3] >> 6

	# the Xing header follows the side information
	if 3 == version:
		offset = index + 4 + (17 if mono else 32)
	else:
		offset = index + 4 + (9 if mono else 17)

	tag = data[offset:offset + 4]
	if tag in (b"Xing", b"Info") and len (data) >= offset + 12 \
	and data[offset + 7] & 1:
		frames = int.from_bytes (data[offset + 8:offset + 12], "big")
		return frames * samples / rate

	kbits = MP3_BITRATES[3 if 3 == version else 2][bitrate]
	return (size - start - index) * 8 / (kbits * 1000)
