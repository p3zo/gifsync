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

Drop in a GIF and a song and the page does the first pass itself: beat frames are suggested on the
animation as soon as it decodes, and the song's tempo and the first few of its beats are worked out
as soon as it does. Everything after that is correcting what it got wrong. **Try an example** loads
a bouncing ball and a 120bpm loop, both generated for the job, if you would rather see it working
before supplying your own, and **Browse GIFs** searches Wikimedia Commons if you do not have one to
hand.

The two files sit down the left; lining them up is the work, and takes the middle of the page. A
step that is not ready yet says what is missing rather than sitting there greyed out, and the
fiddly controls stay folded away until you go looking for them.

The waveform shows the song's beats, where every beat frame of the animation will land, and where
the animation loops. The preview plays the two together, round and round from the downbeat.
Changing the tempo while it is playing re-times the animation and the click track underneath it, so
you can nudge it until it locks. Then **Make the video**, and the mp4 saves itself to wherever your
downloads go — you already have something better than this page for watching it back. Progress,
notices and anything that went wrong appear as messages in the bottom corner rather than each
holding a strip of the page open.

To correct the beat frames: **Suggest beat frames** places a fresh set (how many it places is a
setting under *Change them by hand*), or step through with the arrow keys and mark frames with space, or press **Play the GIF**
and hit space on the accents as they go past — slow it down first if they go by too quickly. To
correct the song: drag the tempo, tap it in, click beats onto the waveform, or tap them with `B`
while the preview plays. The first beat mark is the downbeat the animation starts from. Both kinds
of mark have an undo.

**Tempo (BPM)** is the song's tempo. **The GIF hits** is a separate thing: how often the GIF lands
against that tempo, so `twice a beat` runs the animation at double speed without pretending the song
is faster than it is.

**Between beats**, under *More controls*, distributes each beat across the frames between two marks,
and changes the character of the movement more than you would expect. `even` gives every frame the
same duration, so the animation moves at a constant speed and only its landmarks are on the beat.
The two `ease in and out` settings hold the frames midway between beats and flash through the ones
on either side of the beat itself, so the motion snaps on the beat and drifts between them.
Spreading a 500ms beat over eight frames:

| Between beats           | Per-frame durations (ms)                       |
| ----------------------- | ---------------------------------------------- |
| `even`                  | 62.5 each                                      |
| `ease in and out more`  | 3.9, 27.3, 74.2, 144.5, 144.5, 74.2, 27.3, 3.9 |

### Why Wikimedia Commons and not GIPHY

GIPHY has the better GIFs and was the obvious first choice, but its API returns 401 without a key
you have to register for, and a key in a static page on GitHub Pages is a public key. Its
[API terms](https://support.giphy.com/hc/en-us/articles/360028134111-GIPHY-API-Terms-of-Service)
then require the application to be labelled "Powered by GIPHY" with the GIPHY logo and every GIF to
carry its uploader's attribution. Tenor wants a Google Cloud key on the same footing. Neither says
anything either way about re-encoding someone's GIF into an mp4 with a soundtrack on it, which is
what this tool exists to do, and the content is user uploads whose rights GIPHY does not itself
hold.

Commons needs no key, answers cross-origin, and states a licence for every file — CC BY, CC BY-SA,
CC0 or public domain — which is open enough to cover retiming a GIF and handing the result back.
Its `Animated GIF files` category is a little over 31,000 files deep. The catalogue is documentary
and scientific rather than reaction GIFs, which is the price of the licensing being unambiguous.
Openverse was the other keyless candidate and was rejected on content: of 64 GIFs sampled across
eight searches, 8 were actually animated.

Author and licence come back from Commons as HTML written by whoever uploaded the file, so it is
parsed detached from the page and only its text is used.

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

The song's beats are placed by taking the tempo from the model and then sliding that grid across an
envelope of the attacks, leaving it wherever it catches the most. One envelope frame is 5.8ms. Shift
a track by a known amount and the answer shifts with it to within about 10ms, on all three of the
songs here.

Suggested beat frames are an even spread around the loop starting at frame 0, with each mark nudged
onto whichever of its two neighbouring frames changes most. That is a duller idea than it sounds
like it should be, and it is what the evidence supported: neither dance GIF here repeats at its
accent period, so nothing periodic in the pixels finds the accents, and of two dozen candidate
signals only the one-frame nudge beat the plain even spread without ever making it worse. Against
the hand labels it comes out 0.40 and 0.50 frames off, where marks thrown down at random score
about 3.

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

- **How many beats a loop should last is your call.** Nothing in the pixels settles it, and the two
  hand-labelled GIFs here were deliberately run slower and faster than their own frame rate. Eight
  is the starting guess, and the count is a setting rather than something you are asked for up
  front, since there is no way to know it before seeing the animation against the song.
- **Deriving tempo from beat marks assumes they are consecutive beats.** Mark every bar instead and
  the tempo comes out too slow by that factor.
- **A frame shorter than a display refresh will not read**, however exactly it is timed. The eased
  curves reach that first, since their shortest frames sit right at the beat; the page warns when
  any duration falls below it.
- **Transparency is flattened onto a colour**, black unless you pick another under *More controls*,
  and the preview shows the same one. It cannot be kept: Chrome's `VideoEncoder` refuses
  `alpha: "keep"` outright for every codec, so an alpha channel would mean a Firefox-only output in
  a WebM container.
- **Finding the tempo needs the page served**, not opened off the filesystem, and a network
  connection the first time so TensorFlow.js can load. *Try an example* needs it served for the same
  reason. Off a `file://` url both are disabled and say why; everything else works from a file.
