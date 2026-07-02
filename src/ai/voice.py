from pathlib import Path
import os
from openai import OpenAI
import tempfile
import datetime
from src.utils.AI_model_client import openai_client
from dotenv import load_dotenv

load_dotenv()


# Wrapper class for text to speech
class VoiceHandler:

    def __init__(self, s3_client):
        self.client = OpenAIVoice(s3_client)

    def generate_voice(self, text, voice_id, voice_model):
        return self.client.generate_voice(text, voice_id, voice_model)


class OpenAIVoice:

    def __init__(self, s3_client):
        self.client = openai_client
        self.s3_client = s3_client

    # Purpose: generate audio file for the given text file with the given voice model
    #          returns audio url stored in S3 bucket, or None if an exception is raised
    # Input: text (str), voice_id (str), voice_model (str)
    # output: voice_url (str) or None
    def generate_voice(self, text, voice_id, voice_model):
        try:
            # create temp directory to store audio
            with tempfile.TemporaryDirectory() as temp_dir:
                # create temp file path
                temp_path = Path(temp_dir) / "speech.mp3"

                # generate speech
                response = self.client.audio.speech.create(
                    model=voice_model, voice=voice_id, input=text
                )

                # save to temp file
                response.stream_to_file(temp_path)

                # generate unique filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                s3_filename = f"voice_messages/voice_{timestamp}.mp3"

                # upload audio file to S3
                with open(temp_path, "rb") as audio_file:
                    self.s3_client.upload_fileobj(
                        audio_file,
                        os.getenv("S3_BUCKET_NAME"),
                        s3_filename,
                        ExtraArgs={
                            "ContentType": "audio/mpeg",
                            "CacheControl": "public, max-age=31536000",
                        },
                    )

                # generate url for audio
                voice_url = f"{os.environ.get('S3_LOCATION')}{s3_filename}"
                return voice_url

        except Exception as e:
            print(f"Error generating voice: {e}")
            print(f"S3 Bucket: {os.getenv('S3_BUCKET_NAME')}")
            print(
                f"Generated URL would be: {os.environ.get('S3_LOCATION')}voice_messages/voice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            )
            return None
