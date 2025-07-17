import streamlit as st
from extract_reels import fetch_instagram_reels, extract_and_save_reel_data

import requests
import os
from dotenv import load_dotenv
from openai import OpenAI
import urllib.request
import re
import json
import cv2
from PIL import Image
from io import BytesIO
import base64
import tempfile


def analyze_video_with_snapshots(video_url, interval_sec=10, max_frames=5):
    try:
        video_path = "temp_video.mp4"
        urllib.request.urlretrieve(video_url, video_path)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = int(total_frames / fps)

        snapshots = []
        for sec in range(0, duration, interval_sec):
            cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
            ret, frame = cap.read()
            if not ret:
                continue
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(frame_rgb)
            snapshots.append(img_pil)
            if len(snapshots) >= max_frames:
                break

        cap.release()
        os.remove(video_path)

        visual_descriptions = []
        for img in snapshots:
            base64_img = image_to_base64(img)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": "Describe this video frame in detail."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                    ]}
                ],
                max_tokens=300
            )
            caption = response.choices[0].message.content.strip()
            visual_descriptions.append(caption)

        return "\n".join(visual_descriptions)

    except Exception as e:
        return f"⚠️ Video analysis error: {e}"


def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()


def extract_industry_insights_from_visuals(visual_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are an expert video analyst working for a media agency. "
                    "Your job is to extract only *industry-relevant insights* from visual descriptions. "
                    "Ignore generic or personal content like people standing, smiling, or backgrounds. "
                    "Focus on things that indicate a niche, topic, market, brand, event, or any industrial/commercial element. "
                    "Return a concise paragraph summarizing the relevant content only."
                )},
                {"role": "user", "content": f"Here are the visual frame descriptions:\n{visual_text}"}
            ],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT filtering error: {e}"


OPENAI_API = st.secrets["api"]["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API)


def transcribe_with_openai_whisper(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1"
            )
        return transcript.text
    except Exception as e:
        st.error(f"OpenAI Whisper API error: {e}")
        return None


def query_openai(subtitles):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    """You are a professional video content creator and scriptwriter with expertise in turning raw subtitles into engaging, 
                    shareable video scripts. Your scripts should include:
                    1. A compelling hook to grab the viewer's attention in the first 5 seconds.
                    2. A clear introduction that sets context.
                    3. A logical flow that weaves in the original subtitles verbatim where they add authenticity.
                    4. Brief expansions or transitions that enhance clarity, but never alter the meaning of the subtitle text.
                    5. A strong closing with a clear call to action (e.g., “Like, share, and subscribe”).
                    6. On-screen text cues and suggestions for visuals."""
                )},
                {"role": "user", "content": f"Here are the subtitles: {subtitles}"}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error: {e}"


def sanitize_filename(url):
    return re.sub(r'[^\w\-_.]', '_', url.split("/")[-1].split("?")[0])


# ---- Streamlit UI ----
def main():
    st.title("🎯 Instagram Reels Caption & Subtitle Generator using OpenAI Whisper")

    username = st.text_input("Enter a public Instagram username")
    limit = st.slider("Number of reels to fetch", 1, 100, 10)

    if st.button("Extract & Generate Captions + Subtitles"):
        if not username:
            st.warning("Please enter a username.")
            return

        with st.spinner(f"Fetching reels for {username}..."):
            reels = fetch_instagram_reels(username, limit)

        if not reels:
            st.error("No reels found or invalid username.")
            return

        high_perf_reels = extract_and_save_reel_data(reels, username)

        if not high_perf_reels:
            st.info("No high-performing reels (≥1M views) found.")
            return

        st.success(f"✅ {len(high_perf_reels)} reels found. Generating captions and subtitles...")

        output_lines = []

        for item in high_perf_reels:
            audio_url = item.get("m4a_url")
            video_url = item.get("video_url")

            subtitles = "N/A"
            visual_description = "N/A"

            if video_url:
                visual_text = analyze_video_with_snapshots(video_url)
                visual_description = extract_industry_insights_from_visuals(visual_text)

            if audio_url:
                try:
                    audio_filename = sanitize_filename(audio_url)
                    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=True) as tmp_file:
                        urllib.request.urlretrieve(audio_url, tmp_file.name)
                        subtitles = transcribe_with_openai_whisper(tmp_file.name)

                except Exception as e:
                    subtitles = f"⚠️ Transcription error: {e}"

            if subtitles and isinstance(subtitles, str) and subtitles.strip() and not subtitles.startswith("⚠️"):
                script = query_openai(subtitles)
            else:
                script = "⚠️ Subtitle transcription failed. No script generated."

            # Add to output summary
            output_lines.append(f"🔗 URL: {item['url']}")
            output_lines.append(f"💬 Caption:\n{script}")
            output_lines.append(f"🎧 Subtitles:\n{subtitles}")
            output_lines.append(f"🖼️ Visual Summary:\n{visual_description}")
            output_lines.append("-" * 50 + "\n")

        final_text = "\n".join(output_lines)

        st.subheader("📄 Results: Captions & Subtitles")
        st.text_area("📋 Preview Output", final_text, height=400)

        st.download_button(
            label="📥 Download Results as TXT",
            data=final_text,  # In-memory, no file
            file_name=f"{username}_reels_output.txt",
            mime="text/plain"
        )


if __name__ == "__main__":
    main()
