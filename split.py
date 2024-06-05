import sys
import os
import subprocess
from pathlib import Path
import chardet
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Supported audio file extensions
audio_extensions = ['.flac', '.mp3', '.ogg', '.wav', '.aac', '.m4a', '.wma']

@contextmanager
def change_directory(directory):
    """Context manager for changing the working directory."""
    original_directory = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(original_directory)

def is_audio_file(file_path):
    """Check if the file has an audio file extension."""
    return file_path.suffix.lower() in audio_extensions

def valid_filename(file_path):
    """Check if the filename's second and third characters are not digits."""
    name = file_path.stem
    return len(name) > 2 and not (name[1].isdigit() and name[2].isdigit())

def check_audio_format(file_path):
    """Check if the audio file is already at CD quality."""
    command = [
        'ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
        'stream=sample_rate,bit_rate', '-of', 'default=noprint_wrappers=1:nokey=1',
        str(file_path)
    ]
    output = subprocess.run(command, stdout=subprocess.PIPE, text=True)
    try:
        sample_rate, bit_rate = output.stdout.strip().split()
        return int(sample_rate) == 44100   # 16-bit 44100Hz stereo
    except ValueError:
        logging.warning(f"Unable to determine audio format for {file_path}. Assuming conversion is needed.")
        return False

def convert_to_cd_format(file_path):
    """Use ffmpeg to convert audio to standard CD format if necessary."""
    if not check_audio_format(file_path):
        temp_output_path = file_path.with_suffix('.tmp' + file_path.suffix)
        command = [
            'ffmpeg', '-i', str(file_path), '-ar', '44100', '-ac', '2', '-sample_fmt', 's16',
            str(temp_output_path)
        ]
        subprocess.run(command, check=True)
        if temp_output_path.exists():
            file_path.unlink()
            temp_output_path.rename(file_path)
            logging.info(f"Converted {file_path} to CD format.")

def convert_cue_to_utf8(cue_path):
    """Convert CUE file to UTF-8 encoding and backup the original."""
    backup_path = cue_path.with_suffix('.cue.backup')
    cue_path.rename(backup_path)
    
    # Detect encoding using chardet
    with open(backup_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        source_encoding = result['encoding']
        logging.info(f"Detected encoding: {source_encoding} for {cue_path}")

    # Convert file if encoding detected
    if source_encoding:
        try:
            with open(backup_path, 'r', encoding=source_encoding) as file:
                content = file.read()
            with open(cue_path, 'w', encoding='utf-8') as file:
                file.write(content)
            logging.info(f"Converted {cue_path} from {source_encoding} to UTF-8.")
        except UnicodeDecodeError:
            logging.error(f"Conversion failed for {cue_path}.")
            backup_path.rename(cue_path)
    else:
        logging.warning(f"Encoding detection failed for {cue_path}. Restoring backup.")
        backup_path.rename(cue_path)

def get_directory_size(directory):
    """Get the total size of all audio files in the directory."""
    total_size = 0
    for file in directory.glob('*'):
        if is_audio_file(file):
            total_size += file.stat().st_size
    return total_size

def get_average_audio_file_size(directory):
    """Get the average size of audio files in the directory."""
    total_size = 0
    count = 0
    for file in directory.glob('*'):
        if is_audio_file(file):
            total_size += file.stat().st_size
            count += 1
    return total_size / count if count > 0 else 0

def process_audio_files(path, audio_files):
    """Process and convert audio files in the directory."""
    for audio_file in audio_files:
        convert_to_cd_format(audio_file)

def delete_invalid_files(path):
    """Delete files where the filename follows specific invalid patterns."""
    for file in path.glob('*'):
        name = file.name
        if (len(name) > 5 and name[0] == '(' and name[1].isdigit() and name[2].isdigit() and 
            name[3] == ')' and name[4] == ' ' and name[5] == '[') or \
           (len(name) > 6 and name[0].isdigit() and name[1].isdigit() and name[2:] == '.flac'):
            file.unlink()
            logging.info(f"Deleted file {file} due to invalid naming convention.")

def handle_size_increase(path, initial_size):
    """Handle the case where the directory size increases significantly."""
    final_size = get_directory_size(path)
    if final_size >= 1.5 * initial_size:
        avg_size = get_average_audio_file_size(path)
        for file in path.glob('*'):
            if is_audio_file(file) and file.stat().st_size > avg_size and valid_filename(file):
                file.unlink()
                logging.info(f"Deleted file {file} due to exceeding average size.")

def process_directory(directory):
    """Process each directory for audio files and CUE files."""
    path = Path(directory)
    processing_file = path / '.processing'

    if processing_file.exists():
        delete_invalid_files(path)
    else:
        audio_files = [f for f in path.glob('*') if is_audio_file(f) and valid_filename(f)]
        if not audio_files:
            logging.info(f"No valid audio files found in {directory}, skipping.")
            return  # No valid audio files, skip this directory

        processing_file.touch()  # Create the .processing file if processing begins
        logging.info(f"Started processing directory {directory}")

    for cue_file in path.glob('*.cue'):
        convert_cue_to_utf8(cue_file)

    audio_files = [f for f in path.glob('*') if is_audio_file(f)]
    process_audio_files(path, audio_files)

    initial_size = get_directory_size(path)
    with change_directory(directory):
        try:
            subprocess.run(['sudo', 'split2flac', './', '-of', '(@track) [@performer] @title.@ext', '-F'], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running split2flac in directory {directory}: {e}")

    handle_size_increase(path, initial_size)

    logging.info(f"Finished processing directory {directory}")
    processing_file.unlink()  # Remove the .processing file

def traverse_directories(base_directory):
    """Walk through all subdirectories and process them recursively."""
    for root, dirs, files in os.walk(base_directory):
        try:
            process_directory(Path(root))
        except Exception as e:
            logging.error(f"Error processing directory {root}: {e}")
        for d in dirs:
            traverse_directories(Path(root) / d)  # Recursively process subdirectories

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python split.py <directory>")
        sys.exit(1)
    base_dir = sys.argv[1]
    logging.info(f"Starting traversal from base directory {base_dir}")
    traverse_directories(base_dir)
    logging.info("Completed traversal and processing.")
  
