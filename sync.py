import argparse

import essentia.standard as es
from PIL import GifImagePlugin, Image

# Define loading strategy to retain input alpha channels in all frames of the output GIF
GifImagePlugin.LOADING_STRATEGY = GifImagePlugin.LoadingStrategy.RGB_ALWAYS

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--song_filepath",
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

    # Load audio
    song_filepath = args.song_filepath

    # Estimate BPM
    audio_11khz = es.MonoLoader(filename=song_filepath, sampleRate=11025)()
    global_bpm, local_bpm, local_probs = es.TempoCNN(
        graphFilename="tempocnn/deeptemp-k16-3.pb"
    )(audio_11khz)

    print(f"BPM: {global_bpm}")

    beats_per_second = global_bpm / 60
    seconds_per_beat = 1 / beats_per_second

    # Load gif
    gif_filepath = args.gif_filepath
    im = Image.open(gif_filepath)

    # Iterate through the frames
    frames = []
    print("Input gif frames:")
    try:
        while 1:
            frames.append(im.copy())
            ix = im.tell()
            print("  ", ix, im.format, im.size, im.mode, im.info)
            im.seek(ix + 1)
    except EOFError:
        pass

    n_frames = im.n_frames

    hit_frame_ixs = [int(i) for i in args.hit_frame_ixs]
    print(hit_frame_ixs)

    perfect_loop = args.perfect_loop
    if perfect_loop:
        hit_frame_ixs.append(n_frames)

    # seconds, sync'd with beats @ 124 bpm
    beat_times = [seconds_per_beat * i for i in range(len(hit_frame_ixs))]

    original_duration = frames[0].info["duration"]
    durations = []
    for ix, (hit_frame_ix, htime) in enumerate(zip(hit_frame_ixs, beat_times)):
        if ix == 0:
            continue
        print(f"hit frame ix {hit_frame_ix} at {htime}")
        # TODO: what duration should the hit frames have?

        # assign an equal duration to all frames in between the hit frames to linearly interpolate the movement
        n_frames_btwn = hit_frame_ix - hit_frame_ixs[ix - 1]
        btwn_frame_duration = (htime - beat_times[ix - 1]) / n_frames_btwn * 1000  # ms
        print(
            f"  {n_frames_btwn} frames btwn {hit_frame_ixs[ix - 1]} and {hit_frame_ix} w duration {btwn_frame_duration} ms"
        )

        durations.extend([btwn_frame_duration] * (n_frames_btwn + 1))

    # Duration values get rounded to the nearest 10 ms, and 20 seems to be the minimum value
    # See https://superuser.com/questions/569924/why-is-the-gif-i-created-so-slow/569950#569950
    #   "use a delay of at least two hundreds of a second in all cases."
    # TODO: get around these limitations by stitching the output frames to a video format instead of saving as gif
    assert not any(d < 20 for d in durations)

    output_filepath = args.output_filepath

    # TODO: fix output transparency channel
    frames[0].save(
        output_filepath,
        save_all=True,
        append_images=frames[1 : len(durations)],
        duration=durations,
        loop=0,
    )

    print("Output gif frames:")
    out_im = Image.open(output_filepath)
    try:
        while 1:
            ix = out_im.tell()
            print("  ", ix, out_im.format, out_im.size, out_im.mode, out_im.info)
            out_im.seek(ix + 1)
    except EOFError:
        pass
