"""Serves docs/index.html and lets it render through sync.py.

    python marker.py

The page works on its own from the filesystem, where it renders in the browser. Served
from here it also gets a "Render with sync.py" button, which runs the real pipeline:
essentia for the tempo, ffmpeg for the encode.
"""

import argparse
import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

REPO = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(REPO, "docs", "index.html")
MAX_UPLOAD_BYTES = 256 * 1024 * 1024


def trim_audio(source, downbeat, destination, emit):
    """Cut the lead-in off the audio so it starts on the downbeat, which sync.py assumes."""

    emit(f"Trimming {downbeat:.3f}s off the front of the audio")
    subprocess.check_call(
        # -ss ahead of -i seeks accurately when the audio is being re-encoded anyway
        ["ffmpeg", "-loglevel", "error", "-ss", f"{downbeat}", "-i", source,
         "-c:a", "aac", "-b:a", "192k", "-y", destination]
    )


def run_sync(job_dir, gif_path, audio_path, params, emit):
    """Run sync.py in the job directory and stream its output. Returns the output filename."""

    command = [
        sys.executable, os.path.join(REPO, "sync.py"),
        "--audio_filepath", audio_path,
        "--gif_filepath", gif_path,
        "--beat_frames", *[str(f) for f in params["beat_frames"]],
        "--tempo_multiplier", str(params["tempo_multiplier"]),
        "--interpolation", params["interpolation"],
        "--output_directory", job_dir,
    ]
    if params.get("bpm"):
        command += ["--bpm", str(params["bpm"])]

    emit("$ " + " ".join(command))

    # sync.py reads tempocnn/ relative to the working directory, so link it in rather than
    # running in the repo and leaving the script's scratch directory behind on failure
    os.symlink(os.path.join(REPO, "tempocnn"), os.path.join(job_dir, "tempocnn"))

    process = subprocess.Popen(
        command, cwd=job_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in process.stdout:
        emit(line.rstrip())

    if process.wait() != 0:
        raise RuntimeError(f"sync.py exited with status {process.returncode}")

    audio_stem = os.path.splitext(os.path.basename(audio_path))[0]
    gif_stem = os.path.splitext(os.path.basename(gif_path))[0]
    return f"{audio_stem}_{gif_stem}.mp4"


def render(params, job_dir, emit):
    inputs = os.path.join(job_dir, "inputs")
    os.makedirs(inputs)

    gif_path = os.path.join(inputs, os.path.basename(params["gif_name"]))
    with open(gif_path, "wb") as fh:
        fh.write(base64.b64decode(params["gif_b64"]))

    # Keep the original stem: sync.py names its output after it
    audio_stem = os.path.splitext(os.path.basename(params["audio_name"]))[0]
    uploaded = os.path.join(inputs, "uploaded" + os.path.splitext(params["audio_name"])[1])
    with open(uploaded, "wb") as fh:
        fh.write(base64.b64decode(params["audio_b64"]))

    audio_path = os.path.join(inputs, audio_stem + ".m4a")
    if params["downbeat"] > 0:
        trim_audio(uploaded, params["downbeat"], audio_path, emit)
    else:
        os.rename(uploaded, audio_path)

    return run_sync(job_dir, gif_path, audio_path, params, emit)


def estimate_bpm(params, job_dir):
    import essentia.standard as es

    path = os.path.join(job_dir, "bpm" + os.path.splitext(params["audio_name"])[1])
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(params["audio_b64"]))

    audio = es.MonoLoader(filename=path, sampleRate=11025)()
    global_bpm, _, _ = es.TempoCNN(
        graphFilename=os.path.join(REPO, "tempocnn", "deeptemp-k16-3.pb")
    )(audio)

    if global_bpm == 0:
        raise RuntimeError("Could not estimate the BPM of this audio.")

    return float(global_bpm)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    jobs = {}

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}", file=sys.stderr)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("content-length") or 0)
        if length > MAX_UPLOAD_BYTES:
            raise ValueError(f"Upload of {length} bytes is over the {MAX_UPLOAD_BYTES} byte limit.")
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        route = urlparse(self.path)

        if route.path in ("/", "/index.html"):
            with open(PAGE, "rb") as fh:
                self.send_bytes(fh.read(), "text/html; charset=utf-8")

        elif route.path == "/api/health":
            self.send_json({
                "ok": True,
                "ffmpeg": shutil.which("ffmpeg") is not None,
                "essentia": importlib.util.find_spec("essentia") is not None,
            })

        elif route.path == "/api/result":
            name = (parse_qs(route.query).get("name") or [""])[0]
            # Only ever hand back a file this process just produced, by exact name
            path = self.jobs.get(name)
            if not path or not os.path.isfile(path):
                self.send_json({"error": "No such result."}, 404)
                return
            with open(path, "rb") as fh:
                self.send_bytes(fh.read(), "video/mp4")

        else:
            self.send_json({"error": "Not found."}, 404)

    def do_POST(self):
        route = urlparse(self.path)

        if route.path == "/api/bpm":
            job_dir = tempfile.mkdtemp(prefix="gifsync-bpm-")
            try:
                self.send_json({"bpm": estimate_bpm(self.read_json(), job_dir)})
            except Exception as err:
                traceback.print_exc()
                self.send_json({"error": f"{type(err).__name__}: {err}"}, 500)
            finally:
                shutil.rmtree(job_dir, ignore_errors=True)

        elif route.path == "/api/render":
            self.do_render()

        else:
            self.send_json({"error": "Not found."}, 404)

    def do_render(self):
        try:
            params = self.read_json()
        except Exception as err:
            self.send_json({"error": f"{type(err).__name__}: {err}"}, 400)
            return

        self.send_response(200)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()

        def emit(line):
            data = (line + "\n").encode()
            self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")
            self.wfile.flush()

        job_dir = tempfile.mkdtemp(prefix="gifsync-job-")
        try:
            name = render(params, job_dir, emit)
            path = os.path.join(job_dir, name)
            if not os.path.isfile(path):
                raise RuntimeError(f"sync.py finished but {name} is not there.")
            self.jobs[name] = path
            emit(f"RESULT {name}")
        except Exception as err:
            traceback.print_exc()
            emit(f"ERROR {type(err).__name__}: {err}")
            shutil.rmtree(job_dir, ignore_errors=True)

        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Loopback by default. This runs sync.py on whatever it is sent, so only "
        "widen it (0.0.0.0 in a container) on a network you trust.",
    )
    args = parser.parse_args()

    if not os.path.isfile(PAGE):
        raise SystemExit(f"{PAGE} is missing.")

    print(f"gifsync beat marker on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
