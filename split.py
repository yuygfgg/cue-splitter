import sys
import os
import subprocess
from pathlib import Path
import chardet
import logging
import signal
from contextlib import contextmanager
import os
import shutil
import logging
from mutagen.flac import FLAC
from datetime import datetime, timedelta
import re


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Supported audio file extensions
audio_extensions = ['.flac', '.ape', '.wv', '.wav', '.ape']

# Global variable to track if a SIGINT has been received
sigint_received = False

# Assume splitting finishes in 5 days
DAYS_THRESHOLD = 5

class InterruptException(Exception):
    pass

DATE_PATTERN = re.compile(r'^\d{4}\.\d{2}\.\d{2}')
DISC_PATTERN = re.compile(r'disc\s*(\d+)', re.IGNORECASE)

def set_tags(file_path, album, disc_number, disc_total):
    audio = FLAC(file_path)
    audio['ALBUM'] = album
    audio['DISCNUMBER'] = str(disc_number)
    audio['DISCTOTAL'] = str(disc_total)
    audio.save()

def process_muity_disc_album(directory):
    disc_numbers = []
    flac_files = []
    original_albums = set()

    # Collect all FLAC files and their disc numbers
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.flac'):
                file_path = os.path.join(root, file)
                audio = FLAC(file_path)
                album = audio.get('ALBUM', [None])[0]
                if album:
                    original_albums.add(album)
                    match = DISC_PATTERN.search(album)
                    if match:
                        disc_number = int(match.group(1))
                        disc_numbers.append(disc_number)
                        flac_files.append((file_path, disc_number, album))

    if not flac_files:
        return

    # Determine the new album name after removing "disc n"
    new_albums = {DISC_PATTERN.sub('', album).strip() for _, _, album in flac_files}

    if len(new_albums) > 1:
        print(f"Albums do not match after removing 'disc n'. Found:\n{new_albums}")
        correct_album = input("Please enter the correct album name (or press Enter to skip this directory): ").strip()
        if not correct_album:
            return
    else:
        correct_album = new_albums.pop()

    disc_total = max(disc_numbers)

    # Update tags for each FLAC file
    for file_path, disc_number, _ in flac_files:
        set_tags(file_path, correct_album, disc_number, disc_total)

def process_muity_disc_albums(base_directory):
    for root, dirs, _ in os.walk(base_directory):
        for dir in dirs:
            if DATE_PATTERN.match(dir):
                process_muity_disc_album(os.path.join(root, dir))


def create_new_folder_name(base_folder, album):
    new_folder_name = f"{base_folder} {album}"
    return new_folder_name

def move_non_audio_files(src_folder, dst_folder):
    for item in os.listdir(src_folder):
        item_path = os.path.join(src_folder, item)
        item_path = os.path.abspath(item_path)
        if os.path.isdir(item_path) and not any(f.endswith('.flac') for f in os.listdir(item_path)):
            shutil.copytree(item_path, os.path.join(dst_folder, item))
        elif not item_path.endswith('.flac'):
            shutil.copytree(item_path, dst_folder)

def process_folder(folder, base_folder_name):
    folder = os.path.abspath(folder)
    audio_files = []
    for root, _, files in os.walk(folder):
        root = os.path.abspath(root)
        for file in files:
            if file.endswith('.flac'):
                audio_files.append(os.path.join(root, file))
    
    if not audio_files:
        logging.info(f"No audio files found in folder: {folder}")
        return

    parent_folder = os.path.dirname(folder)

    logging.info(f"Processing folder: {folder}")

    for audio_file_path in audio_files:
        audio_file_path = os.path.abspath(audio_file_path)
        audio = FLAC(audio_file_path)
        album = audio.get('album', ['Unknown Album'])[0]
        new_folder_name = create_new_folder_name(base_folder_name, album)
        new_folder_path = os.path.join(parent_folder, new_folder_name)
        new_folder_path = os.path.abspath(new_folder_path)
        os.makedirs(new_folder_path, exist_ok=True)
        try:
            shutil.move(audio_file_path, new_folder_path)
            logging.info(f"Moved audio file '{audio_file_path}' to '{new_folder_path}'")
        except ValueError as e:
            logging.error(f"fail to move audio file! {e}")

    try:
        move_non_audio_files(folder, new_folder_path)
    except ValueError as e:
            logging.error(f"fail to move non-audio file! {e}")
    shutil.rmtree(folder)
    logging.info(f"Deleted original folder: {folder}")

def is_valid_integer(value):
    try:
        int(value)
        return True
    except ValueError:
        return False

def scan_and_process_mixed_album(base_path):
    base_path = os.path.abspath(base_path)
    cutoff_time = datetime.now() - timedelta(days=DAYS_THRESHOLD)
    for root, dirs, _ in os.walk(base_path):
        root = os.path.abspath(root)
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            folder_path = os.path.abspath(folder_path)
            
            # Skip folders last modified more than DAYS_THRESHOLD days ago
            if datetime.fromtimestamp(os.path.getmtime(folder_path)) < cutoff_time:
                logging.info(f"Skipping folder '{folder_path}' because it was last modified more than {DAYS_THRESHOLD} days ago")
                continue

            if len(dir_name) >= 10 and dir_name[:10].replace('.', '').isdigit():
                base_folder_name = dir_name[:10]  # Extract the base folder name (xxxx.xx.xx)
                skip_folder = False

                logging.info(f"Scanning folder: {folder_path}")

                albums = set()
                for subdir, _, files in os.walk(folder_path):
                    subdir = os.path.abspath(subdir)
                    for file in files:
                        if file.endswith('.flac'):
                            file_path = os.path.join(subdir, file)
                            file_path = os.path.abspath(file_path)
                            audio = FLAC(file_path)
                            total_discs = audio.get('totaldiscs', [1])[0]
                            disc_number = audio.get('discnumber', [1])[0]
                            album = audio.get('album', ['Unknown Album'])[0]
                            albums.add(album)
                            
                            # Ensure 'totaldiscs' and 'discnumber' are valid integers
                            if not (is_valid_integer(total_discs) and is_valid_integer(disc_number)):
                                continue
                            
                            total_discs = int(total_discs)
                            disc_number = int(disc_number)
                            
                            if total_discs > 1 or disc_number > 1:
                                skip_folder = True
                                logging.info(f"Skipping folder '{folder_path}' due to multiple discs set properly")
                                break
                    if skip_folder:
                        break

                if len(albums) == 1:
                    logging.info(f"Skipping folder '{folder_path}' since all audio files have the same album tag")
                    continue

                if not skip_folder:
                    process_folder(folder_path, base_folder_name)


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
    2. The first two characters are not digits and the length is GTE than 7.
    """
    name = file_path.stem
    condition1 = len(name) > 2 and not (name[1].isdigit() and name[2].isdigit())
    condition2 = len(name) >= 7 and not (name[0].isdigit() and name[1].isdigit())
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
                subprocess.run(['split2flac', './', '-of', '(@track) [@performer] @title.@ext', '-nC', '-F'], check=True)
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
    if sigint_received:
        sys.exit(1)
    logging.info(f"Starting scan and process muili-disc album in base path: {base_dir}")
    process_muity_disc_albums(base_dir)
    if sigint_received:
        sys.exit(1)
#The following line will create a separated folder for each album and copy non-audio files to each new folder. It may take a lot of extra disk space and not fully tested. Remove # if you need.
#    logging.info(f"Starting scan and process mixed album in base path: {base_dir}")
#    scan_and_process_mixed_album(base_dir)
    logging.info("Scan and process completed.")
