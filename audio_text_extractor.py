import os
import argparse
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import whisper

try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    print("Warning: moviepy not installed. Install with: pip install moviepy")
    MOVIEPY_AVAILABLE = False

class AudioExtractor:
    @staticmethod
    def extract_audio_from_video(video_path: str) -> Tuple[str, bool]:
        """
        Extract audio from video file and save as temporary WAV file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Tuple of (path_to_audio_file, is_temporary)
        """
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy is required for video processing. Install with: pip install moviepy")
            
        # Create a temporary file for the audio
        temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_audio.close()
        
        try:
            # Extract audio from video
            video = VideoFileClip(video_path)
            audio = video.audio
            # Remove verbose parameter as it's not supported in some versions
            audio.write_audiofile(temp_audio.name, codec='pcm_s16le')
            audio.close()
            video.close()
            return temp_audio.name, True
        except Exception as e:
            # Clean up the temporary file if there was an error
            if os.path.exists(temp_audio.name):
                os.unlink(temp_audio.name)
            raise Exception(f"Error extracting audio from video: {str(e)}")


class ArabicAudioTranscriber:
    def __init__(self, model_name: str = "base", models_dir: str = None):
        """
        Initialize the Arabic audio transcriber with a Whisper model.
        
        Args:
            model_name: The Whisper model to use (tiny, base, small, medium, large, large-v2, large-v3)
            models_dir: Directory containing the Whisper models. If None, uses default location.
        """
        self.model_name = model_name
        self.models_dir = "./models"
        self.model = None
        
    def _get_model_path(self):
        """Get the full path to the model file."""
        model_file = f"{self.model_name}.pt"
        model_path = os.path.join(self.models_dir, model_file)
        
        # Check if model exists in the specified directory
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model '{self.model_name}' not found in {self.models_dir}. "
                f"Please make sure the model file '{model_file}' exists in the models directory."
            )
        return model_path

    def load_model(self):
        """Load the Whisper model for speech recognition with CPU fallback."""
        import torch
        
        # Get the full path to the model file
        model_path = self._get_model_path()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"Loading Whisper {self.model_name} model from {model_path} on {device.upper()}...")
        
        try:
            # Try loading with GPU first
            self.model = whisper.load_model(model_path, device=device)
            print(f"Model loaded successfully on {device.upper()}")
        except RuntimeError as e:
            if "CUDA out of memory" in str(e) and device == "cuda":
                print("CUDA out of memory, falling back to CPU...")
                self.model = whisper.load_model(model_path, device="cpu")
                print("Model loaded successfully on CPU")
            else:
                raise e
    
    def transcribe_media(
        self, 
        media_path: str, 
        output_path: Optional[str] = None,
        language: str = "ar",
        keep_audio: bool = False
    ) -> str:
        """
        Transcribe Arabic audio/video to text.
        
        Args:
            media_path: Path to the audio or video file
            output_path: Optional path to save the transcription
            language: Language code (default: 'ar' for Arabic)
            keep_audio: If True, keep the extracted audio file (for video inputs)
            
        Returns:
            str: The transcribed text
        """
        if not os.path.exists(media_path):
            raise FileNotFound(f"Media file not found: {media_path}")
            
        # Handle video files
        is_video = media_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'))
        audio_path = media_path
        temp_audio = None
        
        if is_video:
            print(f"Extracting audio from video: {media_path}")
            audio_path, is_temp = AudioExtractor.extract_audio_from_video(media_path)
            if is_temp and not keep_audio:
                temp_audio = audio_path
            
        if self.model is None:
            self.load_model()
        
        print(f"Transcribing {'video' if is_video else 'audio'}: {media_path}")
        
        try:
            # Transcribe the audio with CPU-optimized settings
            result = self.model.transcribe(
                audio_path,
                language=language,
                fp16=False,  # Disable mixed precision for CPU
                verbose=True,  # Show progress
                # Remove batch_size as it's not supported in some Whisper versions
                condition_on_previous_text=False,  # Reduce memory usage
                temperature=0.0,  # More deterministic output
                best_of=1,  # Reduce memory usage
                beam_size=1  # Reduce memory usage
            )
            text = result["text"].strip()
        finally:
            # Clean up temporary audio file if it was created from a video
            if temp_audio and os.path.exists(temp_audio):
                os.unlink(temp_audio)
        
        # Save the transcription if output path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Transcription saved to: {output_path}")
        
        return text

def main():
    parser = argparse.ArgumentParser(description='Transcribe Arabic audio/video to text using Whisper')
    parser.add_argument('media_path', type=str, help='Path to the audio or video file to transcribe')
    parser.add_argument('--output', '-o', type=str, help='Output file path for the transcription')
    parser.add_argument('--model', '-m', type=str, default='base',
                      help='Whisper model to use (tiny, base, small, medium, large, large-v2, large-v3)')
    parser.add_argument('--keep-audio', action='store_true',
                      help='Keep the extracted audio file (for video inputs)')
    parser.add_argument('--threads', type=int, default=0,
                      help='Number of CPU threads to use (0 = use all available)')
    
    args = parser.parse_args()
    
    try:
        # Set number of CPU threads if specified
        if args.threads > 0:
            import torch
            torch.set_num_threads(args.threads)
            print(f"Using {args.threads} CPU threads")
            
        transcriber = ArabicAudioTranscriber(model_name=args.model)
        transcription = transcriber.transcribe_media(
            media_path=args.media_path,
            output_path=args.output,
            language="ar",
            keep_audio=args.keep_audio
        )
        
        print("\nTranscription Result:")
        print("-" * 50)
        print(transcription)
        print("-" * 50)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()