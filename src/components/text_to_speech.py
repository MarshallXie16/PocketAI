import os
from google.cloud import texttospeech
from google.oauth2.service_account import Credentials
import sounddevice as sd
import soundfile as sf
import azure.cognitiveservices.speech as msvoice
from openai import OpenAI
from elevenlabs import Voice, set_api_key, VoiceSettings, generate, play

from src.utils.ms_voice import get_SSML
from src.components.context_analyzer import context_analyzer


'''
Currently supports
- GoogleTTS
- OpenAI
- MicrosoftTTS w/ emotion classification
- ElevenLabs

Future updates
- 
'''

''' Credentials '''
google_credentials_path = "C:/Users/Lyric/Downloads/basic-strata-382418-6f8ce922e875.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
creds = Credentials.from_service_account_file(google_credentials_path)
subscription_key = "d031f7f7faa947a1886e930095c6d04b"
region = "WestUS"
FILENAME = "../speech.mp3"


def play_audio():

    # Load and play audio file
    data, samplerate = sf.read('../speech.mp3')
    sd.play(data, samplerate)

    # Wait for audio to finish playing
    sd.wait()

class TextToSpeech:
    def __init__(self):
        print("Transcription by OpenAI")
        self.service = OpenAITTS()

    def speak(self, text):
        self.service.speak(text)

class GoogleTTS:

    # instantiate client, set voice parameters, and set audio file config
    def __init__(self, lang="en-US"):
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=lang,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            name='en-US-News-L'
        )
        self.config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

    def speak(self, text):
        # parse the input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # makes a request to API and return the audio
        response = self.client.synthesize_speech(
            input=synthesis_input, voice=self.voice, audio_config=self.config
        )

        # write decoded audio into mp3 file
        with open(FILENAME, "wb") as f:
            f.write(response.audio_content)

        play_audio()

class MicrosoftTTS:

    EMOTIONS = ['default', 'angry', 'cheerful', 'excited', 'friendly', 'hopeful', 'sad', 'shouting', 'terrified', 'unfriendly', 'whispering']
    ''' Offer a variety of different voice options that can be easily swapped -- ENUM? '''

    def __init__(self):
        self.speech_config = msvoice.SpeechConfig(subscription=subscription_key, region=region)
        self.speech_config.speech_synthesis_voice_name = 'en-US-JessaNeural'
        self.client = msvoice.SpeechSynthesizer(speech_config=self.speech_config)

    def speak(self, text):
        emotion = context_analyzer.emotion_classifier(text)
        print(f'Emotion: {emotion}')
        if emotion.lower() not in self.EMOTIONS:
            emotion = 'default'
        ssml = get_SSML(text, "en-US-JaneNeural", emotion.lower())
        result = self.client.speak_ssml_async(ssml).get()
        # Check the result (!!!)
        if result.reason == msvoice.ResultReason.SynthesizingAudioCompleted:
            print("Speech synthesized.".format(ssml))
        elif result.reason == msvoice.ResultReason.Canceled:
            cancellation = result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation.reason))
            if cancellation.reason == msvoice.CancellationReason.Error:
                print("Error details: {}".format(cancellation.error_details))

class ElevenLabsTTS:
    def __init__(self):
        set_api_key("db648b643c90be8e3fa6c3443e3c8e6d")
        self.voice_id = 'veqAqxKtBQM4mxtjCNHX'

    def speak(self, text):

        audio = generate(
            text=text,
            voice=Voice(
                voice_id=self.voice_id,
                settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
            )
        )

        play(audio)

class OpenAITTS:
    def __init__(self):
        self.client = OpenAI()

    def speak(self, text):

        response = self.client.audio.speech.create(
            input=text,
            model="tts-1",
            voice="nova"
        )

        response.stream_to_file(FILENAME)

        play_audio()


text_to_speech = TextToSpeech()