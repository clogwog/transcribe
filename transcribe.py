import sys
import json
import os

from urllib.request import urlretrieve
from pprint import pprint
from pathlib import Path

#for rss parsing
from xml.dom import minidom

import traceback
import time
import datetime


import xml.etree.cElementTree as ET


# Imports the Google Cloud client library (use beta for the advanced model for speech recognition)
import google.cloud.speech_v1p1beta1 as speech
from google.cloud import storage

# Instantiates a client
storage_client = storage.Client()

# constants
bucket_name = 'natranscript'
rssfeeduri = "http://feed.nashownotes.com/rss.xml"


#just some feedback while the files are downloading
def reporthook(blocknum, blocksize, totalsize):
	readsofar = blocknum * blocksize
	if totalsize > 0:
		percent = readsofar * 1e2 / totalsize
		s = "\r%5.1f%% %*d / %d" % ( percent, len(str(totalsize)), readsofar, totalsize)
		sys.stderr.write(s)
		if readsofar >= totalsize: # near the end
			sys.stderr.write("\n")
	else: # total size is unknown
		sys.stderr.write("read %d\n" % (readsofar,))

#save the transcript to an xml file. chose xml because we can transcode it to other outputs easily using xslt
def write_transcript_to_file(offset, showname , showuri, episodenumber, response, simpleFileName):
	timeOffset=offset*3600
	root = ET.Element("podcast")
	show = ET.SubElement(root, "show", episodenumber=episodenumber, title=showname, showlink=showuri )

	for result in response.results:
		alternative = result.alternatives[0]
		trcrpt = ET.SubElement(show, "transcription", confidence=str(alternative.confidence), rawtext=str(alternative.transcript))
		print(u'Transcript: {}'.format(alternative.transcript))
		print('Confidence: {}'.format(alternative.confidence))
		for word_info in alternative.words:
			word = str(word_info.word)
			start_time = word_info.start_time
			end_time = word_info.end_time
			
			fullseconds=int(timeOffset + start_time.seconds + start_time.nanos * 1e-9)

			ET.SubElement(trcrpt,"word", start_time=str(datetime.timedelta(seconds=fullseconds)).replace(":","-")).text = word

	tree = ET.ElementTree(root)
	tree.write(simpleFileName + "-raw-" + str(offset + 1) + ".xml")



#dynamically import the pydub module
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path + "/pydub")
from pydub import AudioSegment
from pydub.utils import make_chunks



#-------- download rss feed
urlretrieve(rssfeeduri, "rss.xml", reporthook)
xmldoc = minidom.parse('rss.xml')
itemlist = xmldoc.getElementsByTagName('item')
#------ save the enclosures
rssarray = []
counter = 1
for item in itemlist:
    rssarray.append( {"index": counter, "title": item.getElementsByTagName("title")[0].childNodes[0].data, "url" : item.getElementsByTagName("enclosure")[0].getAttribute('url'), "length": item.getElementsByTagName("enclosure")[0].getAttribute('length') })
    counter = counter + 1

# ------ show the available episodes and ask which one to parse
print("")
print("Available episodes: ")
print("")
for  show in rssarray:
	print( " %02d  - %s " % (show["index"], show["title"]) )

episodenumber = 1
while 1:
	print ("")
	episodenumber = input("Please select the episode number you would like to transcribe now [01]") or "1"

	if int(episodenumber) <= 0 or int(episodenumber) >= counter :
		askcontinue = input("invalid choice. do you want to retry ? (Y/N) [Y]" or "Y" )
		if ( askcontinue == 'n' or askcontinue == "N"):
			sys.exit()
	else:
		break

# determine episode number
url = rssarray[int(episodenumber) - 1]["url"]
selectedtitle = rssarray[int(episodenumber) - 1]["title"]
selectedepisodenumber = selectedtitle.split(':')[0]
#pprint( rssarray[int(episodenumber) - 1])
selectedepisodefilesize = int(rssarray[int(episodenumber) - 1]["length"])

#download each episode into its own download directory
downloaddir = dir_path + "/episodes/" + selectedepisodenumber
try:
	os.stat( downloaddir)
except:
	os.mkdir( downloaddir );

print( "selected: " + episodenumber + " now downloading\n\repisode: " + selectedepisodenumber + "\n\rurl    : " + url)

totalFileName = downloaddir + "/" + url.split('/')[-1]

skipDownload = False
# check if the file already exists
checkfile = Path(totalFileName)
if checkfile.is_file():
	checkfilesize = os.path.getsize(totalFileName)
	if checkfilesize == selectedepisodefilesize :
		skipDownload = True
		print( totalFileName + " is already fully downloaded.. skipping download")

if not skipDownload:
	urlretrieve(url, totalFileName, reporthook)



# spilt mp3 into 1 hour chunks
print("splitting mp3 in 1 hour chunks")
fullfile = AudioSegment.from_mp3(totalFileName)
fullfile = fullfile.set_channels(1)
totalLength = len(fullfile)
onehours = 3600000

numberoffullhours = int(totalLength / onehours)
remainder = totalLength % onehours

print("totalLength: " + str(int(totalLength/60000)) + " minutes")
print("numberoffullhours: " + str(numberoffullhours))
print("remainder: " + str(int(remainder/60000)) + " minutes")

simpleFileName = os.path.splitext(totalFileName)[0]


bucket = storage_client.get_bucket(bucket_name)
fullbucketuri = "gs://" + bucket_name + "/"

chunks = make_chunks(fullfile, onehours)

offset=0

for i, chunk in enumerate(chunks):
	chunk_name = simpleFileName + "-{0}.flac".format(i+1)
	filenameext=os.path.basename(chunk_name)
	print ("exporting " , chunk_name)
	chunk.export(chunk_name, format="flac")

	#upload chunk to bucket 
	print("uploading " + filenameext + " to bucket")
	blob = bucket.blob(filenameext)
	blob.upload_from_filename(chunk_name)


	#transcribe chunk
	gcs_uri=fullbucketuri + filenameext

	print("starting transcription for " + filenameext)
	client = speech.SpeechClient()
	audio = speech.types.RecognitionAudio(uri=gcs_uri)
	config = speech.types.RecognitionConfig(
		language_code='en-US',
		sample_rate_hertz=44100,
		use_enhanced=True,
        model='phone_call',
        enable_word_time_offsets=True,
		enable_automatic_punctuation=True)

	operation = client.long_running_recognize(config, audio)

	print('Waiting for operation to complete...')
	time.sleep(100)
	response = operation.result(timeout=3600)

	#write transcription for chunk to file
	
	write_transcript_to_file(i, selectedtitle , url, selectedepisodenumber, response, simpleFileName)






