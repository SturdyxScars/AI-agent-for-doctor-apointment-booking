from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os

def create_service(client_secret, api_name, service_name):
    CLIENT_SECRET = client_secret
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = None
    API_NAME = api_name
    cur_dir = os.getcwd()
    token_dir = "token_files"
    token_file = f"{token_dir}_{API_NAME}.json"
    if not os.path.exists(os.path.join(cur_dir, token_dir)):
        os.mkdir(os.path.join(cur_dir, token_dir))
    if os.path.exists(os.path.join(cur_dir, token_dir, token_file)):
        creds = Credentials.from_authorized_user_file(os.path.join(cur_dir, token_dir, token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(os.path.join(cur_dir, token_dir, token_file), 'w') as token:
            token.write(creds.to_json())
    try:
        service = build(service_name, 'v3', credentials=creds)
        print(service_name, "successfully created")
        return service
    except Exception as e:
        print(e)
        print("Failed to create the service")
        os.remove(os.path.join(cur_dir, token_dir, token_file))
        return None