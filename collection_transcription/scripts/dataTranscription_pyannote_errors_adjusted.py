import whisper
from pyannote.audio import Pipeline
import pyannote
import torch
import pandas as pd
from pandas import *
import sys
import csv
from scp import SCPClient
import os
from pydub import AudioSegment
import paramiko
import warnings
import logging
import traceback

hostname = "stork"
port = 22
username = "rkawaka1"

def get_words_timestamps(result_transcription: dict) -> dict:
    """Get all words, their start and end times into a dict"""
    words = {}
    word_counter = 0
    for segment in result_transcription["segments"]:
        for word in segment["words"]:
            words[f"word_{word_counter}"] = {
                "text": word["word"],
                "start": word["start"],
                "end": word["end"],
            }
            word_counter += 1
    return words

def words_per_segment(
    res_transcription: dict,
    res_diarization: pyannote.core.Annotation,
    add_buffer: bool = True,
    fixed_margin: float = 0.5,  # Default fixed buffer value in seconds
    gap_scale_factor: float = 0.5,  # Default scale factor for dynamic buffer
) -> dict:
    """Get all words per segment and their start and end times into a dict

    Args:
        res_transcription (dict): The transcription result from the whisper library
        res_diarization (pyannote.core.Annotation): The diarization result from the pyannote library
        add_buffer (bool): Whether to add buffer time to segment start and end
        fixed_margin (float): The fixed buffer time in seconds
        gap_scale_factor (float): The scale factor for the dynamic buffer

    Returns:
        dict: A dict containing all words per segment and their start and end times and the speaker
    """

    def calculate_dynamic_before_buffer(idx, segments):
        """Calculate the buffer time based on the previous and current segment"""
        if idx == 0 or idx == len(segments) - 1:
            return fixed_margin
        
        ## In short, previous_end != current_start ?
        previous_end = segments[idx - 1]["end"]
        current_start = segments[idx]["start"]
        return (current_start - previous_end) * gap_scale_factor

    def calculate_dynamic_after_buffer(idx, segments):
        """Calculate the buffer time based on the previous and current segment"""
        if idx == 0 or idx == len(segments) - 1:
            return fixed_margin
        
        ## In short, previous_end != current_start ?
        cur_end = segments[idx]["end"]
        next_start = segments[idx+1]["start"]
        return (next_start - cur_end) * gap_scale_factor

    res_trans_dia = {}
    # segments = list(res_diarization.itersegments())
    segments = [
        {"start": segment.start, "end": segment.end, "speaker": label}
        for segment, _, label in res_diarization.itertracks(yield_label=True)
    ]


    ## get a dict of all the (word, start_time, end_time) tuples in the episode
    words = get_words_timestamps(res_transcription)

    for idx, (segment, _, speaker) in enumerate(
        res_diarization.itertracks(yield_label=True)
    ):  
        ### Get the adjusted_start time and adjusted_end time of each speaker diarization segment
        before_buffer_time = calculate_dynamic_before_buffer(idx, segments) if add_buffer else 0
        after_buffer_time = calculate_dynamic_after_buffer(idx, segments) if add_buffer else 0

        """
        What I think we should be doing is, we should have two buffers - before_buffer and after_buffer
        The before buffer:
            cur_segment.start - prev_segment.end) / 2
        The after buffer:
            (next_segment.start 0 cur_segment.end) / 2
        Then, calculate the adjusted start by doing:
            adjusted_start = max(0, cur_segment.start - before_buffer) if idx != 0 else 0
            adjusted_end = cur_segment.start + after_buffer if idx != len(segments) - 1 else segment.end
        By doing so, based on the assumption that prev_end != cur_start and cur_end != next_start, 
        we can include any words that appear on any time. Now, we calcualte the buffer_time based only on 
        (prev_end - cur_start) * 0.3. This is not going to be able to cover the entire timespan, resulting 
        in posisble lost words in the transcripts. 
        """
        adjusted_start = max(0, segment.start - before_buffer_time) if idx != 0 else 0
        adjusted_end = (
            segment.end + after_buffer_time if idx != len(segments) - 1 else segment.end
        )

        ### Based on the dict of words from Whisper, if the word appears between adjusted_start and adjusted_end, add it to the segment's list of words
        segment_words = []
        for _, word in words.items():
            if word["start"] >= adjusted_start and word["end"] <= adjusted_end:
                segment_words.append(word["text"])
            if word["start"] >= adjusted_end:
                break

        ### Join the list of the segment's words and add it to the larger list of segments of the episode. 
        res_trans_dia[f"segment_{idx}"] = {
            "speaker": speaker,
            "text": " ".join(segment_words),
            "start": adjusted_start,
            "end": adjusted_end,
        }

        # print(f"Segment {idx}: start={adjusted_start}, end={adjusted_end}")
        # print(f"Words in segment {idx}: {segment_words}")
        
    return res_trans_dia


# def words_per_segment(
#     res_transcription: dict,
#     res_diarization: pyannote.core.Annotation,
#     add_buffer: bool = True,
#     fixed_margin: float = 0.5,  # Default fixed buffer value in seconds
#     gap_scale_factor: float = 0.3,  # Default scale factor for dynamic buffer
# ) -> dict:
#     """Get all words per segment and their start and end times into a dict

#     Args:
#         res_transcription (dict): The transcription result from the whisper library
#         res_diarization (pyannote.core.Annotation): The diarization result from the pyannote library
#         add_buffer (bool): Whether to add buffer time to segment start and end
#         fixed_margin (float): The fixed buffer time in seconds
#         gap_scale_factor (float): The scale factor for the dynamic buffer

#     Returns:
#         dict: A dict containing all words per segment and their start and end times and the speaker
#     """

#     def calculate_dynamic_buffer(idx, segments):
#         """Calculate the buffer time based on the previous and current segment"""
#         if idx == 0 or idx == len(segments) - 1:
#             return fixed_margin
#         previous_end = segments[idx - 1].end
#         current_start = segments[idx].start
#         return (current_start - previous_end) * gap_scale_factor

#     res_trans_dia = {}
#     segments = list(res_diarization.itersegments())

#     words = get_words_timestamps(res_transcription)

#     for idx, (segment, _, speaker) in enumerate(
#         res_diarization.itertracks(yield_label=True)
#     ):
#         buffer_time = calculate_dynamic_buffer(idx, segments) if add_buffer else 0

#         adjusted_start = max(0, segment.start - buffer_time) if idx != 0 else 0
#         adjusted_end = (
#             segment.end + buffer_time if idx != len(segments) - 1 else segment.end
#         )

#         segment_words = []
#         for _, word in words.items():
#             if word["start"] >= adjusted_start and word["end"] <= adjusted_end:
#                 segment_words.append(word["text"])
#             if word["start"] >= adjusted_end:
#                 break

#         res_trans_dia[f"segment_{idx}"] = {
#             "speaker": speaker,
#             "text": " ".join(segment_words),
#             "start": adjusted_start,
#             "end": adjusted_end,
#         }

#         print(f"Segment {idx}: start={adjusted_start}, end={adjusted_end}")
#         print(f"Words in segment {idx}: {segment_words}")
#     return res_trans_dia

def saveCSV(df, file_name):
  df.to_csv(file_name, index = False, mode='a', header=False)

def create_ssh_client(hostname, port, username):
  client = paramiko.SSHClient()
  client.load_system_host_keys()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  client.connect(hostname, port, username)
  return client

def getPathToMP3(podName, audio_file):
    local_dir = os.path.join(os.getcwd(), 'temp_audio')
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    local_file_path = os.path.join(local_dir, audio_file) + ".mp3"


        # Define remote directories
    primary_dir = "/local/Audio-Files-Nov5-2"
    secondary_dir = "/local/Audio-Files-Nov5"

    # Build paths for the primary and secondary directories
    primary_file_path = os.path.join(primary_dir, podName, audio_file) + ".mp3"
    secondary_file_path = os.path.join(secondary_dir, podName, audio_file) + ".mp3"

    # Fetch the file from the remote machine
    ssh_client = create_ssh_client(hostname, port, username)
    scp = SCPClient(ssh_client.get_transport())

    try:
        # Try to fetch the file from the primary directory
        print("Trying to copy from primary location:", primary_file_path)
        scp.get(primary_file_path, local_file_path)
    except Exception as e_primary:
        print(f"Primary location failed: {e_primary}")
        try:
            # If primary fails, try the secondary directory
            scp = SCPClient(ssh_client.get_transport())
            print("Trying to copy from secondary location:", secondary_file_path)
            scp.get(secondary_file_path, local_file_path)
        except Exception as e_secondary:
            print(f"Secondary location failed: {e_secondary}")
            raise FileNotFoundError("File not found in either primary or secondary location.")

    # # Remote path on the remote machine
    # remote_dir = "/local/Audio-Files-Nov5"  # Adjust the path as needed
    # remote_file_path = os.path.join(remote_dir, podName, audio_file)
    # remote_file_path = remote_file_path + ".mp3"
    # print("copying from: ", remote_file_path)

    # # Fetch the file from the remote machine
    # ssh_client = create_ssh_client(hostname, port, username)
    # scp = SCPClient(ssh_client.get_transport())
    # scp.get(remote_file_path, local_file_path)
    # # print("copied")

    scp.close()
    ssh_client.close()
    return local_file_path, local_dir

def convertToWAV(local_file_path, local_dir, audio_file):
    # Convert to .wav if needed
    if not local_file_path.endswith('.wav'):
        audio = AudioSegment.from_file(local_file_path)
        wav_file_path = os.path.join(local_dir, f"{os.path.splitext(audio_file)[0]}.wav")
        audio.export(wav_file_path, format="wav")

        os.remove(local_file_path)
        print(f"Deleted file: {local_file_path}")

        return wav_file_path  # Return the new .wav file path
    else:
        return local_file_path

def delete_local_file(file_path):
  """Delete the local MP3 file after processing"""
  if os.path.exists(file_path):
    os.remove(file_path)
    print(f"Deleted file: {file_path}")

"""
Description:
  Parse the file metadata to create the PATH to the parent directory of the transcript
  If the parent directory is not created yet, create one
  Return the path to the path to the parent directory
Param: row (formatted in [ID, podName, epNum, date, duration])
Return: dirPath (PATH)
"""
def makeDirFile(podName):
    seriesTitle = podName
    # grandparent_dir = os.path.join(os.getcwd(), '..')
    parentPath = "gpu_Transcripts_Nov5_2"
    # parentPath = os.path.join(grandparent_dir, parent_dir)
    dirPath = os.path.join(parentPath, seriesTitle)
    if (not (os.path.exists(dirPath))):
        os.mkdir(dirPath)
    return dirPath 

def main():
    startIdx = int(sys.argv[1])
    iterations = int(sys.argv[2])


    """ Load the whisper model with GPU """
    ## Deciding if GPUs are available and load the models   
    # device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # device = torch.device("cpu")
    print(f"Using device: {device}")

    print("Loading whisper model")
    model = whisper.load_model("medium").to(device)  # Move the whisper model to GPU if available
    # model = whisper.load_model("medium").to(device, non_blocking=True)  # Move the whisper model to GPU if available
    # model = whisper.load_model("medium").to("cuda").half()

    print("Building pipelines")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", use_auth_token="HF TOKEN"
    ).to(device)  # Move the pipeline to GPU if available

    # csvName = "podMetadata_Nov5.csv"
    csvName = "errorLog_checktranscripts_Nov5_3.csv"
    errorLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'])
    transcriptionLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'] )

    with open(csvName, 'r') as csvfile: 
        datareader = csv.reader(csvfile)
        # datareader.__next__() # skip the first row of CSV file, [ID,podName,epNum,date,duration]
        # cur_row = 1  
        cur_row = 0
        for row in datareader:
            cur_row += 1
            if cur_row < startIdx:
                continue
            elif cur_row >= startIdx + iterations:
                break
            print(row[0])

            audio_file = row[0]
            # print("filename")
            filename_no_ext = audio_file.replace(".mp3", "")
            parts = filename_no_ext.split('_')

            podName = parts[0]
            epNum = parts[1]

            transPath = makeDirFile(podName) + "/trans_" + podName + "_" + epNum + ".txt"
            if os.path.exists(transPath):
                print("transcript exists for", audio_file)
                continue

            try:
                # audioPath = getPathToMP3(row)
                audioPath, local_dir = getPathToMP3(podName, "pod_" + audio_file)
            except:
                # errorLog.append({'ID': "EXCEPTION", 'ErrorType': "Audio Path Not Found", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
                print("Audio Path Not Found")
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Audio Path Not Found", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue

            try:
                audioPath = convertToWAV(audioPath, local_dir, "pod_" + audio_file)
                print("WAV path is: %s" % audioPath)
            except:
                print("Format Conversion Failed")
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Format Conversion Failed", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue

            """ Transcribing """
            ## Transcribe with Pyannote pipeline
            print("Transcribing with pyannote")
            try:
                diarization_result = pipeline(audioPath)
            except:
                print("Pyannote Pipeline Failed")
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Pyannote Pipline Failed", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue
 
            print("Transcribing with whisper")
            try:
                transcription_result = model.transcribe(audioPath, word_timestamps=True)
            except:
                print("Whisper Failed")
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Whisper Failed", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue

            
            ## TODO: add a try-catch 
            print("Merging the results")
            try:
                final_result = words_per_segment(transcription_result, diarization_result)
            except Exception as e:
                print("Merging failed")
                # Print the type of exception and its message
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {e}")
                # Print the full traceback for more context
                traceback.print_exc()
                
                print("Merging failed")
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Merging Failed", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue


            # transPath = makeDirFile(podName) + "/trans_" + podName + "_" + epNum + ".txt"
            
            """ Saving the Results into the .txt File """
            ## TODO: add a try-catch 
            try:
                with open(transPath, "w") as f:
                    for _, segment in final_result.items():
                        f.write(f'{segment["start"]:.3f}\t{segment["end"]:.3f}\t {segment["speaker"]}\t{segment["text"]}\n')
            except:
                errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Saving to File Incomplete", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
                continue

            transcriptionLog = pd.concat([transcriptionLog, pd.DataFrame([{'ID': "PASSED", 'ErrorType': "Transcription end of loop", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
            print(f"File '{transPath}' created and data saved successfully!")
            delete_local_file(audioPath)


    saveCSV(errorLog, 'errorLog_Transcription_Nov5_errors.csv')
    saveCSV(transcriptionLog, 'transcriptionLog_Nov5_errors.csv')
    print("saved CSV files")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    logging.getLogger("speechbrain.utils.quirks").setLevel(logging.WARNING)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
    main()
