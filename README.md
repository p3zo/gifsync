# GIF Sync

Sync GIFs to music.

Uses the [TempoCNN models](https://essentia.upf.edu/models.html#tempocnn) provided by Essentia.

### Usage

    python sync.py \
        --song_filepath "audio/gypsy.mp3" \
        --gif_filepath "input.gif" \
        --hit_frame_ixs 0 4 \
        --output_filepath "output.gif" \
        --perfect_loop
