import io
import pickle
from googleapiclient.http import MediaIoBaseDownload
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import streamlit_authenticator as stauth
def attrdict_to_dict(attrdict):
    dict_ = {}
    for key, value in attrdict.items():
        if isinstance(value, attrdict.__class__):
            dict_[key] = attrdict_to_dict(value)
        else:
            dict_[key] = value
    return dict_
# Step 1: Set up authentication


import yaml
from yaml.loader import SafeLoader
with open('config.yaml') as file:
    yml_config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    yml_config['credentials'],
    yml_config['cookie']['name'],
    yml_config['cookie']['key'],
    yml_config['cookie']['expiry_days'],
    yml_config['preauthorized']
)

toml_config = st.secrets["auth"]
toml_config_dict = attrdict_to_dict(toml_config)
authenticator = stauth.Authenticate(
    toml_config_dict['credentials'],
    toml_config_dict['cookie']['name'],
    toml_config_dict['cookie']['key'],
    toml_config_dict['cookie']['expiry_days'],
    toml_config_dict['preauthorized']
)
name, authentication_status, username = authenticator.login('Login', 'main')
import copy

toml_config = copy.deepcopy(st.secrets.auth)
authenticator = stauth.Authenticate(
    toml_config.credentials,
    toml_config.cookie.name,
    toml_config.cookie.key,
    toml_config.cookie.expiry_days,
    toml_config.preauthorized
)

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

def convert_conda_to_pip_syntax(input_file, output_file):
    with open(input_file, "r") as file:
        lines = file.readlines()

    with open(output_file, "w") as file:
        for line in lines:
            if "=" in line:
                package = line.replace("=", "==", 1)
                file.write(package)

convert_conda_to_pip_syntax("conda-requirements.txt", "converted-conda-requirements.txt")
def clean_conda_requirements(input_file, output_file):
    with open(input_file, "r") as file:
        lines = file.readlines()

    with open(output_file, "w") as file:
        for line in lines:
            if "=" in line:
                # Skip the 'python' entry
                if line.lower().startswith("python="):
                    continue
                # Keep only package name and version
                package = line.split("=")[0:2]
                # Rejoin package name and version
                cleaned_line = "=".join(package)
                # Remove any suffix like '=pypi_0'
                cleaned_line = cleaned_line.split("_")[0]
                # Write to file only if it has both package name and version
                if cleaned_line.count('=') == 1 and cleaned_line.endswith('='):
                    continue
                file.write(cleaned_line + "\n")

clean_conda_requirements("converted-conda-requirements.txt", "cleaned-converted-conda-requirements.txt")


