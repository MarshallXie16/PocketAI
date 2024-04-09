from openai import OpenAI


client = OpenAI()


transcript = client.audio.transcriptions.create(
    model='whisper-1',
    file=open('recording.wav', 'rb')
)


print(transcript.text)