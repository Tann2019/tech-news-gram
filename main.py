import requests
from transformers import pipeline
from gtts import gTTS
import subprocess
import os
import random
import json
from datetime import datetime, timedelta
from newspaper import Article
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch API keys from environment variables
api_key = os.getenv("NEWSAPI_KEY")
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")


# Fetch Tech News with Full Content
def fetch_tech_news(api_key):
    url = f"https://newsapi.org/v2/top-headlines?category=technology&apiKey={api_key}"
    response = requests.get(url)
    articles = response.json().get("articles", [])[:3]
    
    full_articles = []
    for article in articles:
        article_url = article.get("url")
        if article_url:
            try:
                news_article = Article(article_url)
                news_article.download()
                news_article.parse()
                full_content = news_article.text
                full_articles.append({
                    "title": news_article.title,
                    "content": full_content,
                    "urlToImage": article.get("urlToImage")
                })
            except Exception as e:
                print(f"Failed to fetch article from {article_url}: {e}")
    
    return full_articles

# Summarize Article
def summarize_article(article_text):
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    summary = summarizer(article_text, max_length=120, min_length=35, do_sample=False)
    print(summary)
    return summary[0]['summary_text']

# Download Main Image
def download_main_image(image_url, filename="article_image.jpg"):
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        with open(filename, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        return filename
    else:
        print(f"Failed to download image: {response.status_code}")
        return None

# Generate Voiceover
def generate_voiceover(text, filename="voiceover.mp3"):
    url = "https://api.elevenlabs.io/v1/text-to-speech/TX3LPaxmHKxFdv7VOQHJ"
    headers = {
        "xi-api-key": elevenlabs_api_key,
        "Content-Type": "application/json"
    }
    data = {
        "text": text
    }
    response = requests.post(url, json=data, headers=headers)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        print(f"Error: {response.status_code}, {response.text}")

def get_audio_length(filepath):
    """Return length in seconds of an audio file."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", filepath]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    return 0.0

def create_srt_split_into_quarters(subtitles, offsets, srt_filename="subtitles.srt"):
    """
    Generate an SRT file by splitting each subtitle into four parts.

    :param subtitles: List of subtitle texts.
    :param offsets: List of tuples containing (start_time, end_time) in seconds.
    :param srt_filename: Output SRT file name.
    """
    with open(srt_filename, "w", encoding="utf-8") as srt_file:
        subtitle_counter = 1  # Initialize subtitle numbering
        for subtitle, (start, end) in zip(subtitles, offsets):
            duration = end - start
            quarter_duration = duration / 4  # Duration for each quarter

            # Split the subtitle into four parts based on words
            words = subtitle.split()
            total_words = len(words)
            words_per_quarter = max(1, total_words // 4)
            quarters = [
                ' '.join(words[i:i + words_per_quarter])
                for i in range(0, total_words, words_per_quarter)
            ]

            # Handle any remaining words in the last quarter
            if len(quarters) > 4:
                quarters[3] += ' ' + ' '.join(quarters[4:])
                quarters = quarters[:4]

            # Assign each quarter part to a timestamp
            for q, part in enumerate(quarters):
                part_start = start + q * quarter_duration
                part_end = part_start + quarter_duration

                # Convert seconds to SRT timestamp format
                def sec_to_timestamp(sec):
                    td = timedelta(seconds=sec)
                    total_seconds = int(td.total_seconds())
                    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

                start_ts = sec_to_timestamp(part_start)
                end_ts = sec_to_timestamp(part_end)

                # Write the SRT entry
                srt_file.write(f"{subtitle_counter}\n")
                srt_file.write(f"{start_ts} --> {end_ts}\n")
                srt_file.write(f"{part}\n\n")
                subtitle_counter += 1

def create_video_with_ffmpeg(voiceover_files, srt_file, background_video, image_files, output="final_reel.mp4"):
    durations = [get_audio_length(v) for v in voiceover_files]

    offsets = []
    current_start = 0.0
    for d in durations:
        offsets.append((current_start, current_start + d))
        current_start += d

    # Total video length based on combined voiceovers
    total_voice_length = offsets[-1][1] if offsets else 0

    # Base ffmpeg command
    ffmpeg_command = [
        "ffmpeg",
        # Random start time for background
        "-ss", str(random.randint(0, 30)),
        "-i", background_video
    ]

    # Add all voiceovers
    for v in voiceover_files:
        ffmpeg_command.extend(["-i", v])

    # Add all images
    for img in image_files:
        ffmpeg_command.extend(["-i", img])

    # Build audio concat filter
    concat_parts = []
    for i in range(len(voiceover_files)):
        concat_parts.append(f"[{i+1}:a]")

    n = len(voiceover_files)
    audio_concat = ''.join(concat_parts) + f"concat=n={n}:v=0:a=1[audio_out];"

    # Build video filter to scale and crop background, then overlay images
    video_filter = (
        "[0:v]"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2"
        "[bg];"
    )

    overlay_chains = []
    last_label = "bg"
    for i, _ in enumerate(image_files):
        img_label = f"img{i}"
        ov_label = f"ov{i}"
        image_idx = 1 + n + i  # shift index for images

        # Scale the overlay image to take up more of the screen (e.g., 1000 width)
        video_filter += f"[{image_idx}:v]scale=1000:-1[{img_label}];"

        start_t, end_t = offsets[i] if i < len(offsets) else (0, 0)
        overlay_chains.append(
            f"[{last_label}][{img_label}]overlay=(W-w)/2:(H-h)/4:enable='between(t,{start_t},{end_t})'[{ov_label}];"
        )
        last_label = ov_label

    video_filter += "".join(overlay_chains)
    final_label = last_label if image_files else "bg"

    # Combine all filter parts
    filter_complex = audio_concat + video_filter

    # Add subtitles using the subtitles filter
    # Ensure the SRT file path is correct and escape any special characters
    # It's recommended to provide the absolute path to the SRT file
    srt_path = os.path.abspath(srt_file).replace('\\', '/')
    filter_complex += f"[{final_label}]subtitles='{srt_path}':force_style='FontName=Arial,FontSize=16,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Shadow=2,MarginV=40'[v];"

    ffmpeg_command.extend([
        "-filter_complex", filter_complex,
        # Use the video with subtitles
        "-map", "[v]",
        "-map", "[audio_out]",
        # Set duration to the end of the last voiceover
        "-t", str(total_voice_length),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        output
    ])

    try:
        subprocess.run(ffmpeg_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during FFmpeg execution: {e}")

if __name__ == "__main__":
    tech_articles = fetch_tech_news(api_key)

    voiceover_files = []
    image_files = []
    subtitles = []

    for idx, article in enumerate(tech_articles):
        title = article['title']
        content = article['content'] or article['description']
        image_url = article.get('urlToImage')
        
        summary = summarize_article(content)

        # Generate voiceover
        voiceover_file = f"voiceover_{idx}.mp3"
        generate_voiceover(summary, voiceover_file)
        voiceover_files.append(voiceover_file)

        # Collect subtitle text
        subtitles.append(summary)

        # Download article image
        if image_url:
            image_file = download_main_image(image_url, filename=f"article_image_{idx}.jpg")
            if image_file:
                image_files.append(image_file)

    # Generate "Follow for more" voiceover and subtitle
    follow_voice_file = "follow_for_more.mp3"
    follow_text = "Follow for more tech news!"
    if not os.path.exists(follow_voice_file):
        generate_voiceover(follow_text, follow_voice_file)
    voiceover_files.append(follow_voice_file)
    subtitles.append(follow_text)

    # Create SRT file
    # Calculate offsets based on voiceover durations
    durations = [get_audio_length(v) for v in voiceover_files]
    offsets = []
    current_start = 0.0
    for d in durations:
        offsets.append((current_start, current_start + d))
        current_start += d

    # Generate the SRT file
    srt_filename = "subtitles.srt"
    create_srt_split_into_quarters(subtitles, offsets, srt_filename=srt_filename)

    # Create video with subtitles
    background_video = "stock_video.mp4"  # Replace with your stock video file
    create_video_with_ffmpeg(voiceover_files, srt_filename, background_video, image_files, output="final_reel.mp4")

    print("Tech news reel with subtitles created!")
