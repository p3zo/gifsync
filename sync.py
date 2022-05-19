"""Estimates the tempo of an audio file then reassembles the frames of a GIF to sync its animation to the beat."""

import argparse
import os
import subprocess

import essentia.standard as es
from PIL import Image


def get_durations(hit_frame_ixs, seconds_per_beat, n_frames):
    """Calculate the duration in seconds needed for each output frame to sync the hits to the beat.

    Assumptions:
        1. The gif is a perfect loop, i.e. the last frame transitions perfectly back to the first
        2. The audio starts on a downbeat
    """

    # TODO: address the case where the gif isn't a perfect loop
    # TODO: provide a `first_beat` param to offset the start of the audio

    durations = []

    for ix, hit_frame_ix in enumerate(hit_frame_ixs):
        next_hit_frame = (
            hit_frame_ixs[ix + 1]
            if ix < len(hit_frame_ixs) - 1
            else n_frames + hit_frame_ixs[0]
        )

        # Assign an equal duration to all frames in between the hit frames to linearly interpolate the movement
        n_bf = next_hit_frame - hit_frame_ix
        bf_duration = seconds_per_beat / n_bf * 1000  # seconds

        print(
            f"{hit_frame_ix} to {next_hit_frame}: {n_bf} frames @ {bf_duration} ms ea"
        )

        durations.extend([bf_duration] * n_bf)

    # Re-align the sequence with the input frames
    return durations[hit_frame_ixs[0] :] + durations[: hit_frame_ixs[0]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio_filepath",
        help="The path to the song file to sync the gif to.",
    )
    parser.add_argument(
        "--gif_filepath",
        help="The path to the gif to be sync'd.",
    )
    parser.add_argument(
        "--hit_frame_ixs",
        nargs="+",
        help="The frames in which the 'hits' in the movement occur. Subjective and manually labeled.",
    )
    parser.add_argument(
        "--tempo_multiplier",
        type=float,
        default=1.0,
        help="Multiplier to apply to the extracted tempo. Speeds up or slows down the animation.",
    )
    parser.add_argument(
        "--output_directory",
        default=".",
        help="The directory to which the output will be saved.",
    )
    args = parser.parse_args()

    # Load audio
    audio_filepath = args.audio_filepath

    # Estimate BPM
    audio_11khz = es.MonoLoader(filename=audio_filepath, sampleRate=11025)()
    global_bpm, local_bpm, local_probs = es.TempoCNN(
        graphFilename="tempocnn/deeptemp-k16-3.pb"
    )(audio_11khz)

    if global_bpm == 0:
        raise RuntimeError(f"Could not estimate BPM from {audio_filepath}.")

    print(f"BPM: {global_bpm}")

    beats_per_second = global_bpm / 60
    beats_per_second *= args.tempo_multiplier

    seconds_per_beat = 1 / beats_per_second

    # Load gif
    gif_filepath = args.gif_filepath
    im = Image.open(gif_filepath)

    hit_frame_ixs = [int(i) for i in args.hit_frame_ixs]

    # Get output frame durations needed for hits to sync with beats
    durations = get_durations(hit_frame_ixs, seconds_per_beat, im.n_frames)

    # Create intermediate image & metadata files for ffmpeg in a temporary directory
    gif_name = os.path.splitext(os.path.basename(gif_filepath))[0]
    tmpdir = f"tmp_{gif_name}"
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

    tmp_txt = os.path.join(tmpdir, "input.txt")
    tmp_vid = os.path.join(tmpdir, "tmp.mov")

    with open(tmp_txt, "w") as fh:
        im = Image.open(gif_filepath)
        try:
            while 1:
                ix = im.tell()
                print(f"Saving frame {ix}")
                img_filename = f"{ix}.png"
                im.save(
                    os.path.join(tmpdir, img_filename),
                    duration=durations[ix],
                    disposal=3,  # 3 - Restore to previous content
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
