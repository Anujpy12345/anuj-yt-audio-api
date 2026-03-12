"""
main.py
Modified for Render Deployment
"""

import secrets
import threading
import os
from flask import Flask, request, jsonify, send_from_directory
from uuid import uuid4
from pathlib import Path
import yt_dlp
import access_manager
from constants import *

# Initialize the Flask application
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return jsonify(message="API is running! Use /convert?url=... to get a token.")

@app.route("/convert", methods=["GET"]) # Changed endpoint name for clarity
def handle_audio_request():
    video_url = request.args.get("url")
    if not video_url:
        return jsonify(error="Missing 'url' parameter in request."), 400

    filename = f"{uuid4()}.mp3"
    # Ensure downloads directory exists
    os.makedirs(ABS_DOWNLOADS_PATH, exist_ok=True)
    output_path = Path(ABS_DOWNLOADS_PATH) / filename

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path).replace('.mp3', ''), # yt-dlp adds extension
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }],
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        return jsonify(error="Failed to download or convert audio.", detail=str(e)), 500

    return _generate_token_response(filename)

@app.route("/download", methods=["GET"])
def download_audio():
    token = request.args.get("token")
    if not token:
        return jsonify(error="Missing 'token' parameter in request."), 400

    if not access_manager.has_access(token):
        return jsonify(error="Token is invalid or unknown."), 401

    if not access_manager.is_valid(token):
        return jsonify(error="Token has expired."), 408

    try:
        filename = access_manager.get_audio_file(token)
        return send_from_directory(ABS_DOWNLOADS_PATH, filename, as_attachment=True)
    except Exception as e:
        return jsonify(error="File not found.", detail=str(e)), 404

def _generate_token_response(filename: str):
    token = secrets.token_urlsafe(TOKEN_LENGTH)
    access_manager.add_token(token, filename)
    return jsonify(token=token)

if __name__ == "__main__":
    # Start background cleaner
    token_cleaner_thread = threading.Thread(
        target=access_manager.manage_tokens,
        daemon=True
    )
    token_cleaner_thread.start()
    
    # RENDER SPECIFIC: Get port from environment
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
