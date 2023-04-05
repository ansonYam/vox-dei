# vox-dei
 Flask backend for a Truffle (Youtube extension) embed. 
 Basically we have taped together three libraries: [Streamlink](https://github.com/streamlink/streamlink) to grab the livestream audio, [Whisper](https://github.com/openai/whisper) to transcribe the audio to text, and [Argos Translate](https://github.com/argosopentech/argos-translate) to translate the text into your language of choice (depending on which argos packages you have installed). 
 
 ## Installation
 If you want to try out this local version on your machine,
 1. Clone the repository: 
     `git clone https://github.com/ansonYam/vox-dei.git`
 2. Install the required libraries: 
     `pip install -r requirements.txt`
 3. Run the application:
     `flask run`
     
 ## Usage
 Maybe one day I will deploy this, but for testing, you can just navigate to localhost. The app won't work without a livestream url and your desired language code. Right now it's just english audio in, some other language text out. As an example (it needs to be a livestream):
    `http://localhost:5000/start?stream_url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&to_code=es`
You will need to run `download_pkg.py` to grab the [argos translation packages](https://www.argosopentech.com/argospm/index/). 
You can call the `/stream` endpoint to receive transcriptions as an event-stream, and `/stop` to stop the transcription threads. I also made a [frontend](https://github.com/ansonYam/vox-populi) to go with this repository, but it's for the 'Truffle' youtube extension and you have to add the frontend localhost url into the [embed config table](https://docs.truffle.vip/truffle-embeds/getting-started).

## Future Work
- **Translation:** Right now, the translation is very scuffed because it is being fed ~5 second sound bites in mp3 form. I need to figure out if I can detect pauses in speech from an audio binary stream, so the mp3s can be full sentences instead.
- **Transcription:** The audio transcription might be better if I tune the whisper model to a specific streamer's voice. There's also the problem of recognizing multiple voices. Google's Speech-to-Text is an option for this, but isn't free. 
- **Performance Improvements:** It takes a bit too long to start/restart the app. I added the mutex and a second transcription thread to try and speed things up, but it's still not quite there. I don't expect latency to be any better if this thing is ever deployed, either. 
