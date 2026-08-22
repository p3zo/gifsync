# GIF Sync

Reassembles the frames of a GIF to sync its animation to the beat of an audio file.

A GIF stores a duration per frame, so nothing has to be added or dropped to retime one; the frames
just get held for different lengths. Mark the frames the beat should land on, mark the beats of the
song, and the animation is stretched so the two line up. The output is an mp4 of the retimed
animation with the audio muxed in, looped to the length of the audio.

The whole thing is one page: [docs/index.html](docs/index.html). Open it, or use the deployed copy.

### [Demo 1](./demo/gypsy_alien.mp4)

Credits: [Dance Reaction GIF by DOMCAKE](https://giphy.com/gifs/dance-alien-ufo-z9wqlsrsqkh3ubbixq)
x [Gypsy Girl by Toman](https://www.youtube.com/watch?v=dKZQRG54vHE).

### [Demo 2](./demo/falling_flower_2D.mp4)

Credits: [Nodding Yes GIF](https://giphy.com/gifs/kFTJEiV9nZlhM2juSN)
x [Epik High - 낙화 (落花) {The Falling Flower}](https://www.youtube.com/watch?v=0J39Amz5o-Y).

## Usage

The page walks through four steps, and a step that is not ready yet says what is missing rather
than sitting there greyed out. **Try an example** fills all of it in with a bouncing ball and a
120bpm loop, both generated for the job, if you would rather see it working before supplying your
own.

Drop a GIF in and step through the frames, marking the ones the beat should land on; the marked
frames appear in their own row, in the order the beat will hit them. Drop a song in and click its
beats on the waveform, or tap them in with `B` while it plays: the first is the downbeat the
animation starts from, and two or more give the tempo. `Find the tempo` reads it off the audio
instead. Both kinds of mark have an undo.

The waveform then shows where every beat frame will land and where the animation loops, and the
preview plays the two together. Changing the tempo while it is playing re-times the animation and
the click track underneath it, so you can nudge it until it locks. Then make the video: it plays
on the page, with a button to download it.

**Tempo (BPM)** is the song's tempo. **The GIF hits** is a separate thing: how often the GIF lands
against that tempo, so `twice a beat` runs the animation at double speed without pretending the song
is faster than it is.

**Between beats**, under *More options*, distributes each beat across the frames between two marks,
and changes the character of the movement more than you would expect. `even` gives every frame the
same duration, so the animation moves at a constant speed and only its landmarks are on the beat.
The two `ease in and out` settings hold the frames midway between beats and flash through the ones
on either side of the beat itself, so the motion snaps on the beat and drifts between them.
Spreading a 500ms beat over eight frames:

| Between beats           | Per-frame durations (ms)                       |
| ----------------------- | ---------------------------------------------- |
| `even`                  | 62.5 each                                      |
| `ease in and out more`  | 3.9, 27.3, 74.2, 144.5, 144.5, 74.2, 27.3, 3.9 |

## How it works

1. `ImageDecoder` decodes the GIF a frame at a time.
2. Each pair of consecutive beat frames is stretched to span exactly one beat, however many frames
   sit between them. The last wraps around to the first, so the animation closes its loop on a beat.
3. The easing distributes that beat across those frames, and the per-frame durations are the
   differences between successive points on the curve.
4. The animation is played starting from the first beat frame rather than from frame 0, so that
   frame lands on the song's downbeat and every later beat frame lands on a beat too.
5. `VideoEncoder` and `AudioEncoder` encode the frames and the audio, and the page muxes them into
   an mp4 itself. Frame timestamps are written to the microsecond, so the beats land exactly.

Tempo estimation runs the [TempoCNN](https://essentia.upf.edu/models.html#tempocnn) model in
`docs/tempocnn/` through TensorFlow.js. Its front end — 11025Hz mono, 1024-sample frames every 512,
Hann, magnitude spectrum, 40 Slaney mel bands over 20-5000Hz with unit-triangle normalisation — was
matched against essentia's `TensorflowInputTempoCNN` to a relative error of 1.5e-7, and gives the
same answer essentia does on both demo tracks.

## Development

    node docs/test_timing.mjs
    node docs/test_tempo.mjs

pull the retiming and the tempo front end out of the page and check them against
`docs/timing_cases.json` and `docs/tempo_cases.json`. Both fixtures were recorded from the Python
this tool replaced — the retiming from `sync.py`, the mel features from essentia — while it was
still in the tree, so the page stays pinned to what those produced rather than to whatever it does
today. The Pages workflow runs both before deploying.

## Limitations

- **Beat frames are marked by hand.** Which frame of an animation reads as its accent is a
  judgement about the motion, and nothing here makes it for you. See
  [#4](https://github.com/p3zo/gifsync/issues/4).
- **Deriving tempo from beat marks assumes they are consecutive beats.** Mark every bar instead and
  the tempo comes out too slow by that factor.
- **A frame shorter than a display refresh will not read**, however exactly it is timed. The eased
  curves reach that first, since their shortest frames sit right at the beat; the page warns when
  any duration falls below it.
- **Firefox has no AAC encoder**, so it produces an Opus track, which QuickTime and Safari will not
  play. Chrome and Safari produce AAC. The page says which you are getting.
- **Transparency is not preserved.**
- **Finding the tempo needs the page served**, not opened off the filesystem, and a network
  connection the first time so TensorFlow.js can load. *Try an example* needs it served for the same
  reason. Off a `file://` url both are disabled and say why; everything else works from a file.
