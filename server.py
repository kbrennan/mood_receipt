#!/usr/bin/env python3
"""Local server for Mood Receipt: serves the page and prints receipts on the Polono."""
import argparse
import glob
import io
import os
import signal
import subprocess
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image

QUEUE = "PL80E"
USB_ID = ("0483", "2025")  # The printer disappears from USB when it's switched off.
# The page draws 800x1200, slightly inside a 4x6 label at 203 dpi (812x1218 dots).
LABEL_W, LABEL_H = 800, 1200
SHEET_W, SHEET_H = 812, 1218
ROW_BYTES = (SHEET_W + 7) // 8

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
dry_run_dir = None


def png_to_tspl(png: bytes) -> bytes:
    """Convert an 800x1200 PNG into a TSPL print job. Raises ValueError for anything else."""
    try:
        image = Image.open(io.BytesIO(png))
    except OSError as e:
        raise ValueError("not an image") from e
    if image.size != (LABEL_W, LABEL_H):
        raise ValueError(f"expected {LABEL_W}x{LABEL_H}, got {image.width}x{image.height}")
    mono = image.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("1", dither=Image.Dither.NONE)
    # Labels come out of the printer the other way up from how Karen wants them, so turn the image.
    mono = mono.transpose(Image.Transpose.ROTATE_180)
    # Center by padding with white inside a full-label bitmap at 0,0, a format confirmed on the PL80E.
    sheet = Image.new("1", (ROW_BYTES * 8, SHEET_H), 1)
    sheet.paste(mono, ((SHEET_W - LABEL_W) // 2, (SHEET_H - LABEL_H) // 2))
    # Mode "1" packs rows MSB first with white as 1, which is what TSPL's BITMAP expects.
    header = (
        "SIZE 4,6\r\nGAP 0.12,0\r\nDIRECTION 1\r\nDENSITY 8\r\nCLS\r\n"
        f"BITMAP 0,0,{ROW_BYTES},{SHEET_H},0,"
    ).encode("ascii")
    return header + sheet.tobytes() + b"\r\nPRINT 1\r\n"


def printer_problem() -> str | None:
    """Return a friendly message if the printer can't take a job right now."""
    for device in glob.glob("/sys/bus/usb/devices/*/"):
        try:
            ids = (Path(device, "idVendor").read_text().strip(), Path(device, "idProduct").read_text().strip())
        except OSError:
            continue
        if ids == USB_ID:
            break
    else:
        return "The printer isn't connected. Is it switched on?"
    status = subprocess.run(["lpstat", "-p", QUEUE], capture_output=True, text=True, timeout=5)
    if status.returncode != 0:
        return f"Print queue {QUEUE} wasn't found."
    if "disabled" in status.stdout:
        return f"Print queue {QUEUE} is paused. Run: cupsenable {QUEUE}"
    return None


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify(ok=True)


@app.post("/print")
def print_receipt():
    # Requiring this type means other websites' pages can't trigger a print without a CORS preflight.
    if request.content_type != "image/png":
        return jsonify(message="Expected a PNG."), 415
    try:
        job = png_to_tspl(request.get_data())
    except ValueError as e:
        return jsonify(message=f"Bad receipt image: {e}"), 400

    if dry_run_dir:
        Path(dry_run_dir, "last.tspl").write_bytes(job)
        return jsonify(message="Dry run: saved instead of printing.")

    problem = printer_problem()
    if problem:
        return jsonify(message=problem), 503
    result = subprocess.run(["lp", "-d", QUEUE, "-o", "raw"], input=job, capture_output=True, timeout=15)
    if result.returncode != 0:
        app.logger.error("lp failed: %s", result.stderr.decode(errors="replace"))
        return jsonify(message="The print job failed."), 500
    return jsonify(message="Printing! Thank you for feeling.")


@app.post("/exit")
def exit_kiosk():
    if request.content_type != "application/json":
        return jsonify(message="Expected JSON."), 415
    launcher = os.environ.get("MOOD_KIOSK_PID")
    if not launcher:
        return jsonify(message="Not running in kiosk mode."), 409
    # Reply first; the launcher then closes the browser and this server.
    threading.Timer(0.2, os.kill, (int(launcher), signal.SIGTERM)).start()
    return jsonify(message="Leaving kiosk mode.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", metavar="DIR", help="save print jobs to DIR instead of printing")
    args = parser.parse_args()
    dry_run_dir = args.dry_run
    app.run(host="127.0.0.1", port=args.port, threaded=True)
