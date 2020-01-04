import httplib2
import os
import sys

import google.oauth2.credentials

from apiclient.discovery import build_from_document
from apiclient.errors import HttpError
from googleapiclient import channel
import argparse
import json

argparser = argparse.ArgumentParser(description='This is a PyMOTW sample program')
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains

# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = "service_yt.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
YOUTUBE_READ_WRITE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:
   %s
with information from the APIs Console
https://console.developers.google.com

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))


def get_authenticated_service(_self):
    SCOPES = ['https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/youtube.upload',
              'https://www.googleapis.com/auth/youtube.force-ssl']
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)

    credentials = Credentials.from_authorized_user_file(CLIENT_SECRETS_FILE, SCOPES)

    # #if credentials is None:
    # credentials = flow.run_console()
    #
    # print "Refresh %s \n Client %s\n" % (credentials.refresh_token, credentials.token)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)


def list_captions(youtube, video_id):
    results = youtube.captions().list(
        part="snippet",
        videoId=video_id
    ).execute()

    for item in results["items"]:
        id = item["id"]
        name = item["snippet"]["name"]
        language = item["snippet"]["language"]
        print "Caption track '%s(%s)' in '%s' language." % (name, id, language)

    return results["items"]


# Call the API's captions.insert method to upload a caption track in draft status.
def upload_caption(youtube, video_id, language):
    from googleapiclient.http import MediaFileUpload

    file = "captions_%s.sbv" % language

    insert_result = youtube.captions().insert(
        part="snippet",
        body=dict(
            snippet=dict(
                videoId=video_id,
                language=language,
                name="",
            )
        ),
        media_body=MediaFileUpload(file)
    ).execute()

    print (insert_result)

# Call the API's captions.update method to update an existing caption track's draft status
# and publish it. If a new binary file is present, update the track with the file as well.
def update_caption(youtube, caption_id, file):
    update_result = youtube.captions().update(
        part="snippet",
        body=dict(
            id=caption_id,
            snippet=dict(
                isDraft=False
            )
        ),
        media_body=file
    ).execute()

    name = update_result["snippet"]["name"]
    isDraft = update_result["snippet"]["isDraft"]
    print "Updated caption track '%s' draft status to be: '%s'" % (name, isDraft)
    if file:
        print "and updated the track with the new uploaded file."


# Call the API's captions.download method to download an existing caption track.
def download_caption(youtube, caption_id, tfmt):
    subtitle = youtube.captions().download(
        id=caption_id,
        tfmt=tfmt
    ).execute()

    print "First line of caption track: %s" % (subtitle)


# Call the API's captions.delete method to delete an existing caption track.
def delete_caption(youtube, caption_id):
    youtube.captions().delete(
        id=caption_id
    ).execute()

    print "caption track '%s' deleted succesfully" % (caption_id)


def set_video_localization(youtube, args):
    # Retrieve the snippet and localizations for the video.
    results = youtube.videos().list(
        part='snippet,localizations',
        id=args.videoid
    ).execute()

    video = results['items'][0]

    target_data = translate_meta(args)

    # If the language argument is set, set the localized title and description
    # for that language. The "title" and "description" arguments have default
    # values to make the script simpler to run as a demo. In an actual app, you
    # would likely want to set those arguments also.
    if args.language and args.language != '':
        if 'localizations' not in video:
            video['localizations'] = {}

        video['localizations'][args.language] = {
            'title': target_data["title"],
            'description': target_data["description"]
        }

    video['snippet']['defaultLanguage'] = 'si'

    # Update the video resource.
    update_result = youtube.videos().update(
        part='snippet,localizations',
        body=video
    ).execute()

    print update_result


def translate_meta(args):
    with open('desc.json', 'r') as f:
        target_data = json.load(f)

    input_list = [target_data["title"], target_data["description"]]

    translated_object = translate(input_list, args.language)

    title = translated_object.translations[0].translated_text
    description = translated_object.translations[1].translated_text

    return {"title": title, "description": description}


def translate(source, target_language_code):
    from google.cloud import translate_v3
    client = translate_v3.TranslationServiceClient()
    parent = client.location_path('pituwatv-263900', 'global')

    print("set target language code to %s" % target_language_code)

    return client.translate_text(source, target_language_code, parent)


def translate_caption(args):
    import re
    import time

    timestamp_pattern = re.compile("^[0-9]+:[0-9]+:[0-9]+.[0-9]+,[0-9]+:[0-9]+:[0-9]+.[0-9]+$")
    empty_line_pattern = re.compile("^$")
    text = ""
    source = []
    destination = []
    timestamp = ""

    print("reading source file")
    with open(args.source_file, 'r') as openfileobject:
        for head in openfileobject:
            head = head.replace("\n", "")
            if re.match(empty_line_pattern, head):
                slot = {"timestamp": timestamp, "text": text}
                source.append(slot)
                text = ""
            if re.match(timestamp_pattern, head):
                timestamp = head
            else:
                text += head

    print("source file read with %d records" % len(source))

    print("source: initializing list")

    input_list = []
    for slot in source:
        input_list.append(slot['text'])

    print("source: %d captions" % len(input_list))

    print("output: initializing list")
    output_list = []

    target_language_code = args.language

    print("translation: sending to google")
    t0 = time.time()
    translated_object = translate(input_list, target_language_code)
    t1 = time.time()
    print("translation: response received time elapsed [%f] " % (t1 - t0))

    print("output: populating list")
    for translation in translated_object.translations:
        output_list.append(translation.translated_text)
    i = 0

    print("output: combining translation with timestamps")
    for slot in source:
        hindi_slot = {"timestamp": slot["timestamp"], "text": output_list[i]}
        destination.append(hindi_slot)
        i += 1

    print("writing to output file captions_%s.sbv" % target_language_code)
    with open('captions_%s.sbv' % target_language_code, 'w') as openfileobject:
        for record in destination:
            openfileobject.write(record["timestamp"] + '\n')
            openfileobject.write(record["text"].encode('utf8') + '\n')
            openfileobject.write("" + '\n')


if __name__ == "__main__":
    # The "videoid" option specifies the YouTube video ID that uniquely
    # identifies the video for which the caption track will be uploaded.
    argparser.add_argument("--videoid",
                           help="Required; ID for video for which the caption track will be uploaded.")
    # The "name" option specifies the name of the caption trackto be used.
    argparser.add_argument("--name", help="Caption track name", default="YouTube for Developers")
    # The "file" option specifies the binary file to be uploaded as a caption track.
    argparser.add_argument("--file", help="Captions track file to upload")
    # The "language" option specifies the language of the caption track to be uploaded.
    argparser.add_argument("--language", help="Caption track language", default="en")
    # The "captionid" option specifies the ID of the caption track to be processed.
    argparser.add_argument("--captionid", help="Required; ID of the caption track to be processed")
    # The "action" option specifies the action to be processed.
    argparser.add_argument("--action", help="Action", default="all")
    argparser.add_argument("--title", help="i18n title for destination language")
    argparser.add_argument("--description", help="i18n description for destination language")
    argparser.add_argument("--source_file", help="source sbv file used to translate")

    args = argparser.parse_args()

    if (args.action in ('upload', 'list', 'all')):
        if not args.videoid:
            exit("Please specify videoid using the --videoid= parameter.")

    if (args.action in ('update', 'download', 'delete')):
        if not args.captionid:
            exit("Please specify captionid using the --captionid= parameter.")

    youtube = get_authenticated_service(args)

    try:
        if args.action == 'upload':
            translate_caption(args)
            upload_caption(youtube, args.videoid, args.language)
            set_video_localization(youtube, args)
            #update_caption(youtube, args.videoid, args.language)
        elif args.action == 'list':
            list_captions(youtube, args.videoid)
        elif args.action == 'update':
            update_caption(youtube, args.captionid, args.file);
        elif args.action == 'download':
            download_caption(youtube, args.captionid, 'srt')
        elif args.action == 'delete':
            delete_caption(youtube, args.captionid);
    except HttpError, e:
        print "An HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
    else:
        print "Created and managed caption tracks."
