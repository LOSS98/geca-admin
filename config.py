# config.py
import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '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')

    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_FILE_DIR = os.getenv('SESSION_FILE_DIR', './flask_session')

    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/script.external_request',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'openid'
    ]
    CREDENTIALS_PATH = './credentials.json'

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL',
                                        f'postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PWD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_port')}/{os.getenv('DB_NAME')}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False