import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os


class GoogleAPIConnector:
    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/script.external_request',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid'
        ]
        self.credentials = None
        self.service_script = None
        self.service_oauth2 = None
        self.script_id = os.getenv('GENERAL_SCRIPT_ID')

    def authenticate(self, session_credentials):
        self.credentials = Credentials(**session_credentials)

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes)
                self.credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent')

        self.service_script = googleapiclient.discovery.build('script', 'v1', credentials=self.credentials)
        self.service_oauth2 = googleapiclient.discovery.build('oauth2', 'v2', credentials=self.credentials)
        print("Authentication successful")

    def run_script(self, script_id: str, function_name: str, parameters: list):
        request = {
            "function": function_name,
            "parameters": parameters
        }
        try:
            response = self.service_script.scripts().run(
                body=request,
                scriptId=script_id
            ).execute()

            if 'error' in response:
                print("Erreur lors de l'exécution du script: {}".format(response['error']['details']))
                return None
            else:
                return response['response'].get('result')
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def get_members(self) -> list:
        try:
            members = self.run_script(self.script_id, 'getMembers', [])
            if members is None:
                print('No data found.')
                return []
            else:
                return members
        except Exception as e:
            print(f"An error occurred while fetching members: {e}")
            return []

    def get_user_info(self):
        try:
            user_info = self.service_oauth2.userinfo().get().execute()
            return user_info
        except Exception as e:
            print(f"An error occurred while fetching user info: {e}")
            return None

    def create_spreadsheet(self, title: str) -> str:
        try:
            sheets_service = googleapiclient.discovery.build('sheets', 'v4', credentials=self.credentials)

            spreadsheet = {
                'properties': {
                    'title': title
                }
            }

            result = sheets_service.spreadsheets().create(body=spreadsheet).execute()

            return result.get('spreadsheetId')
        except Exception as e:
            print(f"Error creating spreadsheet: {e}")
            return None

    def append_data_to_sheet(self, spreadsheet_id: str, range_name: str, values: list):
        try:
            sheets_service = googleapiclient.discovery.build('sheets', 'v4', credentials=self.credentials)

            body = {
                'values': values
            }

            result = sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return result
        except Exception as e:
            print(f"Error appending data to sheet: {e}")
            return None

    def share_spreadsheet(self, spreadsheet_id: str, email: str, role: str = 'reader'):
        try:
            drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=self.credentials)

            user_permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }

            result = drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=user_permission,
                fields='id'
            ).execute()

            return result
        except Exception as e:
            print(f"Error sharing spreadsheet: {e}")
            return None

    def test_connection(self):
        """Test de connexion aux API Google pour vérifier la validité des credentials"""
        try:
            # Tester l'API OAuth2 (la plus légère)
            user_info = self.service_oauth2.userinfo().get().execute()

            # Tester l'API Sheets si possible
            if os.getenv('SHEET_ID'):
                sheets_service = googleapiclient.discovery.build('sheets', 'v4', credentials=self.credentials)
                sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=os.getenv('SHEET_ID')).execute()

            return True
        except Exception as e:
            print(f"Erreur lors du test de connexion: {e}")
            return False