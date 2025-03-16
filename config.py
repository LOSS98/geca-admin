import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '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')
    SESSION_TYPE = 'filesystem'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL',
                                        'postgresql://khalil:Kh4lil9870720406*@51.38.83.204:1125/postgres_geca_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', './credentials.json')

    GECA_FINANCE_NAME = 'GECA'
    # Google API scopes
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/script.external_request',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email',
        'openid'
    ]