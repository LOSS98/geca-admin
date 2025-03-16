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
                                        'postgresql://khalil:Kh4lil9870720406*@51.38.83.204:1125/postgres_geca_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False