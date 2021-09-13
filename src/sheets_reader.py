import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_sheet_id(url):
    prefix = 'docs.google.com/spreadsheets/'
    index = url.find(prefix) + len(prefix)
    url = url[index:]
    if 'd/' in url:
        index = url.find('d/')
        url = url[index + len('d/'):]
    index = url.find('/')
    return url[:index]


def read_sheet(spreadsheet_id, page_name):
    return get_service().get(spreadsheetId=spreadsheet_id, range=page_name).execute().get('values', [])


def update_sheet(spreadsheet_id, page_name, data, lazy=False):
    get_service().update(spreadsheetId=spreadsheet_id, range=page_name, valueInputOption='USER_ENTERED',
                         body={"values": [[data]]}).execute()
    if not lazy:
        value = read_sheet(spreadsheet_id, page_name)
        if value[0][0] == str(data):
            return True
        else:
            return False


def get_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('sheets', 'v4', credentials=creds).spreadsheets().values()
