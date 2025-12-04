import streamlit as st
from moviepy.editor import VideoFileClip

st.title("Video to Audio Converter")

uploaded_file = st.file_uploader("Upload a video file", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    with open("input_video.mp4", "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.video(uploaded_file)

    if st.button("Extract Audio"):
        try:
            video = VideoFileClip("input_video.mp4")
            audio = video.audio
            audio.write_audiofile("output_audio.mp3")

            with open("output_audio.mp3", "rb") as audio_file:
                st.download_button(
                    label="Download MP3",
                    data=audio_file,
                    file_name="audio.mp3",
                    mime="audio/mp3"
                )

            st.success("Audio extracted successfully!")

        except Exception as e:
            st.error(f"Error: {e}")
