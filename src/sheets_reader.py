import os.path
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']


def get_sheet_id(url):
    prefix = 'docs.google.com/spreadsheets/'
    index = url.find(prefix) + len(prefix)
    url = url[index:]
    if 'd/' in url:
        index = url.find('d/')
        url = url[index + len('d/'):]
    index = url.find('/')
    return url[:index]


def append_sheet(spreadsheet_id, page_name, data):
    get_service_sheets().append(spreadsheetId=spreadsheet_id, range=page_name, valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS',
                                body={"values": [list(data)]}).execute()


def read_sheet(spreadsheet_id, page_name):
    service = get_service_sheets()
    return service.get(spreadsheetId=spreadsheet_id, range=page_name).execute().get('values', [])


def update_sheet(spreadsheet_id, page_name, data, lazy=False):
    get_service_sheets().update(spreadsheetId=spreadsheet_id, range=page_name, valueInputOption='USER_ENTERED',
                                body={"values": [[data]]}).execute()
    if not lazy:
        value = read_sheet(spreadsheet_id, page_name)
        if value[0][0] == str(data):
            return True
        else:
            return False


def get_creds():
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
    return creds


def get_service_drive():
    return build('drive', 'v3', credentials=get_creds()).files()


def get_service_permissions():
    return build('drive', 'v3', credentials=get_creds()).permissions()


def get_service_sheets():
    service = build('sheets', 'v4', credentials=get_creds()).spreadsheets().values()
    return service


def copy_ump_sheet(file_id, title):
    service = get_service_drive()
    body = {"name": title, 'ignoreDefaultVisibility': True}
    sheet_id = service.copy(fileId=file_id, body=body).execute()['id']
    permission_body = {'type': 'anyone', 'role': 'writer'}
    get_service_permissions().create(fileId=sheet_id, body=permission_body).execute()
    return sheet_id


def rename_sheet(file_id, title):
    body = {"name": title}
    return get_service_drive().update(fileId=file_id, body=body).execute()


def get_last_modified(file_id):
    service = get_service_drive()
    fields = service.get(fileId=file_id, fields='modifiedTime').execute()
    return fields['modifiedTime']