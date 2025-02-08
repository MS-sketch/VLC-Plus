import os
import subprocess
from faster_whisper import WhisperModel
from tqdm import tqdm


def extract_audio(video_path, audio_path="temp_audio.wav"):
    """Extracts audio from video using FFmpeg."""
    command = [
        "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1", audio_path, "-y"
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return audio_path


def split_audio(audio_path, segment_length=7, output_folder="audio_segments"):
    """Splits audio into 7-second segments."""
    os.makedirs(output_folder, exist_ok=True)
    segment_pattern = os.path.join(output_folder, "segment_%03d.wav")

    command = [
        "ffmpeg", "-i", audio_path, "-f", "segment", "-segment_time", str(segment_length),
        "-c", "copy", segment_pattern, "-y"
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return sorted(os.listdir(output_folder))


def transcribe_audio_faster_whisper(segment_path, model):
    """Transcribes audio using Faster Whisper."""
    segments, _ = model.transcribe(segment_path)
    return " ".join([segment.text for segment in segments])


def generate_srt(audio_segments, model, output_srt="captions.srt", segment_length=7):
    """Generates an SRT file from transcriptions with proper timestamps."""
    with open(output_srt, "w", encoding="utf-8") as srt_file:
        for idx, segment in tqdm(enumerate(audio_segments), total=len(audio_segments), desc="Processing"):
            start_time = idx * segment_length
            end_time = start_time + segment_length

            # Convert seconds to SRT timestamp format (HH:MM:SS,ms)
            start_srt = f"{start_time // 3600:02}:{(start_time % 3600) // 60:02}:{start_time % 60:02},000"
            end_srt = f"{end_time // 3600:02}:{(end_time % 3600) // 60:02}:{end_time % 60:02},000"

            # Transcribe each segment
            segment_path = os.path.join("audio_segments", segment)
            transcript = transcribe_audio_faster_whisper(segment_path, model)

            # Write to SRT file
            srt_file.write(f"{idx + 1}\n{start_srt} --> {end_srt}\n{transcript}\n\n")

    return output_srt


def video_to_captions(video_path, model_size="large", compute_type="int8"):
    """Main function to extract audio, split, transcribe, and generate captions."""
    print("[*] Extracting audio from video...")
    audio_path = extract_audio(video_path)

    print("[*] Splitting audio into 7-second segments...")
    audio_segments = split_audio(audio_path)

    print("[*] Loading Faster Whisper model...")
    model = WhisperModel(model_size, compute_type=compute_type)

    print("[*] Generating captions with precise timestamps...")
    generate_srt(audio_segments, model)

    os.remove(audio_path)
    print("[✔] Captions saved to captions.srt")


# Example usage
video_to_captions("sampleVid.mp4", model_size="large", compute_type="int8")
