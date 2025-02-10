import os
import hashlib
import subprocess
import pandas as pd
import librosa
from tqdm import tqdm
import torch
from demucs import pretrained
from demucs.apply import apply_model
import torchaudio
import webrtcvad
import numpy as np
from faster_whisper import WhisperModel

class VideoCaptioner:
    def __init__(self, video_path, model_size="small", compute_type="int8"):
        self.video_path = video_path
        self.model_size = model_size
        self.compute_type = compute_type
        self.audio_path = "temp_audio.wav"
        self.vocal_path = "vocals.wav"
        self.vocal_csv = "vocal_timestamps.csv"
        self.output_srt = ""
        self.output_video = ""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load Whisper model (using fast-whisper)
        self.whisper_model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

        # Load the Demucs model (htdemucs) and move it to the correct device.
        self.demucs_model = pretrained.get_model("htdemucs")
        self.demucs_model.to(self.device)

    def extract_audio(self):
        """Extracts audio from the video using FFmpeg and forces stereo output."""
        try:
            command = [
                "ffmpeg", "-i", self.video_path, "-vn",
                "-acodec", "pcm_s16le", "-ar", "44100",  # Higher sample rate
                "-ac", "2",  # Force stereo
                self.audio_path, "-y"
            ]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting audio: {e}")
            raise

    def separate_audio(self):
        """Separates vocals from the extracted audio using Demucs."""
        try:
            # Load audio using torchaudio
            audio, sr = torchaudio.load(self.audio_path)
            print(f"Loaded audio shape: {audio.shape}")  # (channels, samples)

            # Add batch dimension: (batch, channels, samples)
            audio = audio.unsqueeze(0)
            print(f"Audio shape after unsqueeze: {audio.shape}")  # (1, channels, samples)

            # Apply Demucs model
            wavs = apply_model(self.demucs_model, audio, device=self.device)
            print(f"Separated audio shape: {wavs.shape}")  # (batch=1, sources=4, channels=2, samples)

            # Extract vocals (last source) and remove batch dimension
            vocals = wavs[0, -1]  # Shape: (channels, samples)
            print(f"Vocals shape after extraction: {vocals.shape}")

            # Save vocals
            torchaudio.save(self.vocal_path, vocals, sr)
            print(f"Vocals saved to {self.vocal_path}")

        except Exception as e:
            print(f"Error separating audio: {e}")
            raise

    def detect_vocal_segments(self, aggressiveness=3, frame_duration=30, min_duration=0.5):
        """Detects segments with vocals using webrtcvad."""
        try:
            # Load audio using librosa
            y, sr = librosa.load(self.vocal_path, sr=16000)
            vad = webrtcvad.Vad(aggressiveness)

            # Convert audio to 16-bit PCM format
            audio_int16 = np.int16(y * 32768)

            # Process audio in frames
            frame_size = int(sr * frame_duration / 1000)
            frames = [audio_int16[i:i + frame_size] for i in range(0, len(audio_int16), frame_size)]
            timestamps = []
            start = None

            for i, frame in enumerate(frames):
                if len(frame) < frame_size:
                    continue
                is_speech = vad.is_speech(frame.tobytes(), sr)
                time = i * frame_duration / 1000

                if is_speech and start is None:
                    start = time
                elif not is_speech and start is not None:
                    end = time
                    if end - start >= min_duration:
                        timestamps.append((start, end))
                    start = None

            df = pd.DataFrame(timestamps, columns=["Start Time (s)", "End Time (s)"])
            df.to_csv(self.vocal_csv, index=False)
        except Exception as e:
            print(f"Error detecting vocal segments: {e}")
            raise

    def transcribe_audio(self, segment_path):
        """Transcribes the given audio segment using fast-whisper."""
        try:
            segments, _ = self.whisper_model.transcribe(segment_path)
            return " ".join([seg.text for seg in segments])
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            raise

    def generate_srt(self):
        """Generates an SRT file with timestamps."""
        try:
            df = pd.read_csv(self.vocal_csv)
            checksum = hashlib.md5(open(self.audio_path, "rb").read()).hexdigest()[:8]
            self.output_srt = f"captions_{checksum}.srt"

            with open(self.output_srt, "w", encoding="utf-8") as srt_file:
                for idx, row in tqdm(df.iterrows(), total=len(df), desc="Generating SRT"):
                    start_time, end_time = row["Start Time (s)"], row["End Time (s)"]

                    # Extract and transcribe only the vocal segment using ffmpeg.
                    segment_audio = f"segment_{idx}.wav"
                    command = [
                        "ffmpeg", "-i", self.vocal_path,
                        "-ss", str(start_time), "-to", str(end_time),
                        "-c", "copy", segment_audio, "-y"
                    ]
                    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                    transcript = self.transcribe_audio(segment_audio)
                    os.remove(segment_audio)

                    # Format the SRT file correctly
                    srt_file.write(f"{idx + 1}\n")
                    srt_file.write(f"{self.format_time(start_time)} --> {self.format_time(end_time)}\n")
                    srt_file.write(f"{transcript}\n\n")
        except Exception as e:
            print(f"Error generating SRT: {e}")
            raise

    def format_time(self, time_in_seconds):
        """Formats time in seconds to SRT format (HH:MM:SS,mmm)."""
        hours = int(time_in_seconds // 3600)
        minutes = int((time_in_seconds % 3600) // 60)
        seconds = int(time_in_seconds % 60)
        milliseconds = int((time_in_seconds - int(time_in_seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def add_subtitles(self):
        """Embeds subtitles into the video using FFmpeg."""
        try:
            self.output_video = f"subtitled_{os.path.basename(self.video_path)}"
            command = [
                "ffmpeg", "-i", self.video_path, "-vf",
                f"subtitles={self.output_srt}", "-c:a", "copy",
                self.output_video, "-y"
            ]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error adding subtitles: {e}")
            raise

    def process(self):
        """Runs the entire process: audio extraction, vocal separation, segment detection, and captioning."""
        try:
            self.extract_audio()
            self.separate_audio()
            self.detect_vocal_segments()
            self.generate_srt()
            # Uncomment the following line if you want to embed the subtitles into the video:
            # self.add_subtitles()
            print(f"[✔] Captions saved as {self.output_srt} and added to {self.output_video}.")
        except Exception as e:
            print(f"Error processing video: {e}")
        finally:
            # Clean up temporary files
            if os.path.exists(self.audio_path):
                os.remove(self.audio_path)
            if os.path.exists(self.vocal_path):
                os.remove(self.vocal_path)
            if os.path.exists(self.vocal_csv):
                os.remove(self.vocal_csv)

# Example Usage
if __name__ == "__main__":
    video1 = VideoCaptioner("sample2.mp4")
    video1.process()