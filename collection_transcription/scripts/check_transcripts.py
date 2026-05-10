import pandas as pd
from pandas import *
import os
import csv

def ifTranscriptionExists(row):
  podName = row[1]
  epNum = row[2]
  seriesTitle = row[1]

  parentPath = "Transcripts"
  dirPath = os.path.join(parentPath, seriesTitle)
  transPath = dirPath + "/trans_" + podName + "_" + epNum + ".txt"
  return os.path.exists(transPath)

def saveCSV(df, file_name):
  df.to_csv(file_name, index = False, mode='a', header=False)

def main():
    csvname = "final_podMetadata.csv"
    errorLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'])
    transcriptionLog = pd.DataFrame(columns = ['ID', 'Status', 'Podcast', 'Episode'] )
    with open(csvname, 'r') as csvfile: 
      datareader = csv.reader(csvfile)
      datareader.__next__() # skip the first row of CSV file, [ID,podName,epNum,date,duration]
      count = 0
      for row in datareader:
        # count += 1
        # if count > 10:
        #   break
        flag = ifTranscriptionExists(row)
        if flag:
          print("Exists: %s" % row)
          transcriptionLog = pd.concat([transcriptionLog, pd.DataFrame([{'ID': row[0], 'Status': "Transcription exists", 'Podcast': row[1], 'Episode': row[2]}])], ignore_index=True)
        else:
          errorLog = pd.concat([errorLog, pd.DataFrame([{'ID': row[0], 'ErrorType': "Transcripts Not Found", 'Podcast': row[1], 'Episode': row[2]}])], ignore_index=True)
          print("NO: %s" % row)
    
    saveCSV(errorLog, 'errorLog_checktranscripts.csv')
    saveCSV(transcriptionLog, 'check_transcripts_log.csv')

if __name__ == "__main__":
  main()
