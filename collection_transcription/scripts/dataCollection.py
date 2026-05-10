"""
This script can be used for downloading audio data from RSS feeds.
"""

# To activate virtual environment
# $ source /usr/local/bin/virtualenvwrapper.sh
# $ workon podcast-hate-speech

#!/usr/bin/env python
## IMPORTS
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

from bs4 import BeautifulSoup

def main():
    ## Get a list of urls to the RSS feeds of top100 podcasts
    # data = read_csv("Top_100_Podcasts(11_05_2024).csv")
    # rssList = data["RSS Feed"].tolist()
    rssList = ["https://feeds.megaphone.fm/DISPME9513417677"]

    ## Initialize the csv-file logs 
    df = pd.DataFrame(columns = ['ID', 'podName','epNum', 'date', 'duration', 'title', 'guid', 'desription', 'keywords', 'audioURL'])
    errorLog = pd.DataFrame(columns = ['ID', 'ErrorType', 'Podcast', 'Episode'])

    ## Putting RSS Feeds into Data Frame
    print("Beginning Data Extraction")

    URL_count = 0
    # Call extractData() on each URL to RSS feed
    for url in rssList: 
        try:
            URL_count += 1
            df, errorLog = extractData(url, df, errorLog)
            # if URL_count == 3:
                # break
        except:
            errorLog._append({'ID': "EXCEPTION", 'ErrorType': "RSS FEED BROKEN", 'Podcast': "UNKNOWN", 'Episode': "N/A"}, ignore_index = True)

    ## Save the CSV-file logs
    print("Data Extraction Completed")
    saveCSV(df, 'podMetadata_Nov5_The-Dispatch.csv')
    saveCSV(errorLog, 'errorLog_Collection_Nov5_The-Dispatch.csv')
    print("Saved CSV Files")



def extractData(URL, df, errorLog):
    ErrorCount = 0

    ## Initializing podcast series object 
    pod = feedparser.parse(URL)
    currentPod = ""

    ## if new podcast, create a new directory in Audio-Files and Transcripts
    podName = pod.channel.title
    
    if " " in podName:
        podName = podName.replace(' ', '-') 
    if (podName.startswith('"') and podName.endswith('"')) or (podName.startswith("'") and podName.endswith("'")):
        podName = podName[1:-1]
    if podName == "Fox-Across-America-w/-Jimmy-Failla":
        podName = "Fox-Across-America-with-Jimmy-Failla"
    
    print("Processing " + podName)
    
    episodesParsed= 0

    num = 0
    ## Loop through each podcast episode 
    count = len(pod.entries)
    # count = 1229
    for item in pod.entries:       
        epNum = count
        # if epNum >485:
        #     print("skipping")
        #     continue
        # elif count < 485:
        #     break

        num += 1
        if num > 8:
            break

        ## Find the publishing date
        try:
            date = item["published"]
            print(date)
            yearIn = date.find("202")
            if yearIn == -1:
                yearIn = date.find("201")
            if yearIn == -1:
                errorLog._append({'ID': ErrorCount, 'ErrorType': "Date out of Scope", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
                break
            ## only find episode after 2016
            if int(date[yearIn:yearIn+4]) < 2016:
                break

            ## USED WHEN YOU WANT A FILE ON A SPECIFIC DATE
            # if date not in ["Sun, 04 Aug 2019 09:00:00 +0000"]:
            #     count -= 1
            #     continue
            # else:
            #     print("FOUND: ", date)
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Date", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        ## Finding the duration
        try:
            duration = item["itunes_duration"]
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Duration", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        ID = podName + "_" + str(epNum)
        
        ## Finding the title
        try:
            epTitle = item["title"]
            # print(epTitle)
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Title", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        ## Finding the guid
        try:
            guid = item.get("guid") or item.get("id")
            # print("giud: ", guid)
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding GUID", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        ## Finding the description 
        try:
            description = item.get("description") 

            # Use BeautifulSoup to strip HTML tags
            soup = BeautifulSoup(description, "html.parser")
            description = soup.get_text()  # Extracts text only, removes HTML tags
            
            description = description.replace("\n", " ").replace("\r", " ").strip()
            # print(description)
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error Finding Description", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        ## Creating the directory to store the .mp3s and transcriptions of the series 
        if currentPod != podName:
            currentPod = podName
            try:
                MakeDirectories(currentPod)
            except:
                print("Directory Exists")
        
        ## Finding the URL to audio data
        ## CAUTION: We are pulling any audio URLs in the entry -> if the entry contained multiple audio URLs, we might've been getting a wrong URL
        try:
            links = item.links # get any links from the RSS feed 
            for link in links: # for each link within the data for an episode, find audio data
                if link.type == u'audio/mpeg':  
                    audioURL = (link.href)
                    break
        except:
            errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error finding mp3 file", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)

        keywords = item.get("itunes_keywords", "Not Available")
        # print(keywords)
        
        ## Save the audio data 
        try:
            print("before recordMP3")
            recordMP3(podName, epNum, date, audioURL)
        except:
           errorLog = errorLog._append({'ID': ErrorCount, 'ErrorType': "Error saving mp3 file", 'Podcast': podName, 'Episode': epNum}, ignore_index = True)
        
        df = df._append({'ID' : ID, 'podName' : podName, 'epNum' : epNum, 'date' : date, 'duration' : duration, "title" : epTitle, "guid": guid, "description": description, "keywords": keywords, "audioURL": audioURL}, ignore_index = True)

        count -= 1

        episodesParsed += 1
        
    return df, errorLog

def MakeDirectories(name):

    # Audio-Files in /local
    grandparent_dir = "/local"
    parent_dir = "Audio-Files-Nov5-2"
    parentPath = os.path.join(grandparent_dir, parent_dir)
    path = os.path.join(parentPath,name)
    os.mkdir(path)
    # print("Made a directory %s" % path)
    
    # Transcripts in /podcast-hatespeech
    grandparent_dir = os.path.join(os.getcwd(), '..')
    parent_dir = "Transcripts-Nov5"
    parentPath = os.path.join(grandparent_dir, parent_dir)
    path = os.path.join(parentPath,name)
    os.mkdir(path)

def recordMP3(name, epNum, date, url):
    #Save mp3 file in folder as pod_[Podcast Name]_[Episode Number].mp3
    file_name = "pod_" + name + "_" + str(epNum) + ".mp3"

    # Get path to save it in the correct directory
    # grandparent_dir = os.path.join(os.getcwd(), '..')
    grandparent_dir = "/local"
    parent_dir = "Audio-Files-Nov5-2"
    parentPath = os.path.join(grandparent_dir, parent_dir)
    path = os.path.join(parentPath, name)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    # r = requests.get(url)

    with open(os.path.join(path, file_name), 'wb') as f:
        f.write(r.content)
        print(os.path.join(path, file_name))
    

def saveCSV(df, file_name):
    df.to_csv(file_name, index = False)


if __name__ == '__main__':
    main()
