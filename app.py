from flask import Flask, jsonify, request, Response
import threading
from streamlink import Streamlink
from queue import Queue
import tempfile
from functools import partial
import os
import ffmpeg
import whisper
import argostranslate.translate

app = Flask(__name__)

model = whisper.load_model("tiny.en")
audio_queue = Queue()
audio_thread = None
transcription_queue = Queue()
transcription_thread = None

# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
class StoppableThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

class AudioThread(StoppableThread):
    def __init__(self):
        super().__init__()
        self.stream_url = None
    
    def set_stream_url(self, stream_url):
        self.stream_url = stream_url

    def run(self):
        global audio_queue
        while not self.stopped():
            session = Streamlink()
            streams = session.streams(self.stream_url)
            # print(streams)
            if not streams:
                return []    
            stream = streams["worst"]
            try:
                fd_stream = stream.open()
                with tempfile.TemporaryDirectory() as temp_dir:
                    print(f"Created temporary directory: {temp_dir}")
                    file_count = 0
                    byte_count = 0
                    f = None
                    for chunk in iter(partial(fd_stream.read, 81920), b""):                        
                        if self.stopped():
                            break
                        print(f"Read {len(chunk)} bytes of data")
                        if f is None or byte_count >= 81920 or file_count > 0:
                            if f is not None:
                                f.close()
                                input_file = os.path.join(temp_dir, filename)
                                output_file = os.path.join(temp_dir, f"{file_count}.mp3")
                                convert_to_mp3(input_file, output_file)
                                audio_queue.put(output_file)
                                print(f"Added {output_file} to queue")
                            file_count += 1
                            byte_count = 0
                            filename = f"{file_count}.raw"
                            f = open(os.path.join(temp_dir, filename), "wb")

                        f.write(chunk)
                        byte_count += len(chunk)
                        print(f"Wrote {len(chunk)} bytes to file {filename}")

                    # Add the last file to the audio queue
                    if f is not None:
                        f.close()
                        input_file = os.path.join(temp_dir, filename)
                        output_file = os.path.join(temp_dir, f"{file_count}.mp3")
                        convert_to_mp3(input_file, output_file)
                        audio_queue.put(output_file)
                        print(f"Added {output_file} to queue")
                                
            except Exception as e:
                print(f"Error: {e}")
                return []
                
class TranscriptionThread(StoppableThread):
    def __init__(self):
        super().__init__()
        self.to_code = None

    def set_to_code(self, to_code):
        self.to_code = to_code

    def run(self):
        from_code = "en" # english only for now

        global audio_queue, transcription_queue
        while not self.stopped():
            if not audio_queue.empty():
                audio_file = audio_queue.get()
                # print(f"Transcribing audio at path: {audio_file_path}")
                try:
                    result = model.transcribe(audio_file)
                    transcription = result["text"]
                    translation = argostranslate.translate.translate(transcription, from_code, self.to_code)
                    print(transcription, translation)
                    transcription_queue.put((transcription, translation))
                    audio_queue.task_done()
                except Exception as e:
                    print(f"Error transcribing file {audio_file}: {e}")
                if self.stopped():
                    break

def convert_to_mp3(input_file, output_file):
    (
        ffmpeg
        .input(input_file)
        .output(output_file, acodec='libmp3lame', loglevel='quiet')
        .overwrite_output()
        .run()
    )

@app.route("/start")
def start():    
    global audio_thread
    stream_url = request.args.get('stream_url')
    to_code = request.args.get('to_code', )

    if stream_url is None:
        return jsonify({'error': 'Missing required parameter "stream_url".'}), 400

    audio_thread = AudioThread()
    audio_thread.set_stream_url(stream_url=stream_url)
    audio_thread.start()

    if to_code is None:
        return jsonify({'error': 'Missing required parameter "to_code".'}), 400

    transcription_thread = TranscriptionThread()
    transcription_thread.set_to_code(to_code=to_code)
    transcription_thread.start()
    
    # something wrong here
    """ def generate():
        nonlocal transcription_thread
        while not transcription_thread.stopped():
            if not transcription_queue.empty():
                transcription, translation = transcription_queue.get()
                yield jsonify({'transcription': transcription, 'translation': translation}) + '\n'

    response = Response(generate(), mimetype='text/event-stream')   
    response.headers.add('Access-Control-Allow-Origin', '*')
"""
    return jsonify({'message': 'Threads started'})

@app.route('/status')
def status():
    global audio_thread, transcription_thread
    if audio_thread.stopped() and transcription_thread.stopped():
        return jsonify({'message': 'Both threads stopped'})
    else:
        return jsonify({'message': 'At least one thread still running'})
    
@app.route('/stop')
def stop():
    global audio_thread, transcription_thread
    audio_thread.stop()
    audio_thread.join()
    transcription_thread.stop()
    transcription_thread.join()
    return jsonify({'message': 'Threads stopped'})