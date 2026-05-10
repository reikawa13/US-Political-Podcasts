"""
This script can be used for pulling data from the CSV file downloaded from the Brookings data. 
"""
import pandas as pd 
from pandas import *
import numpy as np 

# run pip install feedparser
''' https://pythonhosted.org/feedparser/ '''
import feedparser 

# Used for downloading mp3 files
import sys
import urllib.request
import requests

# for making directories for podcasts
import os

# used to move files into directory
import shutil

"""
For each audio link we get:
    download the data 
"""

def main():
    podname = "Pod-Save-the-World"

    dirpath = os.path.join("/local/Audio-Files-Nov5-2", podname)
    # data = read_csv("Human_Events_Daily_with_Jack_Posobiec.csv")
    data = read_csv("Pod-Save-America_-April422.csv")
    print(data.columns)
    audioList = data["Audio URL"].tolist()
    dateList = data["Full Date"].tolist()

    df = pd.DataFrame(columns = ['ID', 'podName', 'epNum', 'date', 'duration'])
    errorLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'])

    #count = len(audioList)
    count = 274
    print("There are %d episodes" % count)

    for url, date in zip(audioList, dateList):
        epNum = count
        filename = "pod_" + podname + "_" + str(epNum) + ".mp3"
        path = os.path.join(dirpath, filename)
        
        if not os.path.exists(path):
            try:
                r = requests.get(url)
            except:
                errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error saving mp3 file", 'Podcast': podname, 'Episode': epNum}, ignore_index = True)
            
            with open(path, 'wb') as f:
                f.write(r.content)
                print(os.path.join(path, filename))
        
        ID = podname + "_" + str(epNum)
        df = df._append({'ID' : ID, 'podName' : podname, 'epNum' : epNum, 'date' : date, 'duration' : "?"}, ignore_index = True)
        
        count -= 1
        # if len(audioList) - count > 5:
        #     break
    
    df.to_csv("podMetadata_Nov5_2.csv", index = False)
    errorLog.to_csv("errorLog_Nov5_2.csv", index = False)

    return
    

    print("Beginning Data Extraction")
    print(rssList)

    for url in rssList: 
        try:
            # URL_count += 1
            df, errorLog = extractData(url, df, errorLog)
            # if URL_count == 3:
            #     break
        except:
            errorLog._append({'ID': "EXCEPTION", 'ErrorType': "RSS FEED BROKEN", 'Podcast': "UNKNOWN", 'Episode': "N/A"}, ignore_index = True)
    
    ## Save the CSV-file logs
    print("Data Extraction Completed")
    saveCSV(df, 'podMetadata.csv')
    saveCSV(errorLog, 'errorLog.csv')
    print("Saved CSV Files")

def extractData(URL, df, errorLog):
    pod = feedparser.parse(URL)
    currentPod = ""

    ## if new podcast, create a new directory in Audio-Files and Transcripts
    podName = pod.channel.title

    if " " in podName:
        podName = podName.replace(' ', '-') 
    if (podName.startswith('"') and podName.endswith('"')) or (podName.startswith("'") and podName.endswith("'")):
        podName = podName[1:-1]
    
    print("Processing " + podName)

    episodesParsed= 0

    ## Loop through each podcast episode 
    count = len(pod.entries)
    for item in pod.entries:       
        epNum = count

        ## Find the publishing date
        try:
            date = item["published"]
            yearIn = date.find("202")
            if yearIn == -1:
                yearIn = date.find("201")
            if yearIn == -1:
                errorLog._append({'ID': ErrorCount, 'ErrorType': "Date out of Scope", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
                break
            ## only find episode after 2016
            if int(date[yearIn:yearIn+4]) < 2016:
                break
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Date", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        ## Finding the duration
        try:
            duration = item["itunes_duration"]
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Duration", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        ID = podName + "_" + str(epNum)

        ## Creating the directory to store the .mp3s and transcriptions of the series 
        if currentPod != podName:
            currentPod = podName
            try:
                MakeDirectories(currentPod)
            except:
                print("Directory Exists")
        
        ## Finding the URL to audio data 
        try:
            links = item.links # get any links from the RSS feed 
            for link in links: # for each link within the data for an episode, find audio data
                if link.type == u'audio/mpeg':  
                    audioURL = (link.href)
                    break
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error finding mp3 file", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)

        ## Save the audio data 
        try:
            recordMP3(podName, epNum, date, audioURL)
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error saving mp3 file", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        

        df = df._append({'ID' : ID, 'podName' : podName, 'epNum' : epNum, 'date' : date, 'duration' : duration}, ignore_index = True)

        count -= 1

        episodesParsed += 1
    
    return df, errorLog

def MakeDirectories(name):

    # Audio-Files in /local
    grandparent_dir = "/local"
    parent_dir = "Audio-Files"
    parentPath = os.path.join(grandparent_dir, parent_dir)
    path = os.path.join(parentPath,name)
    os.mkdir(path)
    # print("Made a directory %s" % path)
    
    # Transcripts in /podcast-hatespeech
    # grandparent_dir = os.path.join(os.getcwd(), '..')
    # parent_dir = "Transcripts"
    # parentPath = os.path.join(grandparent_dir, parent_dir)
    # path = os.path.join(parentPath,name)
    # os.mkdir(path)

def recordMP3(name, epNum, date, url):
    #Save mp3 file in folder as pod_[Podcast Name]_[Episode Number].mp3
    file_name = "pod_" + name + "_" + str(epNum) + ".mp3"

    # Get path to save it in the correct directory
    # grandparent_dir = os.path.join(os.getcwd(), '..')
    grandparent_dir = "/local"
    parent_dir = "Audio-Files"
    parentPath = os.path.join(grandparent_dir, parent_dir)
    path = os.path.join(parentPath, name)

    r = requests.get(url)

    with open(os.path.join(path, file_name), 'wb') as f:
        f.write(r.content)
        print(os.path.join(path, file_name))

def saveCSV(df, file_name):
    df.to_csv(file_name, index = False)

if __name__ == '__main__':
    main()