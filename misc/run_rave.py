import sys
import wave

import torch
import torchaudio

if len(sys.argv) < 3:
    print(f"usage: {sys.argv[0]} <model path> <input path> <output path>")
    exit()

model = torch.jit.load(sys.argv[1])

audio, sr = torchaudio.load(sys.argv[2])

audio = audio.sum(axis=0).reshape(1, 1, -1)
with torch.no_grad():
    output = model(audio).select(0, 0).T.contiguous()

# Avoiding torchaudio.save because it uses a funky format in the wave header (which Python's `wave` module can't read).
with wave.open(sys.argv[3], "wb") as w:
    channels = output.shape[1]
    w.setnchannels(channels)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((output * (2**15-1)).to(torch.int16).numpy())
