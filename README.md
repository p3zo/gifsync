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

Install [Docker Compose](https://docs.docker.com/compose/install/) and start the Docker daemon.

Build the container with Essentia, Tensorflow, and ffmpeg

    docker compose build

Start the container and get a shell inside

    docker compose up -d && docker compose exec app bash

Find an audio file that starts exactly on beat. Find a GIF and label the frames you want to align to the
beat. Pass them to the `sync.py` script as in the example below.

    python sync.py \
        --audio_filepath "demo/gypsy.m4a" \
        --gif_filepath "demo/alien.gif" \
        --beat_frames 0 9 17 28 36 45 54 63 72 81

##### Optional arguments

    --tempo_multiplier TEMPO_MULTIPLIER
        A multiplier applied to the extracted tempo. Speeds up or slows down the animation. (default: 1.0)

    --output_directory OUTPUT_DIRECTORY
        The directory to which the output will be saved. (default: .)

    --bpm BPM
        The BPM of the audio. Will be estimated if not passed. (default: None)

    --interpolation INTERPOLATION
        The method of interpolation to use. Options: [linear, cubic, quadratic] (default: linear)
