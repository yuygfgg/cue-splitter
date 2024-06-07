import sys
import os
import subprocess
from pathlib import Path
import chardet
import logging
import signal
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Supported audio file extensions
audio_extensions = ['.flac', '.ape', '.mv', '.wav']

# Global variable to track if a SIGINT has been received
sigint_received = False

class InterruptException(Exception):
    pass

@contextmanager
def change_directory(directory):
    """Context manager for changing the working directory."""
    original_directory = Path.cwd().resolve()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(original_directory)

def handle_sigint(signum, frame):
    global sigint_received
    sigint_received = True
    logging.error("SIGINT received. Terminating the script.")
    raise InterruptException("SIGINT received")

def is_audio_file(file_path):
    """Check if the file has an audio file extension."""
    return file_path.suffix.lower() in audio_extensions

def valid_filename(file_path):
    """Check filename based on two conditions:
    1. The second and third characters are not both digits and the length is greater than 2.
    2. The first two characters are digits and the length is greater than 7.
    """
    name = file_path.stem
    condition1 = len(name) > 2 and not (name[1].isdigit() and name[2].isdigit())
    condition2 = len(name) > 7 and not (name[0].isdigit() and name[1].isdigit())
    return condition1 and condition2

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
    cue_path = cue_path.resolve()
    backup_path = cue_path.with_suffix('.cue.backup')
    cue_path.rename(backup_path)
    
    # Detect encoding using chardet
    with open(backup_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        source_encoding = result['encoding']
        # Treat all GB* encodings as GBK
        if source_encoding and source_encoding.lower().startswith('gb'):
            source_encoding = 'GBK'
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
    directory = Path(directory).resolve()
    total_size = 0
    for file in directory.glob('*'):
        if is_audio_file(file):
            total_size += file.stat().st_size
    return total_size

def get_average_audio_file_size(directory):
    """Get the average size of audio files in the directory."""
    directory = Path(directory).resolve()
    total_size = 0
    count = 0
    for file in directory.glob('*'):
        if is_audio_file(file):
            total_size += file.stat().st_size
            count += 1
    return total_size / count if count > 0 else 0

def process_audio_files(directory, audio_files):
    """Process and convert audio files in the directory."""
    directory = Path(directory).resolve()
    for audio_file in audio_files:
        audio_file = audio_file.resolve()
        convert_to_cd_format(audio_file)

def delete_invalid_files(directory):
    """Delete files where the filename follows specific invalid patterns."""
    directory = Path(directory).resolve()
    for file in directory.glob('*'):
        name = file.name
        if (len(name) > 5 and name[0] == '(' and name[1].isdigit() and name[2].isdigit() and 
            name[3] == ')' and name[4] == ' ' and name[5] == '[') or \
           (len(name) > 6 and name[0].isdigit() and name[1].isdigit() and name[2:] == '.flac'):
            logging.info(f"Deleting file {file} due to invalid naming convention.")
            try:
                file.unlink()
                logging.info(f"Deleted file {file}")
            except Exception as e:
                logging.error(f"Error deleting file {file}: {e}")

def handle_size_increase(directory, initial_size):
    """Handle the case where the directory size increases significantly."""
    directory = Path(directory).resolve()
    final_size = get_directory_size(directory)
    logging.info(f"handle_size_increase in {directory} initial size = {initial_size} final_size = {final_size}")
    if final_size >= 1.5 * initial_size:
        avg_size = get_average_audio_file_size(directory)
        for file in directory.glob('*'):
            if is_audio_file(file) and file.stat().st_size > avg_size and valid_filename(file):
                file.unlink()
                logging.info(f"Deleted file {file} due to exceeding average size.")

def process_directory(directory):
    """Process each directory for audio files and CUE files."""
    global sigint_received
    if sigint_received:
        return
    path = Path(directory).resolve()
    processing_file = path / '.processing'

    try:
        if processing_file.exists():
            logging.info(f".processing file exists in {directory}. Deleting invalid files.")
            delete_invalid_files(path)
        else:
            audio_files = [f for f in path.glob('*') if is_audio_file(f) and valid_filename(f)]
            if not audio_files:
                logging.info(f"No valid audio files found in {directory}, skipping.")
                return  # No valid audio files, skip this directory

            logging.info(f"Creating .processing file in {directory}")
            processing_file.touch()  # Create the .processing file if processing begins
            logging.info(f"Started processing directory {directory}")

        for cue_file in path.glob('*.cue'):
            logging.info(f"Converting CUE file {cue_file} to UTF-8")
            convert_cue_to_utf8(cue_file)

        audio_files = [f for f in path.glob('*') if is_audio_file(f)]
        logging.info(f"Processing audio files in {directory}")
        process_audio_files(path, audio_files)

        initial_size = get_directory_size(path)
        logging.info(f"Initial size of directory {directory}: {initial_size}")
        with change_directory(directory):
            try:
                logging.info(f"Running split2flac in {directory}")
                subprocess.run(['sudo', 'split2flac', './', '-of', '(@track) [@performer] @title.@ext', '-nC', '-F'], check=True)
                # Handle size increase only if split2flac runs successfully
                handle_size_increase(path, initial_size)
                logging.info(f"Finished processing directory {directory}")
                if processing_file.exists() and not sigint_received:
                    logging.info(f"Removing .processing file in {directory}")
                    processing_file.unlink()  # Remove the .processing file only if everything succeeds
            except subprocess.CalledProcessError as e:
                if e.returncode == -signal.SIGINT:
                    sigint_received = True
                    logging.error(f"split2flac interrupted by SIGINT in directory {directory}")
                    raise InterruptException("split2flac interrupted by SIGINT")
                else:
                    logging.error(f"Error running split2flac in directory {directory}: {e}")
    #                raise  # Re-raise the exception to ensure .processing file is not deleted
            except KeyboardInterrupt:
                sigint_received = True
                logging.error(f"split2flac interrupted in directory {directory}")
                raise InterruptException("split2flac interrupted by SIGINT")
            except Exception as e:
                logging.error(f"Unexpected error processing directory {directory}: {e}")
                raise  # Re-raise the exception to ensure .processing file is not deleted
    except InterruptException as e:
        logging.error(f"Error in process_directory for {directory}: {e}")
        raise  # Re-raise to ensure script stops
    finally:
        if not sigint_received and processing_file.exists():
            try:
                logging.info(f"Removing .processing file in finally block for {directory}")
                processing_file.unlink()
            except Exception as unlink_error:
                logging.error(f"Error removing .processing file in finally block: {unlink_error}")

def traverse_directories(base_directory):
    """Walk through all subdirectories and process them recursively."""
    global sigint_received
    base_directory = Path(base_directory).resolve()
    folder_count = 0
    try:
        for root, dirs, files in os.walk(base_directory):
            root_path = Path(root).resolve()
            if sigint_received:
                break
            if root_path.name.lower() in ['scans', 'scan']:
                logging.info(f"Skipping directory {root_path} (name matches 'Scans' or 'scan')")
                continue
            try:
                process_directory(root_path)
                folder_count += 1
            except InterruptException:
                logging.info(f"InterruptException caught, stopping traversal.")
                break
            except Exception as e:
                logging.error(f"Error processing directory {root_path}: {e}")
                break  # Stop processing further directories on error
    except Exception as e:
        logging.error(f"Error walking through base directory {base_directory}: {e}")
    logging.info(f"Total directories processed: {folder_count}")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handle_sigint)
    
    if len(sys.argv) != 2:
        print("Usage: python split.py <directory>")
        sys.exit(1)
    base_dir = Path(sys.argv[1]).resolve()
    logging.info(f"Starting traversal from base directory {base_dir}")
    
    try:
        traverse_directories(base_dir)
    except InterruptException:
        logging.info("Script interrupted by SIGINT.")
        sys.exit(1)
    
    logging.info("Completed traversal and processing.")
