from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import threading
from streamlink import Streamlink
from queue import Queue
import queue
import tempfile
from functools import partial
import os
import ffmpeg
import whisper
import argostranslate.translate
import json
import time

app = Flask(__name__)
CORS(app)

model = whisper.load_model("tiny.en")
audio_queue = Queue()
audio_thread = None
transcription_queue = Queue()
# transcription_thread = None
transcription_threads = []

mutex = threading.Lock()

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
        self.mutex = mutex

    def set_stream_url(self, stream_url):
        self.stream_url = stream_url

    def run(self):
        print("Audio thread started")
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
                    magic_number = 131072 # bytes
                    chunks = []
                    for chunk in iter(partial(fd_stream.read, magic_number), b""):                        
                        # for debugging
                        # print(len(chunk))
                        if self.stopped():
                            break
                        chunks.append(chunk)
                        byte_count += len(chunk)
                        if byte_count >= magic_number:
                            if f is not None:
                                f.close()
                            filename = f"{file_count}.raw"
                            with open(os.path.join(temp_dir, filename), "wb") as f:
                                f.write(b"".join(chunks))
                            input_file = os.path.join(temp_dir, filename)
                            output_file = os.path.join(temp_dir, f"{file_count}.mp3")
                            convert_to_mp3(input_file, output_file)
                            with mutex:
                                audio_queue.put(output_file)
                                # print(f"Added {output_file} to queue")
                            file_count += 1
                            byte_count = 0
                            chunks = []
                    # Write remaining chunks to file and convert to mp3
                    if f is not None:
                        f.close()
                    filename = f"{file_count}.raw"
                    with open(os.path.join(temp_dir, filename), "wb") as f:
                        f.write(b"".join(chunks))
                    input_file = os.path.join(temp_dir, filename)
                    output_file = os.path.join(temp_dir, f"{file_count}.mp3")
                    convert_to_mp3(input_file, output_file)
                    with mutex:
                        audio_queue.put(output_file)
                        # print(f"Added {output_file} to queue")
                                    
            except Exception as e:
                print(f"Error: {e}")
                return []
                
class TranscriptionThread(StoppableThread):
    def __init__(self):
        super().__init__()
        self.to_code = None
        self.mutex = mutex

    def set_to_code(self, to_code):
        self.to_code = to_code

    def run(self):        
        print("Transcription thread started")
        from_code = "en" # english only for now

        global audio_queue, transcription_queue
        while not self.stopped():
            try:
                with self.mutex:
                    audio_file = audio_queue.get_nowait()
                    # print(f"Transcribing audio at path: {audio_file_path}")
                try:
                    result = model.transcribe(audio_file)
                    transcription = result["text"]
                    translation = argostranslate.translate.translate(transcription, from_code, self.to_code)
                    print(transcription, translation)
                    with self.mutex:
                        transcription_queue.put((transcription, translation))
                        # print(f"Currently {transcription_queue.qsize()} item(s) in the queue")
                    with self.mutex:
                        audio_queue.task_done()
                except FileNotFoundError:
                    print(f"Error: File not found at path {audio_file}")
                except Exception as e:
                    print(f"Error transcribing file {audio_file}: {e}")
            except queue.Empty:
                time.sleep(0.1)
                continue

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

def generate(transcription_queue, mutex):
    while True:
        # Attempt to retrieve a transcription from the queue
        with mutex:
            try:
                transcription, translation = transcription_queue.get_nowait()
                # Yield the transcription result to the frontend
                yield f"data: {json.dumps({'transcription': transcription, 'translation': translation})}\n\n"
                transcription_queue.task_done()
            except queue.Empty:
                # If the queue is empty, wait for a short period of time
                time.sleep(0.1)
                continue

@app.route("/start")
def start():    
    global audio_thread, transcription_thread
    stream_url = request.args.get('stream_url')
    to_code = request.args.get('to_code', )

    if stream_url is None:
        return jsonify({'error': 'Missing required parameter "stream_url".'}), 400

    audio_thread = AudioThread()
    audio_thread.set_stream_url(stream_url=stream_url)
    audio_thread.start()

    if to_code is None:
        return jsonify({'error': 'Missing required parameter "to_code".'}), 400

    for _ in range(2): # could be more
        t = TranscriptionThread()
        t.set_to_code(to_code=to_code)
        t.start()
        transcription_threads.append(t)

    return jsonify({'message': 'Threads started'})    

@app.route('/stream')
def stream():
    global transcription_threads, transcription_queue, mutex
    if not transcription_threads:
                return jsonify({'error': 'No transcription threads started.'}), 400
    return Response(generate(transcription_queue, mutex), mimetype='text/event-stream')
    
@app.route('/stop')
def stop():
    global audio_thread, transcription_threads, audio_queue, transcription_queue
    if audio_thread is not None:
        audio_queue.queue.clear()
        audio_thread.stop()
        audio_thread.join()
    if transcription_threads is not None:
        transcription_queue.queue.clear()
        for t in transcription_threads:
            t.stop()
            t.join()
        transcription_threads.clear()
    return jsonify({'message': 'Threads stopped'})