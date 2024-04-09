import azure.cognitiveservices.speech as speechsdk

# Set up the subscription info for the Speech Service:
subscription_key = "d031f7f7faa947a1886e930095c6d04b"  # Replace with your subscription key
region = "WestUS"  # Replace with the region of your service

# Set up the speech configuration:
speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)

# Specify the voice name you want to use:
# You can find the list of available voices through the documentation or API
# Here, "en-US-JessaNeural" is an example of a voice that can express emotion
speech_config.speech_synthesis_voice_name = 'en-US-JessaNeural'

# Create a text-to-speech client:
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

# Your text to be spoken with SSML for emotion:
ssml = """
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
    <voice name='en-US-JessaNeural'>
        <mstts:express-as style='cheerful'>
            Yay, I'm so happy!
        </mstts:express-as>
    </voice>
</speak>
"""

# Synthesize the text:
result = speech_synthesizer.speak_ssml_async(ssml).get()

# Check the result:
if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Speech synthesized to speaker for text [{}]".format(ssml))
elif result.reason == speechsdk.ResultReason.Canceled:
    cancellation = result.cancellation_details
    print("Speech synthesis canceled: {}".format(cancellation.reason))
    if cancellation.reason == speechsdk.CancellationReason.Error:
        print("Error details: {}".format(cancellation.error_details))
