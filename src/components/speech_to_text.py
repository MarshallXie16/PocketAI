# import speech_recognition as sr
# from AudioRecorder import AudioRecorder
# import keyboard
# from src.utils.openai_client import client
# from src.utils.audio_record import start_recording_listener

# '''
# Currently supports
# - whisper transcription
# - googleSTT real-time speech recognition (deprecated)

# Future updates
# - ability to interrupt/type while speaking
# '''


# # represents a generic speech-to-text service
# class SpeechToText:

#     def __init__(self):
#         # print('Transcription by whisper')
#         # print('Transcription by google')
#         self.speech_engine = Whisper()

#     # calls the listen method of the transcription tool
#     def listen(self):
#         transcript = self.speech_engine.listen()
#         return transcript


# # uses google speech recognizer to record and convert audio to text
# class GoogleSTT:

#     def __init__(self):
#         self.recognizer = sr.Recognizer()

#     # listens for too long (???)
#     def listen(self):
#         # use the microphone to record audio
#         with sr.Microphone() as source:
#             print("Recording...")
#             audio = self.recognizer.listen(source, phrase_time_limit=15)
#         try:
#             transcript = self.recognizer.recognize_google(audio)
#         # speech is unintelligible
#         except sr.UnknownValueError:
#             print("Google Speech Recognition could not understand audio")
#             transcript = "E1"
#         # API is unreachable
#         except sr.RequestError as e:
#             print("Could not request results from Google Speech Recognition service; {0}".format(e))
#             transcript = "E2"

#         return transcript


# class Whisper:
#     def __init__(self):
#         pass

#     # transcribes a given audio clip; record audio if using text interface
#     def listen(self):
#         # only for text interface
#         # start_recording_listener()
#         try:
#             audio_file = open("../prototypes/recording.wav", "rb")
#             transcript = client.audio.transcriptions.create(
#                 model='whisper-1',
#                 file=audio_file
#             ).text
#         except Exception as e:
#             print(f"Could not transcribe file: {e}")
#             transcript = 'E2'

#         return transcript


# speech_to_text = SpeechToText()
