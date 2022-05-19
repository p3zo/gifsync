# GIF Sync

Reassembles the frames of a GIF to sync its animation to the beat of an audio file.

Uses the [TempoCNN models](https://essentia.upf.edu/models.html#tempocnn) provided by Essentia.

[Demo](./demo/otter.mp4) synchronizing a
[sticker by takadabear](https://giphy.com/stickers/otter-sea-raccos-76Ezod7CxRDqivd57V)
to [Gypsy Girl by Toman](https://www.youtube.com/watch?v=dKZQRG54vHE).

### Usage

Install [ffmpeg](https://ffmpeg.org), [Essentia](https://essentia.upf.edu) with TensorFlow support,
and [Pillow](https://pillow.readthedocs.io/en/stable/installation.html).

    python sync.py \
        --audio_filepath "demo/gypsy.m4a" \
        --gif_filepath "demo/otter.gif" \
        --hit_frame_ixs 0 4 \
        --output_filepath "demo/otter.mp4" \
        --tempo_multiplier=1.0
