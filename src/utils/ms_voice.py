def get_SSML(text, voice_name, mood):
    ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
            <voice name='{voice_name}'>
                <mstts:express-as style='{mood}'>
                    <prosody pitch="+10.00%">
                        {text}
                    </prosody>
                </mstts:express-as>
            </voice>
        </speak>
        """
    return ssml