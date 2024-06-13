# from pynput import keyboard
# import pyaudio
# import wave

# CHUNK = 8192
# FORMAT = pyaudio.paInt16
# CHANNELS = 2
# RATE = 44100
# WAVE_OUTPUT_FILENAME = "../prototypes/recording.wav"

# p = pyaudio.PyAudio()

# class Recorder:
#     def __init__(self):
#         self.recording = False
#         self.frames = []

#     def start(self):
#         if self.recording: return
#         self.stream = p.open(format=FORMAT,
#                              channels=CHANNELS,
#                              rate=RATE,
#                              input=True,
#                              frames_per_buffer=CHUNK,
#                              stream_callback=self.callback)
#         self.recording = True
#         print("Start recording...")

#     def stop(self):
#         if not self.recording: return
#         self.recording = False
#         self.stream.stop_stream()
#         self.stream.close()
#         with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
#             wf.setnchannels(CHANNELS)
#             wf.setsampwidth(p.get_sample_size(FORMAT))
#             wf.setframerate(RATE)
#             wf.writeframes(b''.join(self.frames))

#     def callback(self, in_data, frame_count, time_info, status):
#         self.frames.append(in_data)
#         return in_data, pyaudio.paContinue

# class MyListener(keyboard.Listener):
#     def __init__(self):
#         super(MyListener, self).__init__(on_press=self.on_press, on_release=self.on_release, suppress=True)
#         self.recorder = Recorder()

#     def on_press(self, key):
#         if key.char == 'r':
#             self.recorder.start()
#         return True

#     def on_release(self, key):
#         if key.char == 'r':
#             self.recorder.stop()
#             return False  # Stop the listener when 'r' is released
#         return True

# def start_recording_listener():
#     with MyListener() as listener:
#         listener.join()