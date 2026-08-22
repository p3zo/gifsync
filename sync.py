import argparse
import math
import os
import subprocess

import essentia.standard as es
import numpy as np
from PIL import Image

from easing import CubicEaseInOut, LinearInOut, QuadEaseInOut

# ffmpeg's concat demuxer gives a stream of images a 1/25 timebase, so it rounds every
# frame duration onto a 40ms grid no matter what the list asks for.
CONCAT_TIMEBASE_MS = 40


def get_durations(beat_frames, ms_per_beat, n_frames, interpolation="linear"):
    """Calculate the duration in milliseconds needed to sync the output frames to the beat frames.

    The durations are ordered from the first beat frame, wrapping around the end of the gif, so
    they line up with the playback order produced by get_frame_order.
    """

    if interpolation not in ["linear", "cubic", "quadratic"]:
        raise ValueError(f"{interpolation=} not supported")

    if not beat_frames:
        raise ValueError("At least one beat frame is required.")

    if list(beat_frames) != sorted(set(beat_frames)):
        raise ValueError(f"Beat frames must be sorted and unique, got {beat_frames}.")

    if beat_frames[0] < 0 or beat_frames[-1] >= n_frames:
        raise ValueError(
            f"Beat frames must be within [0, {n_frames - 1}], got {beat_frames}."
        )

    durations = []

    for ix, frame in enumerate(beat_frames):
        next_frame = (
            beat_frames[ix + 1]
            if ix < len(beat_frames) - 1
            else n_frames + beat_frames[0]
        )

        n = next_frame - frame

        lerp = LinearInOut(start=0, end=ms_per_beat, duration=n)
        if interpolation == "cubic":
            lerp = CubicEaseInOut(start=0, end=ms_per_beat, duration=n)
        if interpolation == "quadratic":
            lerp = QuadEaseInOut(start=0, end=ms_per_beat, duration=n)

        x = np.arange(0, n + 1)
        times = list(map(lerp, x))
        durations.extend([i - j for i, j in zip(times[1:], times)])

    if any([i < CONCAT_TIMEBASE_MS for i in durations]):
        print(
            f"WARNING: ffmpeg rounds frame durations onto a {CONCAT_TIMEBASE_MS}ms grid, and some of these "
            "are shorter than that,\nso the motion will not land where the interpolation puts it. "
            "Try using fewer beat frames\nor a different interpolation method."
        )

    return durations


def get_frame_order(first_beat_frame, n_frames):
    """The order to play the gif's frames in, starting on the first beat frame.

    The animation has to open on a beat frame for the beat frames to land on the audio's beats.
    Starting anywhere else offsets every one of them by however long it takes to reach the first,
    which is a fraction of a beat rather than a whole one.
    """

    return [(first_beat_frame + i) % n_frames for i in range(n_frames)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Estimates the tempo of an audio file, then reassembles the frames of a GIF to sync its movement
        to the beat.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--audio_filepath",
        type=str,
        required=True,
        help="The path to the audio file.",
    )
    parser.add_argument(
        "--gif_filepath",
        type=str,
        required=True,
        help="The path to the gif.",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        help="The BPM of the audio. Will be estimated if not passed.",
    )
    parser.add_argument(
        "--beat_frames",
        nargs="+",
        type=int,
        required=True,
        help="The indices (zero-indexed) of the GIF frames to align with the beat.",
    )
    parser.add_argument(
        "--tempo_multiplier",
        type=float,
        default=1.0,
        help="A multiplier applied to the extracted tempo. Speeds up or slows down the animation.",
    )
    parser.add_argument(
        "--interpolation",
        type=str,
        default="linear",
        help="The method of interpolation to use. Options: [linear, cubic, quadratic]",
    )
    parser.add_argument(
        "--output_directory",
        type=str,
        default=".",
        help="The directory to which the output will be saved.",
    )
    args = parser.parse_args()

    # Load audio
    audio_filepath = args.audio_filepath

    # Estimate BPM
    audio_11khz = es.MonoLoader(filename=audio_filepath, sampleRate=11025)()

    global_bpm = args.bpm
    if global_bpm is None:
        global_bpm, local_bpm, local_probs = es.TempoCNN(
            graphFilename="tempocnn/deeptemp-k16-3.pb"
        )(audio_11khz)

        if global_bpm == 0:
            raise RuntimeError(f"Could not estimate BPM from {audio_filepath}.")

        print(f"Estimated BPM: {global_bpm}")

    if global_bpm <= 0:
        raise ValueError(f"BPM must be positive, got {global_bpm}.")

    if args.tempo_multiplier <= 0:
        raise ValueError(
            f"Tempo multiplier must be positive, got {args.tempo_multiplier}."
        )

    beats_per_second = global_bpm / 60
    beats_per_second *= args.tempo_multiplier

    seconds_per_beat = 1 / beats_per_second
    ms_per_beat = seconds_per_beat * 1000

    # Load gif
    gif_filepath = args.gif_filepath
    im = Image.open(gif_filepath)

    beat_frames = args.beat_frames

    # Get output frame durations in ms
    durations = get_durations(
        beat_frames, ms_per_beat, im.n_frames, interpolation=args.interpolation
    )

    # Create intermediate image & metadata files for ffmpeg in a temporary directory
    gif_name = os.path.splitext(os.path.basename(gif_filepath))[0]
    tmpdir = f"tmp_{gif_name}"
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

    tmp_txt = os.path.join(tmpdir, "input.txt")

    for frame in range(im.n_frames):
        print(f"Saving frame {frame}")
        im.seek(frame)
        im.save(os.path.join(tmpdir, f"{frame}.png"))

    frame_order = get_frame_order(beat_frames[0], im.n_frames)

    # Repeat the frame list itself rather than looping the encoded video with -stream_loop,
    # which does not restart cleanly on the beat and slips a little further at every seam.
    audio_ms = len(audio_11khz) / 11025 * 1000
    n_loops = math.ceil(audio_ms / (len(beat_frames) * ms_per_beat))

    with open(tmp_txt, "w") as fh:
        for _ in range(n_loops):
            for ix, frame in enumerate(frame_order):
                fh.write(f"file '{frame}.png'\n")
                fh.write(f"duration {durations[ix]}ms\n")

    audio_name = os.path.splitext(os.path.basename(audio_filepath))[0]
    os.makedirs(args.output_directory, exist_ok=True)
    output_filepath = os.path.join(
        args.output_directory, f"{audio_name}_{gif_name}.mp4"
    )

    # Stitch the frames together and add the audio, trimming the extra loop off the end.
    # -fps_mode passthrough keeps every frame; -vsync vfr drops the short ones outright.
    # TODO: preserve transparency channels of input PNGs when concatenating
    subprocess.check_call(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-i",
            tmp_txt,
            "-i",
            audio_filepath,
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-y",
            output_filepath,
        ]
    )

    # Clean up temporary files
    subprocess.run(["rm", "-rf", f"{tmpdir}"])

    print(f"Result saved to {output_filepath}")
