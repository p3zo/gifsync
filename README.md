# GIF Sync

Reassembles the frames of a GIF to sync its animation to the beat of an audio file.

Uses the [TempoCNN models](https://essentia.upf.edu/models.html#tempocnn) provided by Essentia.

The output is an mp4 of the retimed animation with the audio muxed in, looped to the length of the audio.

### [Demo 1](./demo/gypsy_alien.mp4)

Credits: [Dance Reaction GIF by DOMCAKE](https://giphy.com/gifs/dance-alien-ufo-z9wqlsrsqkh3ubbixq)
x [Gypsy Girl by Toman](https://www.youtube.com/watch?v=dKZQRG54vHE).

### [Demo 2](./demo/falling_flower_2D.mp4)

Credits: [Nodding Yes GIF](https://giphy.com/gifs/kFTJEiV9nZlhM2juSN)
x [Epik High - 낙화 (落花) {The Falling Flower}](https://www.youtube.com/watch?v=0J39Amz5o-Y).

## Beat marker

`docs/index.html` is a page for picking the beat frames without counting them by hand. Drop a GIF in,
step through the frames, mark the ones the beat should land on, drop a song in and click its first
downbeat on the waveform, then preview the two together before rendering.

Open the file directly and it renders the mp4 itself, using WebCodecs. Serve it with

    python marker.py

and it also offers to render through `sync.py`, trimming the audio to the downbeat first, and to
estimate the tempo with essentia. From inside the container use `python marker.py --host 0.0.0.0`
and open <http://localhost:5000>.

The two renderers agree on the retiming — `node docs/test_timing.mjs` checks the page's copy against
`sync.py` — but not on the encode. The browser writes exact per-frame timestamps, while `sync.py`
goes through ffmpeg's concat demuxer and its 40ms grid.

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

## How it works

A GIF stores a duration per frame, so nothing has to be added or dropped to retime one; the frames just get held for
different lengths.

1. TempoCNN estimates the tempo of the audio, which gives the length of one beat in milliseconds. `--bpm` skips the
   estimation, and `--tempo_multiplier` scales it.
2. Each pair of consecutive `--beat_frames` is stretched to span exactly one beat, however many frames sit between
   them. The last label wraps around to the first, so the animation closes its loop on a beat.
3. An easing function distributes that beat across those frames, and the per-frame durations are the differences
   between successive points on the curve.
4. The animation is played starting from the first `--beat_frames` label rather than from frame 0, so that label
   lands on the audio's first beat and every later one lands on a beat too.
5. ffmpeg concatenates the frames at their new durations, repeating the sequence enough times to cover the audio, and
   muxes the audio in.

`--interpolation` picks the easing, and it changes the character of the movement more than you would expect. `linear`
gives every frame the same duration, so the animation moves at a constant speed and only its landmarks are on the beat.
`cubic` and `quadratic` ease in and out, which holds the frames midway between beats and flashes through the ones on
either side of the beat itself — the motion snaps on the beat and drifts between them. Spreading a 500ms beat over
eight frames:

| Easing   | Per-frame durations (ms)                          |
| -------- | ------------------------------------------------- |
| `linear` | 62.5 each                                         |
| `cubic`  | 3.9, 27.3, 74.2, 144.5, 144.5, 74.2, 27.3, 3.9    |

These are what the curve asks for; what ffmpeg delivers is rounded, see the limitations below.

## Limitations

- **The audio has to start exactly on a beat.** There is no offset detection, so a track with a lead-in has to be
  trimmed first.
- **Beat frames are labelled by hand.** Which frame of an animation reads as its accent is a judgement about the
  motion, and nothing here makes it for you.
- **Frame durations are rounded onto a 40ms grid.** ffmpeg's concat demuxer gives a stream of images a 1/25 timebase,
  so nothing finer than 40ms survives and each beat can land up to 20ms early or late. The error does not accumulate,
  but the shape of an eased curve does get flattened — in the table above every one of `cubic`'s four shortest frames
  rounds to the same length. The script warns when any duration falls below the grid; use fewer beat frames or a
  different easing.
- **Transparency is not preserved** when the frames are concatenated.
