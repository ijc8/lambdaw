import sys

from magenta.models.music_vae import configs
from magenta.models.music_vae import TrainedModel

model = sys.argv[1]
config = configs.CONFIG_MAP[model]
checkpoint_dir_or_path = f"{model}.tar"
temperature = 0.5

model = TrainedModel(
    config, batch_size=1,
    checkpoint_dir_or_path=checkpoint_dir_or_path)

results = model.sample(
    n=1,
    length=config.hparams.max_seq_len,
    temperature=temperature)

print([
    {"pitch": note.pitch, "velocity": note.velocity, "start": note.start_time, "end": note.end_time}
    for note in results[0].notes
])
