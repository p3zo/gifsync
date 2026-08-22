# Gifsync

Gifsync is a free browser tool that retimes a GIF so its animation lands on the beat of a song, and
saves the result as an MP4 with the audio in it. Nothing is uploaded: the decoding, the retiming and
the encoding all happen in the page. **<https://p3zo.github.io/gifsync/>**

Most tools that offer to add music to a GIF lay an audio track underneath and leave the animation
alone, so the loop slides out of time with the song. This one changes the animation instead. A GIF
stores a duration per frame, so nothing has to be added or dropped to retime one. The frames just
get held for different lengths. Mark the frames the beat should land on, mark the beats of the
song, and the animation is stretched so the two line up. The output is an mp4 of the retimed
animation with the audio muxed in, looped to the length of the audio.

[The examples](https://p3zo.github.io/gifsync/examples/) are the same GIF and the same bar timed
three ways, with sound. The page itself explains how to use it, and also runs from
[site/index.html](site/index.html) off disk. This file is about how it works.

## How it works

1. `ImageDecoder` decodes the GIF a frame at a time.
2. Each pair of consecutive beat frames is stretched to span exactly one beat, however many frames
   sit between them. The last pair wraps around to the first, so the loop closes on a beat.
3. The easing spreads that beat across those frames. The per-frame durations are the differences
   between successive points on the curve.
4. Playback starts at the first beat frame rather than at frame 0, so that frame lands on the
   song's downbeat and every later beat frame lands on a beat too.
5. `VideoEncoder` and `AudioEncoder` encode the frames and the audio, and the page muxes them into
   an mp4 itself. Frame timestamps are written to the microsecond.

The easing changes the character of the movement more than you would expect. Spreading a 500ms beat
over eight frames:

| Between beats          | Per-frame durations (ms)                       |
| ---------------------- | ---------------------------------------------- |
| `even`                 | 62.5 each                                      |
| `ease in and out more` | 3.9, 27.3, 74.2, 144.5, 144.5, 74.2, 27.3, 3.9 |

`even` moves at a constant speed, so only the landmarks land on the beat. The eased curves hold the
frames midway between beats and flash through the ones on either side of the beat, so the motion
snaps on the beat and drifts between them.

**Beats in the song.** [TempoCNN](https://essentia.upf.edu/models.html#tempocnn) in `site/tempocnn/`
gives the tempo through TensorFlow.js. Its front end (11025Hz mono, 1024-sample frames every 512,
Hann, magnitude spectrum, 40 Slaney mel bands over 20-5000Hz with unit-triangle normalisation)
matches essentia's `TensorflowInputTempoCNN` to a relative error of 1.5e-7. That tempo grid then
slides across an envelope of the attacks and stops wherever it catches the most. One envelope frame
is 5.8ms, and shifting a track by a known amount shifts the answer with it to within about 10ms.

**Beat frames in the GIF.** An even spread around the loop starting at frame 0, with each mark
nudged onto whichever of its two neighbouring frames changes most. Against hand labels that comes
out 0.40 and 0.50 frames off, where marks thrown down at random score about 3.

**How many beats the loop lasts** is moved to a nearby divisor of the frame count first. A beat
covers a whole number of frames, so 20 frames over 8 beats has to alternate 3 and 2, and that 50%
swing in speed is plain to see. Ten beats over those 20 frames is even the whole way round. A prime
frame count has no divisor worth moving to, so it keeps the count it was given.

**The picker** searches Wikimedia Commons, which needs no key, answers cross-origin, and states a
licence for every file. Author and licence come back as HTML written by whoever uploaded the file,
so it is parsed detached from the page and only its text is used.

## Development

    node test/test_timing.mjs
    node test/test_tempo.mjs

pull the retiming and the tempo front end out of the page and check them against
`test/timing_cases.json` and `test/tempo_cases.json`. Both fixtures were recorded from the Python
this tool replaced, so the page stays pinned to what that produced rather than to whatever it does
today. The Pages workflow runs both before deploying.

Everything in `site/media/` — the link preview card and the three example videos — is rendered by
the page itself. `tools/make-media.mjs` says at the top of the file how to run it.

## Limitations

- **Deriving tempo from beat marks assumes they are consecutive beats.** Mark every bar instead and
  the tempo comes out too slow by that factor.
- **A frame shorter than a display refresh will not read**, however exactly it is timed. The eased
  curves reach that first, since their shortest frames sit right at the beat. The page warns when
  any duration falls below it.
- **Transparency is flattened onto black**, in the preview as well as the render. Chrome's
  `VideoEncoder` refuses `alpha: "keep"` for every codec, so keeping an alpha channel would mean a
  Firefox-only output in a WebM container.
