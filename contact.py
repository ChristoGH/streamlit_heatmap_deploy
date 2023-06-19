import io
import pickle
from googleapiclient.http import MediaIoBaseDownload
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive'
]
# Use Streamlit secrets for service account key
service_account_key = st.secrets["road_graphs"]
credentials = Credentials.from_service_account_info(service_account_key, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)

def download_and_load_pickle(service, file_name):
    # Search for the file by name
    query = f"name='{file_name}'"
    results = service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
    items = results.get('files', [])

    # Check if the file is found
    if not items:
        print(f"The file '{file_name}' was not found.")
        return None

    # Get the file ID of the first matching file
    file_id = items[0]['id']

    # Download the file to memory
    request = service.files().get_media(fileId=file_id)
    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    # Load the pickle data from the memory buffer
    file_buffer.seek(0)
    road_graphs = pickle.load(file_buffer)
    return road_graphs


# Usage example:
# Assuming `service` is your Google Drive API service client
file_name = 'SA_roads.p'  # Name of the file you want to download from Google Drive
road_graphs = download_and_load_pickle(service, file_name)
