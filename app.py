from flask import Flask, jsonify, Response
from audio_utils import get_audio_chunks, transcribe_audio
import threading

app = Flask(__name__)

@app.route("/")
def hello_world():
    response = jsonify({'message': 'Hello, World!'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route("/start")
def start_transcription():
    # start the audio thread
    print("Starting audio_thread")
    audio_thread = threading.Thread(target=get_audio_chunks)
    audio_thread.start()

    # start the transcribing thread
    print("Staring transcription thread")
    transcribing_thread = threading.Thread(target=transcribe_audio, daemon=True)
    transcribing_thread.start()

    return "Transcription started"