"""
This is a file for checking if we have downloaded all the necessary files. 
Condition: 
    We have errorLog.csv for data collection, which records failed either. It contains:
        1. failed to find duration 
        2. failed to save mp3 file
    In case 1, it continues to save mp3 file. 
    In case 2, it does not save the mp3 file and does not create a file for the episode. 
    Regardless of if it succeeded or not, every episode is added to the podMetadata.csv 

Expected failures:
    * path to audio file doesn't exist 
    * path exists but it doesn't contain audio file
        * if not mp3, are they 
            * Falcon: 3gp (AMR), FLAC, MP4/m4a (AAC), Ogg, WAV, and WebM.?
            * Whisper: mp3 , mp4 , mpeg , mpga , m4a , wav , and webm
    * path exists but file size is too small for an episode: it needs to be larger than 

Structure of this script:
    1. For each row of the podMetadata.csv, 
        a. create a potential path to the audio file 
        b. check if the file exists
            b1. if not, add to the error log and continue to the next row 
        c. check if the type of the file is .mp3
            c1. if not, add to the error log and continue to the next row
        d. check if the file is appropriate size (if duration < 5 mins, add it to the log with the duration)
            d1. if too short, add it to the error log
    2. Save the error log to the csv file 
"""
import pandas as pd
import csv
import os
from mutagen.mp3 import MP3
from mutagen import MutagenError
import re
from mutagen.mp4 import MP4
from mutagen.ogg import OggFileType
from mutagen.flac import FLAC
from mutagen.wavpack import WavPack
from mutagen.aiff import AIFF
import subprocess
import json

def saveCSV(df, file_name):
  df.to_csv(file_name, index = False, mode='a', header=False)

def get_file_info(file_path):
    """
    Use ffprobe to get metadata about the file.
    Returns a dictionary with metadata information.
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,streams', '-of', 'json', file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        metadata = json.loads(result.stdout)
        return metadata
    except subprocess.CalledProcessError as e:
        print(f"Error executing ffprobe: {e}")
        return None

def is_webm(file_path):
    """
    Check if a file is a WebM file by inspecting its metadata.
    Returns True if the file is WebM, False otherwise.
    """
    metadata = get_file_info(file_path)
    if metadata:
        # Inspect the format and codec information to determine if it is WebM
        format_name = metadata.get('format', {}).get('format_name', '')
        if 'webm' in format_name:
            return True
    return False

def is_mp3(file_path):
    try:
        # Try MP3
        MP3(file_path)
        return "MP3"
    except MutagenError:
        pass  # Not an MP3

    try:
        # Try MP4/M4A (AAC)
        MP4(file_path)
        return "MP4/M4A (AAC)"
    except MutagenError:
        pass  # Not an MP4/M4A

    try:
        # Try WAV (WavPack)
        WavPack(file_path)
        return "WAV"
    except MutagenError:
        pass  # Not a WAV file

    return None  # Unrecognized or unsupported file format

def check_file_duration(duration_str):
    match = re.match(r'(\d+):(\d+):(\d+)', duration_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        # Convert the entire duration to seconds (ignoring milliseconds)
        total_seconds = hours * 60 * 60 + minutes * 60 + seconds
        return total_seconds <= 3 * 60 #compare with 3 minutes
    match = re.match(r'(\d+):(\d+)', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))   
        total_seconds = minutes * 60 + seconds
        return total_seconds <= 3 * 60 #compare with 3 minutes
    else:
        return int(duration_str) <= 3 * 60

def main():
    csvName = "podMetadata.csv"
    errorLog = pd.DataFrame(columns = ['ID', 'Podcast', 'Episode', 'Error_Description'])
    checkLog = pd.DataFrame(columns = ['ID', 'Podcast', 'Episode'] )
    count = 0
    with open(csvName, 'r') as csvfile: 
        datareader = csv.reader(csvfile)
        datareader.__next__() # skip the first row of CSV file, [ID,podName,epNum,date,duration]
        for row in datareader:
            print(row)
            #count += 1
            #if count > 10:
            #    break
            podName = row[1]
            fileName = "pod_" + row[0] + ".mp3"
            filePath = os.path.join("Audio-Files", podName, fileName)

            ## Check if file exists
            if not os.path.exists(filePath):
                errorLog = pd.concat([errorLog, pd.DataFrame([{
                    "ID":row[0], "Podcast":podName, "Episode":row[2],
                    "Error_Description": "Audio file doesn't exists"
                }])])
                continue

            # Check if it is .mp3
            # audio = is_mp3(filePath)
            #if audio is None:
            #    if not is_webm(filePath):
            #        errorLog = pd.concat([errorLog, pd.DataFrame([{
            #            "ID": row[0], "Podcast": podName, "Episode": row[2],
            #            "Error_Description": "File is not a valid audio file for falcon"
            #        }])])
            #        continue
            audio = is_mp3(filePath)
            if audio is None:
                errorLog = pd.concat([errorLog, pd.DataFrame([{
                    "ID": row[0], "Podcast": podName, "Episode": row[2],
                    "Error_Description": "File is not a valid audio file for falcon"
                }])])
                continue
            
            if check_file_duration(row[4]):
                errorLog = pd.concat([errorLog, pd.DataFrame([{
                    "ID": row[0], "Podcast": podName, "Episode": row[2],
                    "Error_Description": "Duration is too short"
                }])])
                continue

            checkLog = pd.concat([checkLog, pd.DataFrame([{"ID":row[0], "Podcast":podName, "Episode":row[2]}])])
    saveCSV(errorLog, "errorLog_audiocheck.csv")  
    saveCSV(checkLog, "audiocheck_Log.csv") 

if __name__ == "__main__":
    main()
