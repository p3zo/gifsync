import argparse
import os
import subprocess

import numpy as np
import essentia.standard as es
from PIL import Image


class EasingBase:
    """From https://github.com/semitable/easing-functions"""

    limit = (0, 1)

    def __init__(self, start: float = 0, end: float = 1, duration: float = 1):
        self.start = start
        self.end = end
        self.duration = duration

    def func(self, t: float) -> float:
        raise NotImplementedError

    def ease(self, alpha: float) -> float:
        t = self.limit[0] * (1 - alpha) + self.limit[1] * alpha
        t /= self.duration
        a = self.func(t)
        return self.end * a + self.start * (1 - a)

    def __call__(self, alpha: float) -> float:
        return self.ease(alpha)


class LinearInOut(EasingBase):
    def func(self, t: float) -> float:
        return t


class QuadEaseInOut(EasingBase):
    def func(self, t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return (-2 * t * t) + (4 * t) - 1


class CubicEaseInOut(EasingBase):
    def func(self, t: float) -> float:
        if t < 0.5:
            return 4 * t * t * t
        p = 2 * t - 2
        return 0.5 * p * p * p + 1


def get_durations(beat_frames, ms_per_beat, n_frames, interpolation="linear"):
    """Calculate the duration in milliseconds needed to sync the output frames to the beat frames"""

    if interpolation not in ["linear", "cubic", "quadratic"]:
        raise ValueError(f"{interpolation=} not supported")

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

    # Re-align the sequence with the input frames
    aligned = durations[beat_frames[0] :] + durations[: beat_frames[0]]

    if any([i < 2 for i in aligned]):
        print(
            "WARNING: Durations less than 2ms are not processed well by ffmpeg (TODO: source?).\nTry using fewer beat frames or a different interpolation method."
        )

    return aligned


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Estimates the tempo of an audio file, then reassembles the frames of a GIF to sync its movement
        to the beat.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--audio_filepath",
        type=str,
        help="The path to the audio file.",
    )
    parser.add_argument(
        "--gif_filepath",
        type=str,
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
    if not global_bpm:
        global_bpm, local_bpm, local_probs = es.TempoCNN(
            graphFilename="tempocnn/deeptemp-k16-3.pb"
        )(audio_11khz)

        if global_bpm == 0:
            raise RuntimeError(f"Could not estimate BPM from {audio_filepath}.")

        print(f"Estimated BPM: {global_bpm}")

    beats_per_second = global_bpm / 60
    beats_per_second *= args.tempo_multiplier

    seconds_per_beat = 1 / beats_per_second
    ms_per_beat = seconds_per_beat * 1000

    # Load gif
    gif_filepath = args.gif_filepath
    im = Image.open(gif_filepath)

    beat_frames = [int(i) for i in args.beat_frames]

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
    tmp_vid = os.path.join(tmpdir, "tmp.mov")

    with open(tmp_txt, "w") as fh:
        try:
            while 1:
                ix = im.tell()
                print(f"Saving frame {ix}")
                img_filename = f"{ix}.png"
                im.save(
                    os.path.join(tmpdir, img_filename),
                    duration=durations[ix],
                    disposal=3,  # 3: Restore to previous content
                )

                fh.write(f"file '{img_filename}'\n")
                fh.write(f"duration {durations[ix]}ms\n")

                im.seek(ix + 1)
        except EOFError:
            pass

    # Stitch the images together into a video
    # TODO: preserve transparency channels of input PNGs when concatenating
    subprocess.check_call(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-i",
            tmp_txt,
            "-vsync",
            "vfr",
            "-pix_fmt",
            "yuv420p",
            "-y",
            tmp_vid,
        ]
    )

    audio_name = os.path.splitext(os.path.basename(audio_filepath))[0]
    output_filepath = os.path.join(
        args.output_directory, f"{audio_name}_{gif_name}.mp4"
    )

    # Add audio and loop the video to the length of the audio
    subprocess.check_call(
        [
            "ffmpeg",
            "-stream_loop",
            "-1",
            "-i",
            tmp_vid,
            "-i",
            audio_filepath,
            "-c:v",
            "copy",
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
