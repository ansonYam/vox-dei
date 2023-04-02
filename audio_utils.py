from streamlink import Streamlink
from functools import partial
import os
import tempfile 
from queue import Queue
import threading
import whisper
import argostranslate.translate

model = whisper.load_model("tiny.en")
audio_queue = Queue()

from_code = "en"
to_code = "es"

def transcribe_audio(stop_event: threading.Event):
    while True:
        audio_file_path = audio_queue.get()
        # print(f"Transcribing audio at path: {audio_file_path}")
        try:
            result = model.transcribe(audio_file_path)
            transcription = result["text"]
            translation = argostranslate.translate.translate(transcription, from_code, to_code)
            yield transcription, translation
            audio_queue.task_done()
        except FileNotFoundError:
            print(f"Error transcribing file {audio_file_path}: File not found")
        except Exception as e:
            print(f"Error transcribing file {audio_file_path}: {e}")
        if stop_event.is_set():
            break

def get_audio_chunks(stream_url: str, stop_event: threading.Event):
    session = Streamlink()
    streams = session.streams(stream_url)
    # print(streams)
    if not streams:
        return []    
    stream = streams["worst"]
    max_file_size = 10 * 1024 * 1024  # 10 MB in bytes
    try:
        fd_stream = stream.open()
        with tempfile.TemporaryDirectory() as temp_dir:
            print(temp_dir)
            file_count = 0
            file_size = 0
            f = None
            for chunk in iter(partial(fd_stream.read, max_file_size), b""):
                # Create a new file if the current file is too big
                if f is None or file_size + len(chunk) > max_file_size:
                    file_count += 1
                    file_size = 0
                    filename = f"{file_count}.mp3"
                    f = open(os.path.join(temp_dir, filename), "wb")
                    
                f.write(chunk)
                file_size += len(chunk)

                # Change the condition below to break after a certain amount of time or data has been processed
                if file_size > 88200:
                    f.close()
                    f = None
                    # Add the new file to the audio queue
                    audio_queue.put(os.path.join(temp_dir, filename))

                if stop_event.is_set():
                    break

            # Close the last file
            if f is not None:
                f.close()

    # TODO: error handling for stream discontinuities (is this a Twitch-only problem? If so, ignore and focus on Yt)

    except Exception as e:
        print(f"Error: {e}")
        return []