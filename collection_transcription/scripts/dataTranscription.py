# This is a test file for modifying and running a test script for dataTranscription.py
# source /usr/local/bin/virtualenvwrapper.sh

### Actual code for transcription
print("Importing relervant libraries")
import pvfalcon
import whisper
import pandas as pd
from pandas import *
import os
import csv
import sys
import torch 
import numpy as np
import random
import paramiko
from scp import SCPClient

hostname = "stork"
port = 22
username = "rkawaka1"

"""
Description:
  These functions are used for copying audio data from stork
"""
def create_ssh_client(hostname, port, username):
  client = paramiko.SSHClient()
  client.load_system_host_keys()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  client.connect(hostname, port, username)
  return client

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
def makeDirFile(row):
  seriesTitle = row[1]
  # grandparent_dir = os.path.join(os.getcwd(), '..')
  parentPath = "gpu_Transcripts"
  # parentPath = os.path.join(grandparent_dir, parent_dir)
  dirPath = os.path.join(parentPath, seriesTitle)
  if (not (os.path.exists(dirPath))):
    os.mkdir(dirPath)
  return dirPath 

def ifTranscriptionExists(row):
  podName = row[1]
  epNum = row[2]
  seriesTitle = row[1]
  parentPath = "gpu_Transcripts2"
  dirPath = os.path.join(parentPath, seriesTitle)
  transPath = dirPath + "/trans_" + podName + "_" + epNum + ".txt"
  if os.path.exists(transPath):
    return True
  
  parentPath = "gpu_Transcripts"
  dirPath = os.path.join(parentPath, seriesTitle)
  transPath = dirPath + "/trans_" + podName + "_" + epNum + ".txt"
  if os.path.exists(transPath):
    return True

  parentPath = "gpu_Transcripts1"
  dirPath = os.path.join(parentPath, seriesTitle)
  transPath = dirPath + "/trans_" + podName + "_" + epNum + ".txt"
  return os.path.exists(transPath)


"""
Description: 
  Loop through the list of Falcon transcript segments and compare the overlap in time 
Param:
  transcrpt_segment: the Whisper transcript segment (dictionary)
  speaker_segment: the Falcon transcript segment
Return:
  the overlap in time between the two segments
"""
def segment_score(transcript_segment, speaker_segment):
    transcript_segment_start = transcript_segment["start"]
    transcript_segment_end = transcript_segment["end"]
    speaker_segment_start = speaker_segment.start_sec
    speaker_segment_end = speaker_segment.end_sec
    # print("transcript_segment_start: %f" % float(transcript_segment_start))
    # print("transcript_segment_end: %f" % float(transcript_segment_end))
    # print("speaker_segment_start: %f" % float(speaker_segment_start))
    # print("speaker_segment_end: %f" % float(speaker_segment_end))

    overlap = min(transcript_segment_end, speaker_segment_end) - max(transcript_segment_start, speaker_segment_start)
    overlap_ratio = overlap / (transcript_segment_end - transcript_segment_start)
    return overlap_ratio

"""
Description:
  Parse the file metadata to get the PATH to the .mp3 file of the target podcast episode
Param: 
  row: a CSV row that contains metadata about the podcast episode
Return:
  the path to the mp3 file
"""
def getPathToMP3(row):
  seriesTitle = row[1]
  audioFilename = "pod_" + row[0] + ".mp3"

  # Local path where the file will be stored temporarily
  local_dir = os.path.join(os.getcwd(), 'temp_audio')
  if not os.path.exists(local_dir):
    os.makedirs(local_dir)
  local_file_path = os.path.join(local_dir, audioFilename)

  # Remote path on the remote machine
  remote_dir = "/local/Audio-Files"  # Adjust the path as needed
  remote_file_path = os.path.join(remote_dir, seriesTitle, audioFilename)

  # Fetch the file from the remote machine
  ssh_client = create_ssh_client(hostname, port, username)
  scp = SCPClient(ssh_client.get_transport())
  scp.get(remote_file_path, local_file_path)

  scp.close()
  ssh_client.close()

  return local_file_path

  grandparent_dir = os.path.join(os.getcwd(), '..')
  parent_dir = "onlyfirst_Audio-Files"
  #parent_dir = "Audio-Files"
  parentPath = os.path.join(grandparent_dir, parent_dir)
  dirPath = os.path.join(parentPath, seriesTitle)
  filePath = os.path.join(dirPath, audioFilename)
  return filePath

"""
Description:
    Check if the arguments passed to the script are valid 
Param:
    argv: a list of arguments. 
    argv[0]: Transcription.py
    argv[1]: startNum (the idx of the row from which the program starts the transcription)
    argv[2]: iteration (the number of iterations this program is responsible for)
"""
# def argvCheck(argv):
#   # print(argv)


def saveCSV(df, file_name):
  df.to_csv(file_name, index = False, mode='a', header=False)

def main(): 
  # argvCheck(sys.argv)
  startIdx = int(sys.argv[1])
  iterations = int(sys.argv[2])
  # print(startIdx, iterations)

  """
  Load the whisper model with GPU
  """
  # Define a seed value
  seed = 42

  # Set seed for Python's built-in random module
  random.seed(seed)

  # Set seed for NumPy
  np.random.seed(seed)

  # Set seed for PyTorch
  torch.manual_seed(seed)

  # If using CUDA, set seed for all CUDA devices
  if torch.cuda.is_available():
      torch.cuda.manual_seed(seed)
      torch.cuda.manual_seed_all(seed)  # if you are using multi-GPU

  # Ensure deterministic behavior for some operations
  torch.backends.cudnn.deterministic = True
  torch.backends.cudnn.benchmark = False


  if torch.cuda.is_available():
    print(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
    model = whisper.load_model("small", device="cuda") #@param ['tiny', 'base', 'small', 'medium', 'large']  
  else:
    print("CUDA is not available. Using CPU.")
    model = whisper.load_model("small")

  """
  Iterate through the CSV file and transcribe podcasts row by row until >= startIdx + iterations
  """
  csvName = "podMetadata.csv"
  #csvName = "test_podMetadata.csv"
  errorLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'])
  transcriptionLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'] )

  with open(csvName, 'r') as csvfile: 
    datareader = csv.reader(csvfile)
    datareader.__next__() # skip the first row of CSV file, [ID,podName,epNum,date,duration]
    cur_row = 1  
    for row in datareader:
      cur_row += 1
      if cur_row < startIdx:
        continue
      elif cur_row >= startIdx + iterations:
        break
      print(row)

      podName = row[1]
      epNum = row[2]

      # transPath = makeDirFile(row) + "/trans_" + podName + "_" + epNum + ".txt"
      if (ifTranscriptionExists(row)):
        continue

      try:
        audioPath = getPathToMP3(row)
      except:
        # errorLog.append({'ID': "EXCEPTION", 'ErrorType': "Audio Path Not Found", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Audio Path Not Found", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
        continue

      try:
        result = model.transcribe(audioPath)
        # print(result)
      except:
        # errorLog.append({'ID': "EXCEPTION", 'ErrorType': "Whisper Transcription Failure", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Whisper Transcription Failure", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
        delete_local_file(audioPath)
        continue

      transcript_segments = result["segments"] # segments: list of dictionaries of details about segments (=sentences?)

      transPath = makeDirFile(row) + "/trans_" + podName + "_" + epNum + ".txt"
      print("Successfully trasncribed the episode with Whisper")

      try:
        # Using Rei's Swat Email
        # falcon = pvfalcon.create(access_key = 'NFRLmq4nxT9DDiV0qgRCjIAjgmyVC18L9DIfolT7qpoxNmws7quG6A==') #Rei's personal key
        # Using Rei's personal email1
        # falcon = pvfalcon.create(access_key = 'dkqnU1NYDgSQoypaP1KPaCCb7UzEDpqTLH3pCKGOMJPiXFPuqkIfpQ==')
        # Using Rei's second personal email
        # falcon = pvfalcon.create(access_key = 'Xl2yeie85kOKBuVa9Yz0+pY8c/7BETekwxiy6bMi164nXUY1CyX25g==')
        # Using Rei's UTokyo email
        #falcon = pvfalcon.create(access_key = 'Dp4UhziBWxdgmPCNtmrzlxZi2ofvHIqFGWGplhNT3asZI2zuVJqMlw==')
        # Using newly created Ray email
        # falcon = pvfalcon.create(access_key = 'FM3ehugbx5nab5E9p8SYM3YdT4+wCcK1QZf529WaR9O0zEAVBl4rHw==')
        # Using Paulina's email
        falcon = pvfalcon.create(access_key = 'frMKpICnnucPwL8b3czILpbrQlSREAx/sPczBXroyK0QGbZ1GVga3A==')
        speaker_segments = falcon.process_file(audioPath) # each spearker_segment has "speaker_tag" fields indicating speaker
      except:
        # errorLog.append({'ID': "EXCEPTION", 'ErrorType': "Falcon Transcription Failure", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': "EXCEPTION", 'ErrorType': "Falcon Transcription Failure", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
        delete_local_file(audioPath)
        continue


      """ 
      Merge transcripts from Whisper and Falcon by finding the Falcon transcript segment that 
      overlaps the most with the Whisper segment
      """
      with open(transPath, 'w') as f:
          for t_segment in transcript_segments:
            # print("This is t_segment")
            # print(t_segment)
            max_score = 0
            best_s_segment = None
            for s_segment in speaker_segments:
              # print("This is the s_segment")
              # print(s_segment)
              score = segment_score(t_segment, s_segment)
              # print("max: %f, score: %f" % (float(max_score), float(score)))
              if score > max_score:
                max_score = score
                best_s_segment = s_segment # found the best-matching Falcon speaker segment
              # else:
              #   best_s_segment = t_segment
            try:
              # print("This is the best_s_segment")
              # print(best_s_segment)
              # print(f"Speaker {best_s_segment.speaker_tag}: {t_segment['text']}\n")  #Error: best_s_segment is NoneType
              f.write(f"Speaker {best_s_segment.speaker_tag}: {t_segment['text']}\n")
            except TypeError:
              #print("SKIPPED: A TypeError error has occured")
              # print(f"Speaker unidentified (TypeError): {t_segment['text']}\n")  #Error: best_s_segment is NoneType
              f.write(f"Speaker unidentified (TypeError): {t_segment['text']}\n")
            except AttributeError:
              #print("SKIPPED: An AttributeError error has occured")
              # print(f"Speaker unidentified (AttributeError): {t_segment['text']}\n")  #Error: best_s_segment is NoneType
              f.write(f"Speaker unidentified (AttributeError): {t_segment['text']}\n")

      print(f"File '{transPath}' created and data saved successfully!")
      #transcriptionLog.append({'ID': "PASSED", 'ErrorType': "Transcription end of loop", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
      transcriptionLog = pd.concat([transcriptionLog, pd.DataFrame([{'ID': "PASSED", 'ErrorType': "Transcription end of loop", 'Podcast': podName, 'Episode': epNum}])], ignore_index=True)
      # datareader.__next__()
      # datareader.__next__()
      # if count == 5:
      #   exit()
      
      # Delete the local MP3 file after processing
      delete_local_file(audioPath)
      
  saveCSV(errorLog, 'errorLog_Transcription.csv')
  saveCSV(transcriptionLog, 'transcriptionLog.csv')
  print("saved CSV files")
        

if __name__ == "__main__":
    main()


