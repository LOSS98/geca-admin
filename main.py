from datetime import datetime

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_migrate import Migrate

from entities.role import Role
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
from entities.task import Task, TaskState

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

#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gecaDB.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://khalil:Kh4lil9870720406*@51.38.83.204:1125/postgres_geca_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)



with app.app_context():
    db.create_all()
    Role.initialize_roles()

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

    # Récupérer les informations de l'utilisateur connecté
    user_email = session['user_info']['email']
    user = User.query.filter_by(email=user_email).first()

    if not user:
        return redirect(url_for('index', error="Utilisateur non trouvé"))

    # Récupérer les rôles de l'utilisateur
    user_roles = user.get_roles()

    return render_template('singleUser.html', error=error_message, user_info=session['user_info'], user=user,
                           user_roles=user_roles)


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

@app.route('/task')
def timeline():
    if is_not_connected():
        return redirect(url_for('login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('timeline old.html', error = error_message, user_info=session['user_info'])

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


# Add these imports at the top of main.py
from entities.task import Task, TaskState
from flask import jsonify
from datetime import datetime

# Add these route handlers to main.py

# Add these imports at the top of main.py
from entities.task import Task, TaskState
from flask import jsonify
from datetime import datetime

# Add these route handlers to main.py


'''TASKS'''
@app.route('/tasks')
def tasks():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    with app.app_context():
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')

    return render_template('timeline.html', error=error_message, user_info=session['user_info'], user_role=user_role)

@app.route('/createTask')
def create_task_page():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    with app.app_context():
        members = User.get_all_names()
        roles = ['admin', 'member', 'treasurer']  # Add all available roles in your system

    return render_template('createTask.html', error=error_message, user_info=session['user_info'], members=members, roles=roles)

@app.route('/api/tasks')
def get_tasks():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')

        # Get tasks assigned to the current user
        tasks_as_assignee = Task.get_tasks_for_user(user_email)

        # Get tasks assigned by the current user (regardless of role)
        tasks_as_assigner = Task.get_assigned_tasks_by_user(user_email)

        # Combine and remove duplicates
        all_tasks = []
        task_ids = set()

        for task in tasks_as_assignee + tasks_as_assigner:
            if task.id not in task_ids:
                all_tasks.append(task)
                task_ids.add(task.id)

        # Convert tasks to dictionaries with a flag indicating if the user is the assigner
        tasks_data = []
        for task in all_tasks:
            task_dict = task.to_dict()
            task_dict['is_assigner'] = (task.assigned_by == user_email)
            task_dict['can_manage'] = (task.assigned_by == user_email) or (user_role == 'admin')
            tasks_data.append(task_dict)

        return jsonify(tasks_data)
    except Exception as e:
        print(f"Error getting tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/createTask', methods=['POST'])
def create_task_api():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    user_email = session['user_info']['email']

    try:
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%dT%H:%M')
        due_date = datetime.strptime(data['due_date'], '%Y-%m-%dT%H:%M')

        task_data = {
            'assigned_by': user_email,
            'start_date': start_date,
            'due_date': due_date,
            'subject': data['subject'],
            'description': data['description'],
            'priority': data.get('priority', 'medium'),  # Default to medium priority
            'target_roles': []  # Default à une liste vide
        }

        # Handle different assignment types
        assignment_type = data.get('assignment_type')

        if assignment_type == 'role':
            # Récupérer les rôles cibles de la tâche
            task_data['target_roles'] = data.get('target_roles', [])

        # Créer la tâche en utilisant le constructeur
        task = Task(task_data)

        # Sauvegarder la tâche en base de données
        task.save_to_db()

        # Si la tâche est attribuée à des utilisateurs spécifiques
        if assignment_type == 'users':
            # Get selected users
            assignees = data.get('assignees', [])
            print(f"Selected assignees: {assignees}")
            if assignees:
                # Utiliser la méthode d'assignation multiple
                user_emails = []
                from entities.user import User
                for assignee_name in assignees:
                    # Find user by name (format: "lastname firstname")
                    parts = assignee_name.split(' ', 1)
                    if len(parts) == 2:
                        lname, fname = parts
                        user = User.query.filter_by(lname=lname, fname=fname).first()
                        if user:
                            user_emails.append(user.email)

                if user_emails:
                    task.assign_to_users(user_emails)

        return jsonify({'success': True, 'task_id': task.id})

    except Exception as e:
        db.session.rollback()
        print(f"Error creating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/dispute', methods=['POST'])
def dispute_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Check if the user is assigned to this task
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode dispute qui notifie automatiquement
        task.dispute(user_email)

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error disputing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/validate', methods=['POST'])
def validate_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Check if the user is assigned to this task
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode mark_to_validate qui notifie automatiquement
        task.mark_to_validate(user_email)

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error validating task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only the assigner or an admin can mark a task as complete
        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode mark_as_done qui notifie automatiquement
        task.mark_as_done()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error completing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/remove-assignee', methods=['POST'])
def remove_assignee(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    user_email = session['user_info']['email']
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # Only the assigner can remove assignees
    if task.assigned_by != user_email:
        return jsonify({'error': 'Not authorized'}), 403

    assignee_email = data.get('assignee_email')
    if assignee_email:
        task.remove_assignee(assignee_email)

    return jsonify({'success': True})

@app.route('/api/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only the assigner or an admin can delete a task
        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode delete_task qui notifie automatiquement
        task.delete_task()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/cancel-validation', methods=['POST'])
def cancel_validation(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only task assignees can cancel their validation request
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode cancel_validation qui notifie automatiquement
        task.cancel_validation()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling validation: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/reject-validation', methods=['POST'])
def reject_validation(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Seul l'émetteur de la tâche peut rejeter une validation
        if task.assigned_by != user_email:
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode reject_validation qui notifie automatiquement
        task.reject_validation()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting validation: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 2. Mise à jour de la fonction de rejet de contestation pour gérer correctement les erreurs de notification
@app.route('/api/tasks/<int:task_id>/reject-dispute', methods=['POST'])
def reject_dispute(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only the assigner can reject a dispute
        if task.assigned_by != user_email:
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode reject_dispute qui notifie automatiquement
        task.reject_dispute()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting dispute: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 3. Amélioration de la fonction de réouverture de tâche
@app.route('/api/tasks/<int:task_id>/reopen', methods=['POST'])
def reopen_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only the assigner or an admin can reopen a task
        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        # Utiliser la méthode reopen_task qui notifie automatiquement
        task.reopen_task()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error reopening task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/priority', methods=['POST'])
def change_task_priority(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Only the assigner or an admin can change priority
        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        # Get new priority from request
        data = request.json
        new_priority = data.get('priority')

        if not new_priority or new_priority not in ['low', 'medium', 'high']:
            return jsonify({'error': 'Invalid priority value'}), 400

        # Utiliser la méthode set_priority qui gère la notification
        result = task.set_priority(new_priority)

        if not result:
            return jsonify({'error': 'Failed to update priority'}), 500

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Error changing task priority: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/available-tasks')
def available_tasks_page():
    if is_not_connected():
        return redirect(url_for('login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    with app.app_context():
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()
        user_roles = user.get_roles() if user else []

    return render_template('available-tasks.html', error=error_message, user_info=session['user_info'], user_roles=user_roles)


@app.route('/api/available-tasks')
def get_available_tasks():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify([])

        # Récupérer les rôles de l'utilisateur
        user_roles = user.get_roles()

        # Récupérer toutes les tâches assignées
        all_tasks = Task.query.filter(
            Task.state == TaskState.ASSIGNED
        ).all()

        # Filtrer les tâches disponibles pour cet utilisateur
        available_tasks = []
        for task in all_tasks:
            # Si la tâche a déjà des assignés, elle n'est pas disponible
            if len(task.assignees) > 0:
                continue

            # Vérifier si la tâche est disponible pour cet utilisateur en fonction de ses rôles
            is_available = False

            # Si la tâche n'a pas de rôles cibles, elle est disponible pour tous
            if not task.target_roles:
                is_available = True
            else:
                # Si la tâche a des rôles cibles, vérifier si l'utilisateur a au moins un de ces rôles
                target_role_names = [role.name for role in task.target_roles]
                if any(role in target_role_names for role in user_roles):
                    is_available = True

            # Si la tâche est disponible, l'ajouter à la liste
            if is_available:
                task_dict = task.to_dict()

                # Ajouter les informations sur le fait que la tâche a été libérée
                # Cela nécessite d'ajouter un champ dans la base de données ou une table de logs
                # Pour l'instant, nous utilisons un champ fictif
                task_dict['previous_assignees'] = []  # À implémenter : historique des assignés

                available_tasks.append(task_dict)

        return jsonify(available_tasks)
    except Exception as e:
        print(f"Error getting available tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/take', methods=['POST'])
def take_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        from entities.user import User
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si la tâche est dans l'état assigné et n'a pas d'assignés
        if task.state != TaskState.ASSIGNED or len(task.assignees) > 0:
            return jsonify({'error': 'Cette tâche n\'est plus disponible'}), 400

        # Vérifier si la tâche est disponible pour cet utilisateur en fonction de ses rôles
        is_available = True
        if task.target_roles:
            user_roles = user.get_roles()
            target_role_names = [role.name for role in task.target_roles]
            if not any(role in target_role_names for role in user_roles):
                is_available = False

        if not is_available:
            return jsonify({'error': 'Vous n\'avez pas les rôles requis pour cette tâche'}), 403

        # Assigner la tâche à cet utilisateur
        task.assignees.append(user)

        # Enregistrer l'action dans l'historique
        from entities.task_history import TaskHistory
        history_entry = TaskHistory(
            task_id=task.id,
            user_email=user_email,
            action="self_assigned"
        )
        history_entry.save_to_db()

        db.session.commit()

        # Notifier le créateur de la tâche
        try:
            from entities.user import User
            creator = User.query.filter_by(email=task.assigned_by).first()
            if creator and creator.phone:
                message = f"Votre tâche '{task.subject}' a été prise par {user.fname} {user.lname}."
                task._send_notification(creator.phone, message)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error taking task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/remind', methods=['POST'])
def remind_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est le créateur de la tâche
        if task.assigned_by != user_email:
            return jsonify({'error': 'Non autorisé'}), 403

        # Envoyer un rappel à tous les assignés
        for user in task.assignees:
            if hasattr(user, 'phone') and user.phone:
                message = task._format_message("reminder", user_email, "Ce rappel a été envoyé par le créateur de la tâche.")
                task._send_notification(user.phone, message)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error sending reminder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/updateUserRole', methods=['POST'])
def update_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        new_role = data.get('role')

        # Vérifier que le rôle est valide
        valid_roles = [
            'Team Bureau', 'Team Partenariat', 'Team Com', 'Team BDA', 'Team BDS',
            'Team Soirée', 'Team FISA', 'Team Opé', 'Team Argent', 'Team Logistique',
            'Team Orga', 'Team Animation', 'Team Sécu', 'Team Film', 'Team E-BDS',
            'Team Silencieuses', 'Team Standard', 'Team Goodies', 'Team INFO', 'Team A&C'
        ]

        if new_role and new_role not in valid_roles:
            return jsonify({'error': 'Rôle invalide'}), 400

        # Mettre à jour le rôle
        user.role = new_role
        db.session.commit()

        # Mettre à jour la session
        session['role'] = new_role

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating user role: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/addUserRole', methods=['POST'])
def add_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        new_role = data.get('role')

        # Vérifier que le rôle est valide
        valid_roles = [
            'Team Bureau', 'Team Partenariat', 'Team Com', 'Team BDA', 'Team BDS',
            'Team Soirée', 'Team FISA', 'Team Opé', 'Team Argent', 'Team Logistique',
            'Team Orga', 'Team Animation', 'Team Sécu', 'Team Film', 'Team E-BDS',
            'Team Silencieuses', 'Team Standard', 'Team Goodies', 'Team INFO', 'Team A&C'
        ]

        if not new_role or new_role not in valid_roles:
            return jsonify({'error': 'Rôle invalide'}), 400

        # Vérifier si l'utilisateur a déjà ce rôle
        if user.has_role(new_role):
            return jsonify({'error': 'Vous avez déjà ce rôle'}), 400

        # Ajouter le rôle
        user.add_role(new_role)

        # Renvoyer la liste mise à jour des rôles
        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error adding user role: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/removeUserRole', methods=['POST'])
def remove_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        role_to_remove = data.get('role')

        # Vérifier que l'utilisateur a bien ce rôle
        if not user.has_role(role_to_remove):
            return jsonify({'error': 'Vous n\'avez pas ce rôle'}), 400

        # Supprimer le rôle
        user.remove_role(role_to_remove)

        # Renvoyer la liste mise à jour des rôles
        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error removing user role: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/request-transfer', methods=['POST'])
def request_task_transfer(task_id):
    """API pour demander une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Récupérer l'email du nouvel utilisateur depuis la requête
        data = request.json
        new_user_email = data.get('new_user_email')

        if not new_user_email:
            return jsonify({'error': 'Email du nouvel utilisateur manquant'}), 400

        # Vérifier que l'utilisateur existe
        from entities.user import User
        new_user = User.query.filter_by(email=new_user_email).first()
        if not new_user:
            return jsonify({'error': 'Utilisateur cible non trouvé'}), 404

        # Demander la cession
        success, message = task.request_transfer(user_email, new_user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error requesting task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/approve-transfer', methods=['POST'])
def approve_task_transfer(task_id):
    """API pour approuver une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Approuver la cession
        success, message = task.approve_transfer(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error approving task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/reject-transfer', methods=['POST'])
def reject_task_transfer(task_id):
    """API pour rejeter une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Rejeter la cession
        success, message = task.reject_transfer(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """API pour récupérer la liste des utilisateurs (pour la sélection lors de la cession)"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        from entities.user import User
        users = User.query.all()
        users_data = [{'email': user.email, 'name': f"{user.lname} {user.fname}"} for user in users]
        return jsonify(users_data)
    except Exception as e:
        print(f"Error getting users: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/release', methods=['POST'])
def release_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est assigné à cette tâche
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Vous n\'êtes pas assigné à cette tâche'}), 403

        # Retirer l'utilisateur des assignés
        task.assignees.remove(user)

        # Si la tâche n'a plus d'assignés et n'est pas en état "done" ou "deleted"
        if len(task.assignees) == 0 and task.state not in [TaskState.DONE, TaskState.DELETED]:
            # Remettre la tâche à l'état "assigned" (disponible)
            task.state = TaskState.ASSIGNED

        db.session.commit()

        # Notifier le créateur de la tâche
        try:
            from entities.user import User
            creator = User.query.filter_by(email=task.assigned_by).first()
            if creator and creator.phone:
                message = f"La tâche '{task.subject}' a été libérée par {user.fname} {user.lname} et est maintenant disponible pour d'autres personnes."
                # Utiliser la méthode existante pour envoyer la notification
                task._send_notification(creator.phone, message)
        except Exception as e:
            print(f"Erreur d'envoi de notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error releasing task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/reassign', methods=['POST'])
def reassign_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est le créateur de la tâche
        if task.assigned_by != user_email:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à réassigner cette tâche'}), 403

        data = request.json
        new_assignees = data.get('assignees', [])

        if not new_assignees:
            return jsonify({'error': 'Veuillez sélectionner au moins un destinataire'}), 400

        # Supprimer les assignations actuelles
        task.assignees = []

        # Ajouter les nouveaux assignés
        from entities.user import User
        for assignee_name in new_assignees:
            # Find user by name (format: "lastname firstname")
            parts = assignee_name.split(' ', 1)
            if len(parts) == 2:
                lname, fname = parts
                user = User.query.filter_by(lname=lname, fname=fname).first()
                if user:
                    task.assignees.append(user)

        # Remettre l'état à "assigned" si ce n'est pas déjà le cas
        if task.state not in [TaskState.DONE, TaskState.DELETED]:
            task.state = TaskState.ASSIGNED

        db.session.commit()

        # Envoyer une notification aux nouveaux assignés
        task.notify_assignment()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error reassigning task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/transfer-ownership', methods=['POST'])
def transfer_task_ownership(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est le créateur de la tâche
        if task.assigned_by != user_email:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à transférer la propriété de cette tâche'}), 403

        data = request.json
        new_owner_email = data.get('new_owner')

        if not new_owner_email:
            return jsonify({'error': 'Veuillez sélectionner un nouveau propriétaire'}), 400

        # Vérifier que le nouvel utilisateur existe
        from entities.user import User
        new_owner = User.query.filter_by(email=new_owner_email).first()

        if not new_owner:
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        # Mettre à jour le propriétaire de la tâche
        old_owner = task.assigned_by
        task.assigned_by = new_owner_email
        db.session.commit()

        # Notifier le nouveau propriétaire
        try:
            if new_owner.phone:
                message = f"La propriété de la tâche '{task.subject}' vous a été transférée par {user_email}. Vous êtes maintenant responsable de cette tâche."
                task._send_notification(new_owner.phone, message)
        except Exception as e:
            print(f"Erreur d'envoi de notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error transferring task ownership: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<int:task_id>/release', methods=['POST'])
def release_task_api(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Utiliser la nouvelle méthode de libération de tâche
        success, message = task.release_task(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error releasing task: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/reassign-by-assignee', methods=['POST'])
def reassign_task_by_assignee(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        data = request.json
        assignment_type = data.get('assignment_type')

        if assignment_type not in ['users', 'roles', 'all']:
            return jsonify({'error': 'Type d\'assignation invalide'}), 400

        # Préparer les données de réassignation selon le type
        reassignment_data = {}

        if assignment_type == 'users':
            # Pour l'assignation à des utilisateurs spécifiques
            assignees = data.get('assignees', [])

            # Convertir les noms d'utilisateurs en emails si nécessaire
            assignee_emails = []
            from entities.user import User

            for assignee in assignees:
                # Si c'est un email, l'utiliser directement
                if '@' in assignee:
                    user = User.query.filter_by(email=assignee).first()
                    if user:
                        assignee_emails.append(assignee)
                else:
                    # Sinon c'est un nom complet, le convertir en email
                    parts = assignee.split(' ', 1)
                    if len(parts) == 2:
                        lname, fname = parts
                        user = User.query.filter_by(lname=lname, fname=fname).first()
                        if user:
                            assignee_emails.append(user.email)

            reassignment_data['assignees'] = assignee_emails

        elif assignment_type == 'roles':
            # Pour l'assignation à des rôles
            reassignment_data['target_roles'] = data.get('target_roles', [])

        # Utiliser la méthode de réassignation par l'assigné
        success, message = task.reassign_by_assignee(user_email, assignment_type, reassignment_data)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error reassigning task by assignee: {str(e)}")
        return jsonify({'error': str(e)}), 500
# Route pour réassigner une tâche
@app.route('/api/tasks/<int:task_id>/reassign', methods=['POST'])
def reassign_task_api(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est le créateur de la tâche
        if task.assigned_by != user_email:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à réassigner cette tâche'}), 403

        data = request.json
        new_assignees = data.get('assignees', [])

        # Convertir les noms d'utilisateurs en emails
        new_assignee_emails = []
        from entities.user import User
        for assignee_name in new_assignees:
            # Find user by name (format: "lastname firstname")
            parts = assignee_name.split(' ', 1)
            if len(parts) == 2:
                lname, fname = parts
                user = User.query.filter_by(lname=lname, fname=fname).first()
                if user:
                    new_assignee_emails.append(user.email)

        # Utiliser la méthode de réassignation de tâche
        success, message = task.reassign_task(new_assignee_emails)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error reassigning task: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route pour transférer la propriété d'une tâche
@app.route('/api/tasks/<int:task_id>/transfer-ownership', methods=['POST'])
def transfer_task_ownership_api(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        # Vérifier si l'utilisateur est le créateur de la tâche
        if task.assigned_by != user_email:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à transférer la propriété de cette tâche'}), 403

        data = request.json
        new_owner_email = data.get('new_owner')

        # Utiliser la méthode de transfert de propriété
        success, message = task.transfer_ownership(new_owner_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error transferring task ownership: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
