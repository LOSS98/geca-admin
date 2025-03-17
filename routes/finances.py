from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify

from models.income import Income
from models.expense import Expense
from routes.auth import is_not_connected
from services.google_api import GoogleAPIConnector
from config import Config
from models.user import User
from models import db
from services.notifications import notification_service

finances_bp = Blueprint('finances', __name__)


@finances_bp.route('/addExpense')
def add_expense():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    members = User.get_all_names()
    members.insert(0, 'GECA')

    return render_template('addExpense.html', error=error_message, user_info=session['user_info'], members=members)


@finances_bp.route('/addingExpense', methods=['GET', 'POST'])
def adding_expense():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        required_fields = ['date', 'debitedfrom', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('finances.add_expense', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
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
            return redirect(url_for('finances.add_expense', error=error_message))

        try:
            # expense.save_to_db()
            print(expense.add_to_sheet(connector))
            expense.notify()
            return redirect(url_for('finances.add_expense', error="Dépense ajoutée avec succès"))
        except Exception as e:
            return redirect(url_for('finances.add_expense', error=f"Transaction non ajoutée ! Reconnection nécessaire."))

    return redirect(url_for('finances.add_expense'))


@finances_bp.route('/addIncome')
def add_income():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    session_credentials = session['credentials']
    connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
    connector.authenticate(session_credentials)
    members = User.get_all_names()
    members.insert(0, 'GECA')

    return render_template('addIncome.html', error=error_message, user_info=session['user_info'], members=members)


@finances_bp.route('/addingIncome', methods=['GET', 'POST'])
def adding_income():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        required_fields = ['date', 'givenBy', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('finances.add_income', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
        connector.authenticate(session_credentials)

        members = User.get_all_names()
        members.insert(0, 'GECA')

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
            return redirect(url_for('finances.add_income', error=error_message))

        try:
            # income.save_to_db()
            income.add_to_sheet(connector)
            income.notify()
            return redirect(url_for('finances.add_income', error="Recette ajoutée avec succès"))
        except Exception as e:
            return redirect(url_for('finances.add_income', error=f"Transaction non ajoutée ! Reconnection nécessaire."))

    return redirect(url_for('finances.add_income'))


@finances_bp.route('/addInternalTransfer')
def add_internal_transfer():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    session_credentials = session['credentials']
    connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
    connector.authenticate(session_credentials)
    members = User.get_all_names()
    members.insert(0, 'GECA')

    return render_template('addInternalTransfer.html', error=error_message, user_info=session['user_info'],
                           members=members)


@finances_bp.route('/addingInternalTransfer', methods=['GET', 'POST'])
def adding_internal_transfer():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        required_fields = ['date', 'debitedfrom', 'beneficiary', 'subject', 'amount', 'description']
        if not all(field in request.form and request.form[field] for field in required_fields):
            return redirect(url_for('finances.add_internal_transfer', error="Veuillez remplir tous les champs"))

        session_credentials = session['credentials']
        connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
        connector.authenticate(session_credentials)

        members = User.get_all_names()
        members.insert(0, 'GECA')

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
            return redirect(url_for('finances.add_internal_transfer', error=error_income))

        is_valid_expense, error_expense = expense.validate_data()
        if not is_valid_expense:
            return redirect(url_for('finances.add_internal_transfer', error=error_expense))

        try:
            # expense.save_to_db()
            # income.save_to_db()
            expense.add_to_sheet(connector)
            income.add_to_sheet(connector)
            notification_service.notify_internal_transfer(expense, income)
            return redirect(url_for('finances.add_internal_transfer', error="Transfert Interne ajouté avec succès"))
        except Exception as e:
            return redirect(url_for('finances.add_internal_transfer', error=f"Transaction non ajoutée ! Reconnection nécessaire."))

    return redirect(url_for('finances.add_internal_transfer'))


# @finances_bp.route('/incomes')
# def incomes_list():
#     if is_not_connected():
#         return redirect(url_for('auth.login'))
#     error_message = None
#     if 'error' in request.args:
#         error_message = request.args.get('error')
#     return render_template('viewIncomes.html', error=error_message, user_info=session['user_info'])



# @finances_bp.route('/askForMoney')
# def ask_for_money():
#     if is_not_connected():
#         return redirect(url_for('auth.login'))
#     error_message = None
#     if 'error' in request.args:
#         error_message = request.args.get('error')
#     session_credentials = session['credentials']
#     connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
#     connector.authenticate(session_credentials)
#     return render_template('askForMoney.html', error=error_message, user_info=session['user_info'],
#                            members=connector.get_members())


# @finances_bp.route('/askingForMoney', methods=['GET', 'POST'])
# def asking_for_money():
#     if is_not_connected():
#         return redirect(url_for('auth.login'))
#     if request.method == 'POST':
#         if request.form['toBeGivenBy'] and request.form['beneficiary'] and request.form['reason'] and request.form[
#             'amount'] and request.form['description']:
#             session_credentials = session['credentials']
#             connector = GoogleAPIConnector(Config.CREDENTIALS_PATH)
#             connector.authenticate(session_credentials)
#             members = connector.get_members()
#
#             from services.ask_money import AskMoney
#             moneyask = AskMoney({
#                 'toBeGivenBy': request.form['toBeGivenBy'],
#                 'beneficiary': request.form['beneficiary'],
#                 'reason': request.form['reason'],
#                 'amount': request.form['amount'],
#                 'description': request.form['description'],
#                 'askedBy': session['user_info']['email'],
#                 'members': members
#             })
#
#             is_valid, Error = moneyask.validate_data()
#             if is_valid:
#                 moneyask.askForMoney(connector)
#             else:
#                 return redirect(url_for('finances.ask_for_money', error=Error))
#         else:
#             return redirect(url_for('finances.ask_for_money', error="Veuillez remplir tous les champs"))
#         return redirect(url_for('finances.ask_for_money', error="Demande ajoutée avec succès"))