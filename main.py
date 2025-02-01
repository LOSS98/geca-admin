from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_migrate import Migrate

from flask_session import Session
import os
from dotenv import load_dotenv
import betclic
import google.auth
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from classes.GoogleAPIConnector import GoogleAPIConnector
import classes.Expense, classes.Income, classes.AskMoney
import logging

from db import db
from entities.user import User
from entities.income import Income
from entities.expense import Expense

if True :
    logging.basicConfig(level=logging.DEBUG,
                         format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
                         handlers=[
                             logging.FileHandler("app.log"),  # Log to a file named 'app.log'
                             logging.StreamHandler()  # Also log to console
                         ])



load_dotenv()
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

app = Flask(__name__, static_folder='static')
app.secret_key = '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'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

credentials_path = './credentials.json'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gecaDB.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

with app.app_context():
    allowed_people = User.get_all_emails()

# OAuth 2.0 scopes
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/script.external_request',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

def is_credentials_valid(credentials):
    # Créer un objet Credentials à partir du dictionnaire
    creds = Credentials(**credentials)
    # Vérifier si les credentials sont valides et non expirés
    return creds and creds.valid

def is_not_connected():
    return 'credentials' not in session or not is_credentials_valid(session['credentials'])

@app.route('/')
def index():
    if is_not_connected():
        return redirect(url_for('login'))

    return render_template('dashboard.html', user_info=session['user_info'])

# Connections
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            credentials_path, scopes=scopes)
        flow.redirect_uri = url_for('callback', _external=True)

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true')

        session['state'] = state
        return redirect(authorization_url)
    return render_template('login.html')

@app.route('/callback')
def callback():
    state = session.get('state')
    if not state:
        flash("Session expired. Please try logging in again.")
        return redirect(url_for('login'))

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        credentials_path, scopes=scopes, state=state)
    flow.redirect_uri = url_for('callback', _external=True)

    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)

    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session['credentials'])

    user_info = connector.get_user_info()

    if user_info['email'] not in allowed_people:
        flash(f"Access Denied: The email {user_info['email']} is not allowed.")
        return redirect(url_for('login'))

    with app.app_context():
        user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        flash("Your email is not registered in the system.")
        return redirect(url_for('login'))

    session['user_info'] = user_info
    session['role'] = user.get_role()

    flash(f"Welcome {user_info['email']}! You are logged in as {session['role']}.")
    return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    session.clear()
    return redirect(url_for('login'))


'''EXPENSES'''
@app.route('/addExpense')
def addExpense():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    members = User.get_all_names()

    return render_template('addExpense.html', error=error_message, user_info=session['user_info'], members=members)


@app.route('/addingExpense', methods=['GET', 'POST'])
def addingExpense():
    if is_not_connected():
        return redirect(url_for('login'))

    if request.method == 'POST':
        required_fields = ['date', 'debitedfrom', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('addExpense', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(credentials_path)
        connector.authenticate(session_credentials)

        members = User.get_all_emails()

        expense_data = {
            'date': request.form['date'],
            'debitedfrom': request.form['debitedfrom'],
            'beneficiary': request.form['beneficiary'],
            'subject': request.form['subject'],
            'amount': float(request.form['amount']),
            'description': request.form['description'],
            'addedBy': session['user_info']['email'],
            'members': members
        }
        expense = Expense(expense_data)

        is_valid, error_message = expense.validate_data()
        if not is_valid:
            return redirect(url_for('addExpense', error=error_message))

        try:
            expense.save_to_db()
            expense.add_to_sheet(connector)
            return redirect(url_for('addExpense', error="Dépense ajoutée avec succès"))
        except Exception as e:
            return redirect(url_for('addExpense', error=f"Erreur : {e}"))

    return redirect(url_for('addExpense'))

'''INCOMES'''
@app.route('/addIncome')
def addIncome():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    members = User.get_all_names()

    return render_template('addIncome.html', error=error_message, user_info=session['user_info'], members=members)


@app.route('/addingIncome', methods=['GET', 'POST'])
def addingIncome():
    if is_not_connected():
        return redirect(url_for('login'))

    if request.method == 'POST':
        required_fields = ['date', 'givenBy', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('addIncome', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(credentials_path)
        connector.authenticate(session_credentials)

        members = connector.get_members()

        income_data = {
            'date': request.form['date'],
            'givenBy': request.form['givenBy'],
            'beneficiary': request.form['beneficiary'],
            'subject': request.form['subject'],
            'amount': float(request.form['amount']),
            'description': request.form['description'],
            'addedBy': session['user_info']['email'],
            'members': members
        }
        income = Income(income_data)

        is_valid, error_message = income.validate_data()
        if not is_valid:
            return redirect(url_for('addIncome', error=error_message))

        try:
            income.save_to_db()
            income.add_to_sheet(connector)
            return redirect(url_for('addIncome', error="Recette ajoutée avec succès"))
        except Exception as e:
            return redirect(url_for('addIncome', error=f"Erreur : {e}"))

    return redirect(url_for('addIncome'))

'''INTERNAL TRANSFERS'''
@app.route('/addInternalTransfer')
def addInternalTransfer():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    members = User.get_all_names()

    return render_template('addInternalTransfer.html', error=error_message, user_info=session['user_info'], members=members)


@app.route('/addingInternalTransfer', methods=['GET', 'POST'])
def addingInternalTransfer():
    if is_not_connected():
        return redirect(url_for('login'))

    if request.method == 'POST':
        required_fields = ['date', 'debitedfrom', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('addInternalTransfer', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(credentials_path)
        connector.authenticate(session_credentials)

        members = connector.get_members()

        transfer_data = {
            'date': request.form['date'],
            'debitedfrom': request.form['debitedfrom'],
            'beneficiary': request.form['beneficiary'],
            'subject': '[TI] ' + request.form['subject'],
            'amount': float(request.form['amount']),
            'description': request.form['description'],
            'addedBy': session['user_info']['email'],
            'members': members
        }
        income = Income({
            'date': transfer_data['date'],
            'givenBy': transfer_data['debitedfrom'],
            'beneficiary': transfer_data['beneficiary'],
            'subject': transfer_data['subject'],
            'amount': transfer_data['amount'],
            'description': transfer_data['description'],
            'addedBy': transfer_data['addedBy'],
            'members': transfer_data['members']
        })

        expense = Expense({
            'date': transfer_data['date'],
            'debitedfrom': transfer_data['debitedfrom'],
            'beneficiary': transfer_data['beneficiary'],
            'subject': transfer_data['subject'],
            'amount': transfer_data['amount'],
            'description': transfer_data['description'],
            'addedBy': transfer_data['addedBy'],
            'members': transfer_data['members']
        })

        is_valid_income, error_income = income.validate_data()
        if not is_valid_income:
            return redirect(url_for('addInternalTransfer', error=error_income))

        is_valid_expense, error_expense = expense.validate_data()
        if not is_valid_expense:
            return redirect(url_for('addInternalTransfer', error=error_expense))

        try:
            expense.save_to_db()
            income.save_to_db()
            expense.add_to_sheet(connector)
            income.add_to_sheet(connector)
            return redirect(url_for('addInternalTransfer', error="Transfert Interne ajouté avec succès"))
        except Exception as e:
            return redirect(url_for('addInternalTransfer', error=f"Erreur : {e}"))

    return redirect(url_for('addInternalTransfer'))


'''@app.route('/askForMoney')
def askForMoney():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    return render_template('askForMoney.html', error = error_message, user_info=session['user_info'], members = connector.get_members())

@app.route('/askingForMoney', methods=['GET', 'POST'])
def askingForMoney():
    if is_not_connected():
        return redirect(url_for('login'))
    if request.method == 'POST':
        if request.form['toBeGivenBy'] and request.form['beneficiary'] and request.form['reason'] and request.form['amount'] and request.form['description']:

            session_credentials = session['credentials']
            connector = GoogleAPIConnector(credentials_path)
            connector.authenticate(session_credentials)
            members = connector.get_members()
            moneyask = classes.AskMoney.AskMoney({   'toBeGivenBy': request.form['toBeGivenBy'],
                                               'beneficiary': request.form['beneficiary'],
                                               'reason': request.form['reason'],
                                               'amount': request.form['amount'],
                                               'description': request.form['description'],
                                               'askedBy': session['user_info']['email'],
                                               'members': members})
            is_valid, Error = moneyask.validate_data()
            print(Error)
            if is_valid:
                moneyask.askForMoney(connector)
            else:
                return redirect(url_for('askForMoney', error=Error))
        else:
            return redirect(url_for('askForMoney', error="Veuillez remplir tous les champs"))
        return redirect(url_for('askForMoney', error="Demande ajoutée avec succès"))

@app.route('/searchOdds')
def searchOdds():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('searchOdds.html', error = error_message, user_info=session['user_info'])

@app.route('/viewOdds', methods=['GET','POST'])
def viewOdds():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    links = {
            'football' : 'https://www.betclic.fr/football-s1',
            'rugbyxiii' : 'https://www.betclic.fr/rugby-a-xiii-s52',
            'rugbyxv' : 'https://www.betclic.fr/rugby-a-xv-s5',
            'tennis' : 'https://www.betclic.fr/tennis-s2',
            'badminton' : 'https://www.betclic.fr/badminton-s27',
            'baseball' : 'https://www.betclic.fr/baseball-s20',
            'basketball' : 'https://www.betclic.fr/basketball-s4',
            'beachvolley' : 'https://www.betclic.fr/beach-volley-s49',
            'boxe' : 'https://www.betclic.fr/boxe-s16',
            'footamericain' : 'https://www.betclic.fr/football-americain-s14',
            'golf' : 'https://www.betclic.fr/golf-s7',
            'handball' : 'https://www.betclic.fr/handball-s9',
            'hockeysurglace' : 'https://www.betclic.fr/hockey-sur-glace-s13',
            'mma' : 'https://www.betclic.fr/mma-s23'
        }
    if request.method == 'POST' and request.form['sport'].lower() in links.keys():
        marketFilter = {
            'oddA': {
                'min': float(request.form['Amin']) if request.form['Amin'] else None,
                'max': float(request.form['Amax']) if request.form['Amax'] else None
            },
            'oddB': {
                'min': float(request.form['Bmin']) if request.form['Bmin'] else None,
                'max': float(request.form['Bmax']) if request.form['Bmax'] else None
            },
            'coteDraw': {
                'min': float(request.form['Dmin']) if request.form['Dmin'] else None,
                'max': float(request.form['Dmax']) if request.form['Dmax'] else None
            },
            'toDate': request.form['to'] if request.form['to'] else None,
            'fromDate': request.form['from'] if request.form['from'] else None
        }

        data = betclic.scrape_html(marketFilter, links[request.form['sport'].lower()])
        return render_template('viewOdds.html', error = error_message, user_info=session['user_info'], data=data, marketFilter = marketFilter)
    return redirect(url_for('searchOdds', error="Une erreur est survenue"))'''



#User management
@app.route('/singleUser')
def singleUser():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('singleUser.html', error = error_message, user_info=session['user_info'])

@app.route('/users')
def users():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error = error_message, user_info=session['user_info'])

@app.route('/createUser')
def createUser():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error = error_message, user_info=session['user_info'])

@app.route('/incomes')
def incomes():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('viewIncomes.html', error = error_message, user_info=session['user_info'])

@app.route('/timeline')
def timeline():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('timeline.html', error = error_message, user_info=session['user_info'])

@app.route('/save-location', methods=['POST'])
def save_location():
    data = request.json  # Receive JSON data from client
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    email = session['user_info']['email']

    if latitude is not None and longitude is not None:
        current_datetime = datetime.now()
        user = User.query.filter_by(email=email).first()
        user.set_location(longitude, latitude, current_datetime)
        return jsonify({'status': 'success', 'message': 'Location saved successfully!'}), 201
    else:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
