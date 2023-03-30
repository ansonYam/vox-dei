from streamlink import Streamlink
from functools import partial
import os
import tempfile 
from queue import Queue
import whisper

model = whisper.load_model("tiny.en")
audio_queue = Queue()

def transcribe_audio():
    while True:
        audio_file_path = audio_queue.get()
        # print(f"Transcribing audio at path: {audio_file_path}")
        try:
            result = model.transcribe(audio_file_path)
            transcription = result["text"]
            print(transcription)
            audio_queue.task_done()
        except Exception as e:
            print(f"Error transcribing file {audio_file_path}: {e}")

def get_audio_chunks():
    # TODO: don't hardcode the URL
    session = Streamlink()
    stream_url = "https://www.twitch.tv/qtcinderella"
    streams = session.streams(stream_url)
    # print(streams)
    if not streams:
        return []
    
    # we won't always have this available, so switch this for 'worst' and use ffmpeg to convert video to audio
    audio_stream = streams["audio_only"]
    max_file_size = 10 * 1024 * 1024  # 10 MB in bytes
    try:
        fd_stream = audio_stream.open()
        with tempfile.TemporaryDirectory() as temp_dir:
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
                if file_size > 1024 * 1024:
                    f.close()
                    f = None
                    # Add the new file to the audio queue
                    audio_queue.put(os.path.join(temp_dir, filename))

            # Close the last file
            if f is not None:
                f.close()
    
    except Streamlink.StreamlinkError as e:
        print("Encountered a stream error. Re-establishing connection...")
        get_audio_chunks()
        
    except Exception as e:
        print(f"Error: {e}")
        return []