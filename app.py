from flask import Flask, jsonify, request, Response
from audio_utils import get_audio_chunks, transcribe_audio
import threading
import json

app = Flask(__name__)

# need this to stop my threads
stop_event = threading.Event()

# subroutine for streaming the transcribed text
def stream_transcription(transcription_generator):
    global stop_event
    for transcription, translation in transcription_generator:
        data = {'transcription': transcription, 'translation': translation}
        yield 'data: %s\n\n' % json.dumps(data)

        if stop_event.is_set():
            break

@app.route("/")
def hello_world():
    response = jsonify({'message': 'Hello, World!'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route("/start")
def start_transcription():
    # get the stream_url from the request
    stream_url = request.args.get('stream_url',)

    # start the audio thread
    print(f"Starting audio_thread for stream URL {stream_url}")
    threading.Thread(target=get_audio_chunks,
                     args=(stream_url, stop_event)).start()
    
    # start the transcribing thread
    print("Starting transcription thread")
    transcription_generator = transcribe_audio(stop_event)
    threading.Thread(target=stream_transcription,
                     args=(transcription_generator,),
                     daemon=True).start()     
       
    # set response headers
    response = Response(stream_transcription(transcription_generator), mimetype='text/event-stream')    
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

@app.route('/stop')
def stop():
    stop_event.set()
    
    # set response headers
    response = jsonify({'message': 'Transcription stopped'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    
    return response