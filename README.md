# GIF Sync

Sync GIFs to music.

[Demo](./output.mp4)

Uses the [TempoCNN models](https://essentia.upf.edu/models.html#tempocnn) provided by Essentia.

### Usage

Install ffmpeg and essentia.

    python sync.py \
        --audio_filepath "audio/gypsy.mp3" \
        --gif_filepath "input.gif" \
        --hit_frame_ixs 0 4 \
        --output_filepath "output.mp4" \
        --perfect_loop
