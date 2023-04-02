from flask import Flask, jsonify, request, Response
from audio_utils import get_audio_chunks, transcribe_audio, stop_transcription
import threading
import json

app = Flask(__name__)

@app.route("/")
def hello_world():
    response = jsonify({'message': 'Hello, World!'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
class StoppableThread(threading.Thread):
    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


@app.route("/start")
def start_transcription():
    global audio_thread, transcribing_thread

    # get the stream_url from the request
    stream_url = request.args.get('stream_url',)

    # subroutine for streaming the transcribed text
    def stream_transcription():
        for transcription, translation in transcribe_audio():
            data = {'transcription': transcription, 'translation': translation}
            yield 'data: %s\n\n' % json.dumps(data)

    # start the audio thread
    print(f"Starting audio_thread for stream URL {stream_url}")
    audio_thread = StoppableThread(target=get_audio_chunks, args=(stream_url,))
    audio_thread.start()

    # start the transcribing thread
    print("Staring transcription thread")
    transcribing_thread = StoppableThread(target=transcribe_audio)
    transcribing_thread.start()

    # set response headers
    response = Response(stream_transcription(), mimetype='text/event-stream')    
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

@app.route('/stop')
def stop():
    global audio_thread, transcribing_thread
    stop_transcription()
    
    # stop the threads
    audio_thread.stop()
    transcribing_thread.stop()

    # wait for threads to finish
    audio_thread.join()
    transcribing_thread.join()

    # set response headers
    response = Response("Transcription stopped", status=200)
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response