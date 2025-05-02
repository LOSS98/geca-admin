
import os
from datetime import timedelta, datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from models.user import User
from models.role import Role
from services.google_api import GoogleAPIConnector
from config import Config

from db import db

auth_bp = Blueprint('auth', __name__)


def is_credentials_valid(credentials):
    try:

        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
        if not all(field in credentials for field in required_fields):
            print("Champs manquants dans les credentials:", credentials.keys())
            return False

        creds = Credentials(**credentials)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())

                    session['credentials'] = credentials_to_dict(creds)
                except Exception as e:
                    print(f"Erreur lors du rafraîchissement du token: {e}")
                    return False
            else:
                return False


        service = googleapiclient.discovery.build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info['email']
        from models.user import User
        user = User.get_by_email(user_email)
        if user.is_blocked():
            print(f"Utilisateur bloqué: {user_email}")
            return False
        now = datetime.now()
        user.last_connection = now
        return True
    except Exception as e:
        print(f"Erreur de validation des credentials: {e}")
        return False


def is_not_connected():
    return 'credentials' not in session or not is_credentials_valid(session['credentials'])


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            Config.CREDENTIALS_PATH, scopes=Config.GOOGLE_SCOPES)
        flow.redirect_uri = url_for('auth.callback', _external=True)

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        session['state'] = state
        return redirect(authorization_url)
    return render_template('login.html')


@auth_bp.route('/callback')
def callback():
    state = session.get('state')
    if not state:
        flash("Session expired. Please try logging in again.")
        return redirect(url_for('auth.login'))

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        Config.CREDENTIALS_PATH, scopes=Config.GOOGLE_SCOPES, state=state)
    flow.redirect_uri = url_for('auth.callback', _external=True)

    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)


    session.permanent = True

    session.permanent_session_lifetime = timedelta(hours=2)

    connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
    connector.authenticate(session['credentials'])

    user_info = connector.get_user_info()
    if not user_info:
        flash("Unable to get user information. Please try again.")
        return redirect(url_for('auth.login'))

    allowed_people = User.get_all_emails()
    if user_info['email'] not in allowed_people:
        flash(f"Access Denied: The email {user_info['email']} is not allowed.")
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        flash("Your email is not registered in the system.")
        return redirect(url_for('auth.login'))

    try:
        from models.user import user_roles
        role_names = db.session.query(Role.name) \
            .join(user_roles) \
            .filter(user_roles.c.user_email == user.email) \
            .all()

        roles = [role[0] for role in role_names]
    except Exception as e:
        print(f"Error fetching roles: {e}")
        roles = ["member"]

    session['user_info'] = user_info
    session['role'] = roles

    flash(f"Welcome {user_info['email']}! You are logged in.")
    return redirect(url_for('tasks.index'))


@auth_bp.route('/disconnect')
def disconnect():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/check-session')
def check_session():
    """Route pour vérifier la validité de la session côté client"""
    if is_not_connected():
        return jsonify({'valid': False}), 401
    return jsonify({'valid': True})