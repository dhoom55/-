# Jarvis only uses Google recognition, which needs the bundled FLAC encoder -
# not the ~40 MB of offline PocketSphinx models the default hook would add.
from PyInstaller.utils.hooks import collect_data_files

datas = [d for d in collect_data_files("speech_recognition") if "pocketsphinx" not in d[0]]
