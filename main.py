import requests
from transformers import pipeline
import subprocess
import os
import random
import json
from newspaper import Article
from dotenv import load_dotenv
import pysrt
import whisper
import unicodedata


# Fetch Tech News with Full Content
def fetch_tech_news(api_key):
    url = f"https://newsapi.org/v2/everything?q=(programming OR coding OR development) AND (features OR updates OR news) AND (languages OR frameworks) NOT (hiring OR jobs OR careers OR vacancies OR Gold OR economics)&from=2025-01-01&to=2025-01-14&language=en&sortBy=publishedAt&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching news: {response.status_code}")
        return []
        
    articles = response.json().get("articles", [])
    
    # Sort articles by date, newest first
    valid_articles = []
    for article in articles:
        # Skip removed or empty articles
        if (article.get("title") == "[Removed]" or 
            article.get("content") == "[Removed]" or 
            not article.get("url") or
            not article.get("publishedAt")):
            continue
            
        valid_articles.append(article)
    
    # Sort by publishedAt date descending
    
    full_articles = []
    for article in valid_articles:
        try:
            news_article = Article(article.get("url"))
            news_article.download()
            news_article.parse()
            
            # Validate article has meaningful content
            if not news_article.text or len(news_article.text) < 100 or article.get("urlToImage") is None:
                continue
                
            full_articles.append({
                "title": news_article.title,
                "content": news_article.text,
                "urlToImage": article.get("urlToImage"),
                "publishedAt": article.get("publishedAt")
            })
            
            # Break once we have 3 valid articles
            if len(full_articles) >= 3:
                break
                
        except Exception as e:
            print(f"Failed to fetch article from {article.get('url')}: {e}")
            continue
    
    return full_articles

# Summarize Article
def summarize_article(article_text, summarizer):
    # Limit the input text to prevent excessive memory usage
    max_input_length = 1024  # Adjust based on model's maximum token limit
    if len(article_text) > max_input_length:
        article_text = article_text[:max_input_length]
    
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
        "text": text,
        "model_id": "eleven_flash_v2_5",
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

def transcribe_with_whisper(audio_file, offset=0.0):

    # Transcribe audio file using whisper with shorter, more precise segments
    model = whisper.load_model("base")
    
    # Transcribe with word-level timestamps
    result = model.transcribe(audio_file, word_timestamps=True)
    
    # Convert to srt format with shorter segments
    subs = pysrt.SubRipFile()
    
    current_text = []
    current_start = None
    word_count = 0
    
    for segment in result["segments"]:
        for word_info in segment["words"]:
            word = word_info["word"].strip()
            if current_start is None:
                current_start = word_info["start"]
            
            current_text.append(word)
            word_count += 1
            
            # Create new subtitle every 3-4 words or at punctuation
            if (word_count >= 4 or 
                any(punct in word for punct in ".,!?") or 
                word_info == segment["words"][-1]):
                
                sub = pysrt.SubRipItem(
                    index=len(subs) + 1,
                    start=pysrt.SubRipTime(seconds=current_start + offset),
                    end=pysrt.SubRipTime(seconds=word_info["end"] + offset),
                    text=" ".join(current_text)
                )
                subs.append(sub)
                
                # Reset for next segment
                current_text = []
                current_start = None
                word_count = 0
    
    return subs

# Replace existing generate_subtitles_with_subsai function
def generate_subtitles_with_subsai(audio_file, offset=0.0):
    return transcribe_with_whisper(audio_file, offset)

# Replace existing generate_single_srt function  
def generate_single_srt(audio_file, output_path, offset=0.0):
    subs = transcribe_with_whisper(audio_file, offset)
    subs.save(output_path)
    return subs

def escape_text(text):

    # Escapes special characters in the text for FFmpeg's drawtext filter.
    # Converts curly apostrophes to straight ones and escapes single quotes, colons, and backslashes.

    # Normalize text to NFKC to standardize characters
    text = unicodedata.normalize('NFKC', text)
    # Escape backslashes first
    text = text.replace("\\", "\\\\")
    # Escape single quotes
    text = text.replace("'", "\\'")
    # Escape colons
    text = text.replace(":", " - ")
    return text

def create_video_with_ffmpeg(voiceover_files, srt_file, background_video, image_files, titles, output="final_reel.mp4"):
    durations = [get_audio_length(v) for v in voiceover_files]

    offsets = []
    current_start = 0.0
    for d in durations:
        offsets.append((current_start, current_start + d))
        current_start += d

    # Total video length based on combined voiceovers
    total_voice_length = offsets[-1][1] if offsets else 0

    total_bg_length = get_audio_length(background_video)
    
    # Validate background video length and calculate random start
    if total_bg_length <= total_voice_length:
        randomstart = 0  # If background is too short, start from beginning
    else:
        max_start = int(total_bg_length - total_voice_length)
        randomstart = random.randint(0, max_start)

    # Rest of the function remains the same
    ffmpeg_command = [
        "ffmpeg",
        "-ss", str(randomstart),
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

    # Build video filter to scale and crop background
    video_filter = (
        "[0:v]"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2"
        "[bg];"
    )

    # Add title overlays
    last_label = "bg"
    for i, title in enumerate(titles):
        if i >= len(offsets):
            continue
        
        # Skip empty titles
        if not title.strip():
            continue

        start_t, end_t = offsets[i]
        title_label = f"title{i}"

        # Escape special characters in title
        escaped_title = escape_text(title)
        print(f"Escaped Title {i}: {escaped_title}")  # Debugging line

        # Create title overlay using drawtext filter
        # video_filter += (
        #     f"[{last_label}]drawtext="
        #     f"text='{escaped_title}':"
        #     "fontfile=/System/Library/Fonts/Helvetica.ttc:"
        #     "fontsize=48:"
        #     "fontcolor=white:"
        #     "x=(w-text_w)/2:"
        #     "y=80:"  # Position from top
        #     "box=1:"
        #     "boxcolor=black@0.5:"
        #     "boxborderw=10:"
        #     f"enable='between(t,{start_t},{end_t})':"
        #     f"[{title_label}];"
        # )
        # last_label = title_label

    # Continue with image overlays
    overlay_chains = []
    for i, _ in enumerate(image_files):
        img_label = f"img{i}"
        ov_label = f"ov{i}"
        image_idx = 1 + n + i  # shift index for images

        # Scale the overlay image to take up more of the screen (e.g., 900 width)
        video_filter += f"[{image_idx}:v]scale=900:-1[{img_label}];"

        if i < len(offsets):
            start_t, end_t = offsets[i]
        else:
            start_t, end_t = (0, 0)

        overlay_chains.append(
            f"[{last_label}][{img_label}]overlay=(W-w)/2:(H-h)/4:enable='between(t,{start_t},{end_t})'[{ov_label}];"
        )
        last_label = ov_label

    video_filter += "".join(overlay_chains)
    final_label = last_label if image_files else "bg"

    # Combine all filter parts
    filter_complex = audio_concat + video_filter
    print(filter_complex)

    # Generate subtitles using SubsAI for all voiceovers
    all_subs = []
    current_offset = 0.0
    
    for voice_file in voiceover_files:
        subs = generate_subtitles_with_subsai(voice_file, current_offset)
        all_subs.extend(subs)
        current_offset += get_audio_length(voice_file)
    
    # Save combined subtitles
    srt_path = os.path.abspath(srt_file)
    combined_subs = pysrt.SubRipFile(all_subs)
    combined_subs.save(srt_path, encoding='utf-8')

    # Add subtitles using the subtitles filter
    # Ensure the SRT file path is correct and escape any special characters
    # It's recommended to provide the absolute path to the SRT file
    srt_path = os.path.abspath(srt_file).replace('\\', '/')
    filter_complex += (
        f"[{final_label}]subtitles='{srt_path}':"
        "force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF&,"
        "OutlineColour=&H000000&,Outline=2,Shadow=1,MarginV=40,MarginL=20,MarginR=20'"
        "[v];"
    )

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

def combine_srt_files(srt_paths, final_srt_path):
    """Combine multiple SRT files into one"""
    combined_subs = pysrt.SubRipFile()
    for srt_path in srt_paths:
        subs = pysrt.open(srt_path)
        combined_subs.extend(subs)
    combined_subs.save(final_srt_path, encoding='utf-8')

if __name__ == "__main__":
    
    # Load environment variables from .env file
    load_dotenv()

    # Fetch API keys from environment variables
    newsapi_api_key = os.getenv("NEWSAPI_KEY")
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

    # Initialize the summarizer once
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

    tech_articles = fetch_tech_news(newsapi_api_key)

    voiceover_files = []
    image_files = []
    subtitles = []
    titles = []

    for idx, article in enumerate(tech_articles):
        title = article['title']
        titles.append(title)
        content = article['content'] or article['description']
        image_url = article.get('urlToImage')
        
        summary = summarize_article(content, summarizer)

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

    # Add empty title for "Follow for more" segment
    titles.append("")

    # Create SRT file
    srt_filename = "subtitles.srt"
    
    # Generate individual SRTs
    srt_paths = []
    current_offset = 0.0
    
    for idx, voiceover in enumerate(voiceover_files):
        srt_path = f"subtitle_{idx}.srt"
        generate_single_srt(voiceover, srt_path, current_offset)
        srt_paths.append(srt_path)
        current_offset += get_audio_length(voiceover)
    
    # Combine all SRTs
    combine_srt_files(srt_paths, "final_subtitles.srt")
    
    # Create video with combined subtitles
    create_video_with_ffmpeg(
        voiceover_files, 
        "final_subtitles.srt", 
        "stock_video.mp4", 
        image_files,
        titles
    )

    print("Tech news reel with subtitles created!")
