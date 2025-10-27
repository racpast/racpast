import subprocess
import os
import math
import sys
import json
import shutil

# --- Configuration ---
MAX_FILE_SIZE_MB = 9.99
AUDIO_BITRATE_LADDER_K = [192, 128, 96, 64]
MIN_VIDEO_BITRATE_K = 50
BITRATE_SAFETY_MARGIN = 0.98

INPUT_FILENAME = "input_raw.mp4"
DEFAULT_OUTPUT_FILENAME = "output_720p_final.mp4"
TEMP_DIR = "ffmpeg_temp_work"
PASS_LOG_FILE = "ffmpeg2pass_log"

def run_command(command, description, critical=True, cwd=None):
    """Executes a shell command and logs its progress."""
    print(f"\n[INFO] Running: {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True, encoding='utf-8', cwd=cwd)
        print(f"[SUCCESS] {description} completed.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed to execute: {command}")
        print(f"        Stderr:\n{e.stderr}")
        if critical:
            sys.exit(1)
        return None
    except FileNotFoundError:
        print(f"[ERROR] Required program (e.g., ffmpeg, yt-dlp) not found. Ensure it is installed and in the system's PATH.")
        sys.exit(1)

def cleanup_temp_dir(temp_dir_path):
    """Removes the specified temporary directory if it exists."""
    if os.path.exists(temp_dir_path):
        shutil.rmtree(temp_dir_path)
        print(f"[INFO] Cleaned up temporary directory: {temp_dir_path}")

def auto_compress_video():
    """Main function to download and compress a video to a target file size."""
    print("----------------------------------------------------")
    print("      Automated H.264 Video Compression Script")
    print("----------------------------------------------------")
    
    video_url = input("Please enter the video URL: ")
    user_filename_input = input(f"Enter the final output filename (or press Enter for '{DEFAULT_OUTPUT_FILENAME}'): ")

    if not user_filename_input.strip():
        output_filename = DEFAULT_OUTPUT_FILENAME
    else:
        output_filename = user_filename_input.strip()
        if not output_filename.lower().endswith('.mp4'):
            output_filename += '.mp4'

    print(f"[INFO] Final filename will be: {output_filename}")

    script_dir = os.getcwd()
    temp_dir_path = os.path.join(script_dir, TEMP_DIR)

    if os.path.exists(temp_dir_path):
        cleanup_temp_dir(temp_dir_path)
    os.makedirs(temp_dir_path, exist_ok=True)
    
    temp_input_path_abs = os.path.join(temp_dir_path, INPUT_FILENAME)
    temp_output_path_abs = os.path.join(temp_dir_path, output_filename)
    final_output_path_abs = os.path.join(script_dir, output_filename) 

    metadata_json = run_command(f'yt-dlp --skip-download --print-json "{video_url}"', "Fetching video metadata", critical=True)
    
    try:
        metadata = json.loads(metadata_json)
        duration = metadata.get('duration') 
        if duration is None or duration <= 0:
            print(f"[ERROR] Could not find valid duration in video metadata.")
            cleanup_temp_dir(temp_dir_path)
            return
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to parse JSON data from yt-dlp.")
        cleanup_temp_dir(temp_dir_path)
        return

    duration = float(duration)
    print(f"\n[INFO] Video Duration: {duration:.2f} seconds")
    print(f"[INFO] Target File Size: {MAX_FILE_SIZE_MB} MB")
    
    download_cmd = f'yt-dlp -f "bv*+ba/b" --merge-output-format mp4 --output "{temp_input_path_abs}" "{video_url}"'
    run_command(download_cmd, f"Downloading video to {temp_dir_path}", critical=True)
    
    if not os.path.exists(temp_input_path_abs):
        print(f"[ERROR] Video file download failed: {temp_input_path_abs}")
        cleanup_temp_dir(temp_dir_path)
        return

    for target_audio_bitrate_k in AUDIO_BITRATE_LADDER_K:
        print(f"\n================================================================")
        print(f"  Attempting with Audio Bitrate: {target_audio_bitrate_k} kbps")
        print(f"================================================================")

        target_file_size_bits = MAX_FILE_SIZE_MB * 1024 * 1024 * 8
        target_audio_size_bits = target_audio_bitrate_k * 1000 * duration
        target_video_size_bits = target_file_size_bits - target_audio_size_bits
        
        if target_video_size_bits <= 0:
            print(f"[WARN] Target size too small for {target_audio_bitrate_k}k audio. Trying next audio level.")
            continue

        initial_target_bitrate_k = math.floor((target_video_size_bits / duration) / 1000)
        current_target_bitrate_k = initial_target_bitrate_k
        
        print(f"[INFO] Initial video bitrate calculated for this audio level: {current_target_bitrate_k} kbps")

        attempt = 0
        compression_successful = False
        while True:
            attempt += 1
            
            if current_target_bitrate_k < MIN_VIDEO_BITRATE_K:
                print(f"[WARN] Video bitrate ({current_target_bitrate_k}k) fell below minimum threshold ({MIN_VIDEO_BITRATE_K}k).")
                print(f"[INFO] Moving to next lower audio quality level...")
                break

            print(f"\n----------------------------------------------------------------")
            print(f"  Compression Attempt #{attempt} (Video: {current_target_bitrate_k}k, Audio: {target_audio_bitrate_k}k)")
            print(f"----------------------------------------------------------------")
            
            pass1_cmd = (
                f'ffmpeg -i "{temp_input_path_abs}" -y -loglevel error '
                f'-c:v libx264 -b:v {current_target_bitrate_k}k -preset veryslow -profile:v high -level 4.0 -pix_fmt yuv420p -tune film '
                f'-x264-params pass=1:deblock=-2,-2:bframes=8:b-adapt=2:ref=5:rc-lookahead=60:open-gop=0:passlogfile="{PASS_LOG_FILE}" '
                f'-vf scale=-2:720 '
                f'-an -f null -'
            )
            run_command(pass1_cmd, f"Pass 1: Video Analysis", critical=True, cwd=temp_dir_path)
            
            if os.path.exists(temp_output_path_abs):
                os.remove(temp_output_path_abs) 
                
            pass2_cmd = (
                f'ffmpeg -i "{temp_input_path_abs}" -y -loglevel error '
                f'-c:v libx264 -b:v {current_target_bitrate_k}k -preset veryslow -profile:v high -level 4.0 -pix_fmt yuv420p -tune film '
                f'-x264-params pass=2:deblock=-2,-2:bframes=8:b-adapt=2:ref=5:rc-lookahead=60:open-gop=0:passlogfile="{PASS_LOG_FILE}" '
                f'-vf scale=-2:720 '
                f'-c:a aac -b:a {target_audio_bitrate_k}k '
                f'"{temp_output_path_abs}"'
            )
            run_command(pass2_cmd, f"Pass 2: Final Encoding", critical=True, cwd=temp_dir_path)
            
            if os.path.exists(temp_output_path_abs):
                final_file_size_byte = os.path.getsize(temp_output_path_abs)
                final_file_size_mb = final_file_size_byte / (1024 * 1024)
                
                print(f"\n[RESULT] Actual file size: {final_file_size_mb:.3f} MB")
                
                if final_file_size_mb <= MAX_FILE_SIZE_MB:
                    print(f"[SUCCESS] File size ({final_file_size_mb:.3f} MB) is within the target of {MAX_FILE_SIZE_MB} MB.")
                    print(f"[INFO] Moving final file to: {final_output_path_abs}")
                    shutil.move(temp_output_path_abs, final_output_path_abs)
                    print(f"[INFO] Final output file: {output_filename}")
                    compression_successful = True
                    break
                else:
                    size_ratio = MAX_FILE_SIZE_MB / final_file_size_mb
                    new_bitrate = math.floor(current_target_bitrate_k * size_ratio * BITRATE_SAFETY_MARGIN)
                    print(f"[WARN] File size exceeds limit. Recalculating bitrate...")
                    print(f"[INFO] Old bitrate: {current_target_bitrate_k}k -> New bitrate: {new_bitrate}k")
                    current_target_bitrate_k = new_bitrate
            else:
                print(f"[ERROR] Output file not found after encoding. Process aborted.")
                break
        
        if compression_successful:
            break

    print("\n--- Finalizing ---")
    cleanup_temp_dir(temp_dir_path)
    if compression_successful:
        print("All tasks completed.")
    else:
        print("[ERROR] Could not meet file size target even with the lowest audio quality settings. Process finished.")


if __name__ == "__main__":
    auto_compress_video()
