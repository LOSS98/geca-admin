from http.client import responses
import os
import json
from urllib.parse import urlparse, parse_qs
import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from flask import session


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
        self.K3_cell_value = os.getenv('K3_CELL_VALUE')

        self.is_dev = os.getenv('DEVELOP') == '1'
        if self.is_dev:
            self.redirect_uri = "http://127.0.0.1:5000/callback"
        else:
            self.redirect_uri = "https://www.assos-geca.fr/callback"

    def get_auth_url(self):
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true'
        )

        return authorization_url, state

    def process_callback(self, authorization_response, state=None):
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                self.credentials_path,
                scopes=self.scopes,
                state=state
            )
            flow.redirect_uri = self.redirect_uri

            flow.fetch_token(authorization_response=authorization_response)
            self.credentials = flow.credentials

            self.service_script = googleapiclient.discovery.build('script', 'v1', credentials=self.credentials)
            self.service_oauth2 = googleapiclient.discovery.build('oauth2', 'v2', credentials=self.credentials)

            print("Authentication successful")
            return True, self.credentials_to_dict()
        except Exception as e:
            print(f"Error processing OAuth callback: {e}")
            return False, str(e)

    def authenticate(self, session_credentials=None):
        try:
            if session_credentials:
                self.credentials = Credentials(**session_credentials)

                if not self.credentials or not self.credentials.valid:
                    if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                        self.credentials.refresh(Request())
                    else:
                        return None

                self.service_script = googleapiclient.discovery.build('script', 'v1', credentials=self.credentials)
                self.service_oauth2 = googleapiclient.discovery.build('oauth2', 'v2', credentials=self.credentials)
                print("Authentication successful using existing credentials")
                return True
            else:
                return None
        except Exception as e:
            print(f"Error during authentication: {e}")
            return False

    def credentials_to_dict(self):
        if not self.credentials:
            return None

        return {
            'token': self.credentials.token,
            'refresh_token': self.credentials.refresh_token,
            'token_uri': self.credentials.token_uri,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
            'scopes': self.credentials.scopes
        }

    def run_script(self, script_id: str, function_name: str, parameters: list):
        request = {
            "function": function_name,
            "parameters": parameters
        }
        try:
            if self.K3_cell_value:
                remoteK3 = self.service_script.scripts().run(
                    body={
                        "function": "getCellK3Value",
                        "parameters": []
                    },
                    scriptId=self.script_id
                ).execute()['response'].get('result')
                print(f"remoteK3: {remoteK3}")
                if remoteK3 != self.K3_cell_value:
                    print("K3 cell value does not match the expected value.")
                    raise Exception("Transaction non ajoutée ! Reconnection nécessaire.")

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
            print(f"Error executing script: {e}")
            return 'error'

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
        try:
            user_info = self.service_oauth2.userinfo().get().execute()

            if os.getenv('SHEET_ID'):
                sheets_service = googleapiclient.discovery.build('sheets', 'v4', credentials=self.credentials)
                sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=os.getenv('SHEET_ID')).execute()

            return True
        except Exception as e:
            print(f"Erreur lors du test de connexion: {e}")
            return False