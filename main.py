from flask import Flask, render_template, request, session, redirect, url_for, flash
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
# logging.basicConfig(level=logging.DEBUG,
#                     format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
#                     handlers=[
#                         logging.FileHandler("app.log"),  # Log to a file named 'app.log'
#                         logging.StreamHandler()  # Also log to console
#                     ])



load_dotenv()
allowed_people = ['achillemortier@gmail.com','brieuc.sapin@gmail.com','enzodelpy7@gmail.com','hachemigabrielle974@gmail.com','isrope04@gmail.com','jeannemoulis28@gmail.com','breuillerjulian@gmail.com','ganej712@gmail.com','khalil.mzoughikm@gmail.com','leosentes31@gmail.com','lilianmellinger@gmail.com','lilou.montain@gmail.com','delassault.lucas@gmail.com','ludo.vig04@gmail.com','ralitemac@gmail.com','m.dalmon@orange.fr','famathilde12@gmail.com','mathis.morel1803@gmail.com','maximecav02@gmail.com','mia.perrouin@gmail.com','bouzier.noa1406@gmail.com','garel.noemie@gmail.com','paul.ferre316481@gmail.com','pierre.vilcocq14@gmail.com','robin.chausson66@gmail.com','sachadarly564@gmail.com','lison.spielmann@gmail.com','thibautbredel76390@gmail.com','timotheecroclyonnet@gmail.com','tompardo978@gmail.com','nowak.ugo31@gmail.com','valentine.sandrin15@gmail.com','zachary.barre0809@gmail.com','eglantine.fonrose@gmail.com','amandine.rolland39@gmail.com','gorelgwladys@gmail.com','glathlouise@gmail.com','celia.ap.insa@gmail.com','hugoroze72@gmail.com','boniloann29@gmail.com','tom.philibert2004@gmail.com','lilian.monfort1@gmail.com','annateixido66@gmail.com','nils.peteil@gmail.com','lorickdesert2003@gmail.com','pierre.deblaise35@gmail.com','cluka042@gmail.com','teggyrosier@gmail.com']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

app = Flask(__name__, static_folder='static')
app.secret_key = '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'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Chemins vers les fichiers credentials et token
credentials_path = './credentials.json'

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

@app.route('/')
def index():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
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
    state = session['state']
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
        flash(f"Access Denied: The email {user_info['email']} address is not allowed.")
        return redirect(url_for('disconnect'))
    session['user_info'] = user_info
    return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    session.clear()
    return redirect(url_for('login'))

@app.route('/addExpense')
def addExpense():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    return render_template('addExpense.html', error = error_message, user_info=session['user_info'], members = connector.get_members())

@app.route('/addingExpense', methods=['GET', 'POST'])
def addingExpense():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        if request.form['date'] and request.form['debitedfrom'] and request.form['beneficiary'] and request.form['subject'] and request.form['amount'] and request.form['description']:

            session_credentials = session['credentials']
            connector = GoogleAPIConnector(credentials_path)
            connector.authenticate(session_credentials)
            members = connector.get_members()
            expense = classes.Expense.Expense({'date': request.form['date'],
                                               'debitedfrom': request.form['debitedfrom'],
                                               'beneficiary': request.form['beneficiary'],
                                               'subject': request.form['subject'],
                                               'amount': request.form['amount'],
                                               'description': request.form['description'],
                                               'addedBy': session['user_info']['email'],
                                               'members': members})
            is_valid, Error = expense.validate_data()
            print(Error)
            if is_valid:
                expense.addExpense(connector)
            else:
                return redirect(url_for('addExpense', error=Error))
        else:
            return redirect(url_for('addExpense', error="Veuillez remplir tous les champs"))
        return redirect(url_for('addExpense', error="Dépense ajoutée avec succès"))

@app.route('/addIncome')
def addIncome():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    return render_template('addIncome.html', error = error_message, user_info=session['user_info'], members = connector.get_members())

@app.route('/addingIncome', methods=['GET', 'POST'])
def addingIncome():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        if request.form['date'] and request.form['givenBy'] and request.form['beneficiary'] and request.form['subject'] and request.form['amount'] and request.form['description']:

            session_credentials = session['credentials']
            connector = GoogleAPIConnector(credentials_path)
            connector.authenticate(session_credentials)
            members = connector.get_members()
            income = classes.Income.Income({'date': request.form['date'],
                                               'givenBy': request.form['givenBy'],
                                               'beneficiary': request.form['beneficiary'],
                                               'subject': request.form['subject'],
                                               'amount': request.form['amount'],
                                               'description': request.form['description'],
                                               'addedBy': session['user_info']['email'],
                                               'members': members})
            is_valid, Error = income.validate_data()
            print(Error)
            if is_valid:
                income.addIncome(connector)
            else:
                return redirect(url_for('addIncome', error=Error))
        else:
            return redirect(url_for('addIncome', error="Veuillez remplir tous les champs"))
        return redirect(url_for('addIncome', error="Recette ajoutée avec succès"))

@app.route('/addInternalTransfer')
def addInternalTransfer():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    session_credentials = session['credentials']
    connector = GoogleAPIConnector(credentials_path)
    connector.authenticate(session_credentials)
    return render_template('addInternalTransfer.html', error = error_message, user_info=session['user_info'], members = connector.get_members())

@app.route('/addingInternalTransfer', methods=['GET', 'POST'])
def addingInternalTransfer():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        if request.form['date'] and request.form['debitedfrom'] and request.form['beneficiary'] and request.form['subject'] and request.form['amount'] and request.form['description']:

            session_credentials = session['credentials']
            connector = GoogleAPIConnector(credentials_path)
            connector.authenticate(session_credentials)
            members = connector.get_members()
            income = classes.Income.Income({'date': request.form['date'],
                                               'givenBy': request.form['debitedfrom'],
                                               'beneficiary': request.form['beneficiary'],
                                               'subject': '[TI] '+request.form['subject'],
                                               'amount': request.form['amount'],
                                               'description': request.form['description'],
                                               'addedBy': session['user_info']['email'],
                                               'members': members})
            expense = classes.Expense.Expense({'date': request.form['date'],
                                               'debitedfrom': request.form['debitedfrom'],
                                               'beneficiary': request.form['beneficiary'],
                                               'subject': '[TI] '+request.form['subject'],
                                               'amount': request.form['amount'],
                                               'description': request.form['description'],
                                               'addedBy': session['user_info']['email'],
                                               'members': members})
            is_valid, Error = income.validate_data()
            if is_valid:
                is_valid, Error = expense.validate_data()
                if is_valid:
                    expense.addExpense(connector)
                    income.addIncome(connector)
                else:
                    return redirect(url_for('addInternalTransfer', error=Error))
            else:
                return redirect(url_for('addInternalTransfer', error=Error))
        else:
            return redirect(url_for('addInternalTransfer', error="Veuillez remplir tous les champs"))
        return redirect(url_for('addInternalTransfer', error="Transfert Interne ajouté avec succès"))

@app.route('/askForMoney')
def askForMoney():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
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
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
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
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('searchOdds.html', error = error_message, user_info=session['user_info'])

@app.route('/viewOdds', methods=['GET','POST'])
def viewOdds():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
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
    return redirect(url_for('searchOdds', error="Une erreur est survenue"))



#User management
@app.route('/singleUser')
def singleUser():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('singleUser.html', error = error_message, user_info=session['user_info'])

@app.route('/users')
def users():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error = error_message, user_info=session['user_info'])

@app.route('/createUser')
def createUser():
    if 'credentials' not in session or not is_credentials_valid(session['credentials']):
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error = error_message, user_info=session['user_info'])


def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
