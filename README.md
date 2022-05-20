# GIF Sync

Reassembles the frames of a GIF to sync its animation to the beat of an audio file.

Uses the [TempoCNN models](https://essentia.upf.edu/models.html#tempocnn) provided by Essentia.

### [Demo 1](./demo/gypsy_alien.mp4)

Credits: [Dance Reaction GIF by DOMCAKE](https://giphy.com/gifs/dance-alien-ufo-z9wqlsrsqkh3ubbixq)
x [Gypsy Girl by Toman](https://www.youtube.com/watch?v=dKZQRG54vHE).

### [Demo 2](./demo/falling_flower_2D.mp4)

Credits: [Nodding Yes GIF](https://giphy.com/gifs/kFTJEiV9nZlhM2juSN)
x [Epik High - 낙화 (落花) {The Falling Flower}](https://www.youtube.com/watch?v=0J39Amz5o-Y).

## Usage

Install [ffmpeg](https://ffmpeg.org), [Essentia](https://essentia.upf.edu) with TensorFlow support,
and [Pillow](https://pillow.readthedocs.io/en/stable/installation.html).

Find an audio file that starts exactly on beat. Find a GIF and identify which of its frames you want to align with the
beat. Pass them to the `sync.py` script as in the example below.

##### Example

    python sync.py \
        --audio_filepath "demo/gypsy.m4a" \
        --gif_filepath "demo/alien.gif" \
        --beat_frames 0 9 17 28 36 45 54 63 72 81

##### Optional arguments

      --tempo_multiplier TEMPO_MULTIPLIER
            A multiplier applied to the extracted tempo. Speeds up or slows down the animation. (default: 1.0)

      --output_directory OUTPUT_DIRECTORY
            The directory to which the output will be saved. (default: .)
