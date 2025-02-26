import pysrt
import whisper
import json
import subprocess

def get_audio_length(filepath):

    # Return length in seconds of an audio file.
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