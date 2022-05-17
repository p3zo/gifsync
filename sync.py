import argparse
import os
import subprocess

import essentia.standard as es
from PIL import Image

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
        "--output_filepath",
        help="The path where the output will be saved.",
    )
    parser.add_argument(
        "--perfect_loop",
        action="store_true",
        help="A gif is a perfect loop if the end of a gif transitions perfectly back to the start. Note that if the input not a perfect loop, the end frames will be cut off to create one",
    )
    args = parser.parse_args()

    if not args.audio_filepath:
        args.audio_filepath = "audio/gypsy.mp3"
        args.gif_filepath = "input.gif"
        args.hit_frame_ixs = [0, 4]
        args.output_filepath = "output.mp4"
        args.perfect_loop = True

    # Load audio
    audio_filepath = args.audio_filepath

    # Estimate BPM
    audio_11khz = es.MonoLoader(filename=audio_filepath, sampleRate=11025)()
    global_bpm, local_bpm, local_probs = es.TempoCNN(
        graphFilename="tempocnn/deeptemp-k16-3.pb"
    )(audio_11khz)

    print(f"BPM: {global_bpm}")

    beats_per_second = global_bpm / 60
    seconds_per_beat = 1 / beats_per_second

    # Load gif
    gif_filepath = args.gif_filepath
    im = Image.open(gif_filepath)

    hit_frame_ixs = [int(i) for i in args.hit_frame_ixs]

    if args.perfect_loop:
        hit_frame_ixs.append(im.n_frames)

    # Get seconds for beats @ the estimated bpm
    beat_times = [seconds_per_beat * i for i in range(len(hit_frame_ixs))]

    # Calculate the duration of each output frame to sync the hits to the audio
    durations = []
    for ix, (hit_frame_ix, htime) in enumerate(zip(hit_frame_ixs, beat_times)):
        if ix == 0:
            continue

        # Assign an equal duration to all frames in between the hit frames to linearly interpolate the movement
        # TODO: what duration should the hit frames have?
        n_frames_btwn = hit_frame_ix - hit_frame_ixs[ix - 1]
        btwn_frame_duration = (htime - beat_times[ix - 1]) / n_frames_btwn * 1000  # ms

        durations.extend([btwn_frame_duration] * (n_frames_btwn + 1))

    # Create intermediate image & metadata files for ffmpeg in a temporary directory
    tmpdir = f"tmp_{os.path.splitext(os.path.basename(gif_filepath))[0]}"
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

    tmp_txt = os.path.join(tmpdir, "input.txt")
    tmp_mp4 = os.path.join(tmpdir, "tmp.mp4")

    with open(tmp_txt, "w") as fh:
        im = Image.open(gif_filepath)
        try:
            while 1:
                ix = im.tell()

                img_filename = f"{ix}.png"
                im.save(os.path.join(tmpdir, img_filename), duration=durations[ix])

                fh.write(f"file '{img_filename}'\n")
                fh.write(f"duration {durations[ix]}ms\n")

                im.seek(ix + 1)
        except EOFError:
            pass

    # Stitch the images together into a video
    # TODO: preserve transparency channels of input PNGs when concatenating
    check = subprocess.check_call(
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
            tmp_mp4,
        ]
    )

    if check == 0:
        # Add audio and loop the images to the length of the audio
        # TODO: running this script fails here with an encoding error, but copy/pasting into a REPL doesn't. Why?
        # TODO: output has several extra video loops after audio ends. Video should end with audio.
        check2 = subprocess.check_call(
            [
                "ffmpeg",
                "-stream_loop",
                "-1",
                "-i",
                tmp_mp4,
                "-i",
                audio_filepath,
                "-shortest",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-y",
                args.output_filepath,
            ]
        )

        # Clean up temporary files
        if check2 == 0:
            subprocess.run(["rm", "-rf", f"{tmpdir}"])
