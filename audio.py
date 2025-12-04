import streamlit as st
from moviepy.editor import VideoFileClip
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import tempfile
import zipfile
import io
import os
from scipy.io import wavfile
from math import ceil

# ---------- UTILS ---------- #

def compress_image(img, max_bytes=5 * 1024 * 1024):
    """Compress PIL image to <= 5 MB."""
    quality = 95
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    size = len(buffer.getvalue())

    while size > max_bytes and quality > 10:
        quality -= 10
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        size = len(buffer.getvalue())

    return buffer.getvalue()

def create_spectrogram(audio, sr):
    """Create spectrogram image from audio chunk."""
    plt.figure(figsize=(6, 3))
    plt.specgram(audio, Fs=sr)
    plt.axis("off")

    buf = io.BytesIO()
    plt.savefig(buf, format="jpeg", bbox_inches="tight", pad_inches=0)
    plt.close()

    buf.seek(0)
    return Image.open(buf)

# ---------- MAIN PROCESS ---------- #

def process_video(video_bytes):
    """Split video → extract audio → cut audio → extract frames → compress images."""
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_video.write(video_bytes)
    temp_video.close()

    video = VideoFileClip(temp_video.name)
    duration = video.duration
    mid = duration / 2

    parts = [
        ("part1", 0, mid),
        ("part2", mid, duration)
    ]

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, start, end in parts:

            # --- VIDEO SPLIT ---
            clip = video.subclip(start, end)
            tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            clip.write_videofile(tmp_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)

            with open(tmp_path, "rb") as f:
                zf.writestr(f"{name}.mp4", f.read())

            os.remove(tmp_path)

            # --- AUDIO EXTRACTION ---
            audio_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            clip.audio.write_audiofile(audio_tmp, fps=22050, verbose=False, logger=None)
            sr, audio_data = wavfile.read(audio_tmp)

            wav_bytes = open(audio_tmp, "rb").read()
            zf.writestr(f"{name}_full_audio.wav", wav_bytes)
            os.remove(audio_tmp)

            # Convert to float
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)

            audio_data = audio_data.astype(np.float32)
            chunk_len = 5 * sr
            total_samples = len(audio_data)
            chunks = ceil(total_samples / chunk_len)

            # --- AUDIO CHUNKS + SPECTROGRAMS ---
            for i in range(chunks):
                s = i * chunk_len
                e = min(s + chunk_len, total_samples)
                chunk = audio_data[s:e]

                # Save chunk
                chunk_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
                wavfile.write(chunk_path, sr, chunk.astype(np.float32))
                zf.writestr(f"{name}_audio_chunk_{i}.wav", open(chunk_path, "rb").read())
                os.remove(chunk_path)

                # Spectrogram
                spec_img = create_spectrogram(chunk, sr)
                compressed = compress_image(spec_img)
                zf.writestr(f"{name}_spectrogram_{i}.jpg", compressed)

            # --- EXTRACT FRAMES ---
            frame_count = int(clip.duration)
            for i in range(frame_count):
                frame = clip.get_frame(i)
                img = Image.fromarray(frame)
                compressed = compress_image(img)
                zf.writestr(f"{name}_frame_{i}.jpg", compressed)

        video.close()

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# ---------- STREAMLIT UI ---------- #

st.title("Video Split + Audio Cut + Image Extract (<=5MB images)")

uploaded = st.file_uploader("Upload video", type=["mp4", "mov", "mkv"])

if uploaded:
    st.video(uploaded)
    if st.button("Process Video"):
        with st.spinner("Processing..."):
            try:
                zip_file = process_video(uploaded.getvalue())
                st.success("Done!")

                st.download_button(
                    "Download ZIP",
                    data=zip_file,
                    file_name="processed_video.zip",
                    mime="application/zip"
                )

            except Exception as e:
                st.error(f"Error: {e}")
