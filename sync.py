import argparse
import os
import subprocess

import essentia.standard as es
from PIL import Image


def get_durations(beat_frames, seconds_per_beat, n_frames):
    """Calculate the duration in seconds needed for each output frame to sync the hits to the beat."""

    durations = []

    for ix, bframe in enumerate(beat_frames):
        next_bframe = (
            beat_frames[ix + 1]
            if ix < len(beat_frames) - 1
            else n_frames + beat_frames[0]
        )

        # Assign an equal duration to all frames in between the hit frames to linearly interpolate the movement
        n = next_bframe - bframe
        duration = seconds_per_beat / n * 1000  # seconds

        print(f"{bframe} to {next_bframe}: {n} frames @ {duration} ms ea")

        durations.extend([duration] * n)

    # Re-align the sequence with the input frames
    return durations[beat_frames[0] :] + durations[: beat_frames[0]]


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

    beat_frames = [int(i) for i in args.beat_frames]

    # Get output frame durations
    durations = get_durations(beat_frames, seconds_per_beat, im.n_frames)

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
