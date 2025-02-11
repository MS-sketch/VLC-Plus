import os
import hashlib
import subprocess
import pandas as pd
import librosa
import torchaudio
import webrtcvad
import numpy as np
from tqdm import tqdm
import torch
from demucs import pretrained
from demucs.apply import apply_model
from faster_whisper import WhisperModel
from concurrent.futures import ThreadPoolExecutor, as_completed


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

        # Load models
        self.whisper_model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        self.demucs_model = pretrained.get_model("htdemucs").to(self.device)

    def extract_audio(self):
        """Extract audio with dynamic normalization and multithreading"""
        try:
            subprocess.run([
                "ffmpeg", "-i", self.video_path, "-vn",
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                self.audio_path, "-y"
            ], check=True)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Audio extraction failed: {e}")

    def separate_audio(self):
        """Optimized vocal separation with proper tensor handling"""
        try:
            # Load and preprocess audio
            waveform, sr = torchaudio.load(self.audio_path)
            waveform = waveform[:2].to(self.device)  # Force stereo and move to device

            # Process in one pass with proper batching
            with torch.no_grad():
                sources = apply_model(
                    self.demucs_model,
                    waveform.unsqueeze(0),
                    overlap=0.25,
                    device=self.device
                )

            # Extract vocals and save
            vocals = sources[0, -1].cpu()
            torchaudio.save(self.vocal_path, vocals, sr)
        except Exception as e:
            raise RuntimeError(f"Vocal separation failed: {e}")


    def detect_vocal_segments(self, aggressiveness=1, min_duration=0.3, batch_size=1000):
        """Optimized multi-threaded VAD processing with non-overlapping timestamps."""
        try:
            # Load & convert audio
            y, sr = librosa.load(self.vocal_path, sr=16000, mono=True)
            audio_int16 = (y * 32767).astype(np.int16)

            # WebRTC VAD requires 10ms frames (160 samples @ 16kHz)
            frame_size = 160
            vad = webrtcvad.Vad(aggressiveness)
            total_frames = (len(audio_int16) - frame_size) // frame_size

            # Generate timestamps only once
            timestamps = np.arange(total_frames) * (frame_size / sr)

            def process_batch(start_idx):
                """Processes a batch of frames ensuring no overlap."""
                end_idx = min(start_idx + batch_size, total_frames)
                batch_frames = np.array([
                    audio_int16[i * frame_size:(i + 1) * frame_size].tobytes()
                    for i in range(start_idx, end_idx)
                ], dtype=object)

                return [
                    (start_idx + i, vad.is_speech(frame, sr)) 
                    for i, frame in enumerate(batch_frames)
                ]

            # Process batches in parallel
            batch_indices = range(0, total_frames, batch_size)
            results = []
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                futures = list(tqdm(executor.map(process_batch, batch_indices), total=len(batch_indices), desc="VAD Processing"))
            
            # Flatten results
            results = np.array([item for batch in futures for item in batch])
            speech_frames = results[results[:, 1] == True][:, 0].astype(int)

            if len(speech_frames) == 0:
                pd.DataFrame(columns=["Start", "End"]).to_csv(self.vocal_csv, index=False)
                return
            
            # Find contiguous speech segments
            diff = np.diff(speech_frames)
            segment_breaks = np.where(diff > 1)[0] + 1
            segment_starts = np.insert(speech_frames[segment_breaks], 0, speech_frames[0])
            segment_ends = np.append(speech_frames[segment_breaks - 1], speech_frames[-1])

            # Convert frame indices to timestamps
            final_segments = [(timestamps[start], timestamps[end] + frame_size / sr) 
                              for start, end in zip(segment_starts, segment_ends) 
                              if timestamps[end] - timestamps[start] >= min_duration]

            # Save timestamps without overlaps
            pd.DataFrame(final_segments, columns=["Start", "End"]).to_csv(self.vocal_csv, index=False)

        except Exception as e:
            raise RuntimeError(f"VAD processing failed: {e}")


    def transcribe_segment(self, idx, start, end):
        """Optimized segment transcription with error handling"""
        try:
            output = f"segment_{idx}.wav"
            subprocess.run([
                "ffmpeg", "-i", self.vocal_path,
                "-ss", str(start), "-to", str(end),
                "-c", "copy", output, "-y"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            segments, _ = self.whisper_model.transcribe(
                output,
                beam_size=5,
                temperature=(0.0, 0.2, 0.4, 0.6),
                vad_filter=True
            )
            transcript = " ".join(seg.text for seg in segments)
            os.remove(output)
            return (idx, start, end, transcript)
        except Exception as e:
            print(f"Segment {idx} error: {str(e)}")
            return (idx, start, end, "")

    def generate_srt(self):
        """Parallel SRT generation with ordered results"""
        try:
            segments = pd.read_csv(self.vocal_csv)
            self.output_srt = f"captions_{hashlib.md5(open(self.audio_path, 'rb').read()[:8]).hexdigest()}.srt"

            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                futures = [executor.submit(self.transcribe_segment, i, row.Start, row.End)
                           for i, row in segments.iterrows()]

                results = []
                for future in tqdm(as_completed(futures), total=len(futures), desc="Transcribing"):
                    results.append(future.result())

            # Sort by original index and write to file
            results.sort(key=lambda x: x[0])
            with open(self.output_srt, "w", encoding="utf-8") as f:
                for idx, start, end, text in results:
                    f.write(f"{idx + 1}\n"
                            f"{self._format_ts(start)} --> {self._format_ts(end)}\n"
                            f"{text}\n\n")
        except Exception as e:
            raise RuntimeError(f"SRT generation failed: {e}")

    def _format_ts(self, seconds):
        """Optimized timestamp formatting"""
        ms = seconds % 1
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int(ms * 1000):03}"

    def process(self):
        """Main processing pipeline with cleanup"""
        try:
            self.extract_audio()
            self.separate_audio()
            self.detect_vocal_segments()
            self.generate_srt()
            print(f"Success! Captions saved to {self.output_srt}")
        except Exception as e:
            print(f"Processing failed: {str(e)}")
        finally:
            for f in [self.audio_path, self.vocal_path, self.vocal_csv]:
                if os.path.exists(f):
                    os.remove(f)


if __name__ == "__main__":
    VideoCaptioner("sample2.mp4").process()