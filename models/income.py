from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from typing import Dict, Optional, Any
import os
from services.notifications import notification_service

from db import db

class Income(db.Model):
    __tablename__ = 'incomes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime, nullable=False)
    given_by = db.Column(db.String(100), nullable=False)
    beneficiary = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    added_by = db.Column(db.String(100), db.ForeignKey('users.email'), nullable=False)
    validated = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', backref='incomes', lazy='joined')

    def __init__(self, data: Dict[str, Optional[Any]]):
        self.date = data.get('date')
        self.given_by = data.get('givenBy')
        self.beneficiary = data.get('beneficiary')
        self.subject = data.get('subject')
        self.amount = float(data.get('amount'))
        self.description = data.get('description')
        self.added_by = data.get('addedBy')
        self.script_id = os.getenv('INCOME_SCRIPT_ID')
        self.validated = data.get('validated', False)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date,
            'given_by': self.given_by,
            'beneficiary': self.beneficiary,
            'subject': self.subject,
            'amount': self.amount,
            'description': self.description,
            'added_by': self.added_by,
            'validated': self.validated
        }

    def to_list(self):
        return [
            self.date,
            self.beneficiary,
            self.given_by,
            self.subject,
            self.amount,
            self.description,
            self.added_by,
            self.validated
        ]

    def validate(self):
        self.validated = True
        db.session.commit()

    def invalidate(self):
        self.validated = False
        db.session.commit()

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def notify(self):
        notification_service.notify_income(self)


    def add_to_sheet(self, connector):
        try:
            if isinstance(self.date, str):
                try:
                    self.date = datetime.strptime(self.date, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"Format de date invalide : {self.date}. Attendu : YYYY-MM-DD")

            if not isinstance(self.date, datetime):
                raise TypeError(f"La date doit être un objet datetime, mais est de type {type(self.date)}")

            formatted_date = self.date.strftime('%d/%m/%Y')

            data = self.to_list()
            data[0] = formatted_date
            print(f'beneficiary: {self.beneficiary} debited_from: {self.given_by}')

            print(f"Tentative d'ajout à la feuille: {data}")

            result = connector.run_script(self.script_id, "addIncome", data)
            if result is None:
                print("Avertissement: Le script a été exécuté mais n'a retourné aucun résultat")
            elif 'error' in result:
                print(f"Erreur lors de l'ajout à la feuille: {result}")
                raise Exception(f"{result}")
            else:
                print(f"Résultat de l'ajout à la feuille: {result}")
            return True
        except TypeError as e:
            print(f"Erreur de type lors de l'ajout à la feuille: {e}")
            raise
        except ValueError as e:
            print(f"Erreur de valeur lors de l'ajout à la feuille: {e}")
            raise
        except Exception as e:
            print(f"Error adding income to sheet: {e}")
            print(f"Type d'erreur: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise

    def validate_data(self):
        from models.user import User
        members = User.get_all_names()
        members.insert(0, 'GECA')
        try:
            if self.amount is None or self.amount <= 0.01:
                return False, 'Amount error'

            print(self.beneficiary)
            print(members)
            if self.beneficiary not in members:
                return False, 'Beneficiary not registered'

            try:
                from datetime import datetime
                datetime.strptime(self.date, '%Y-%m-%d')
            except ValueError:
                return False, 'Date Error'

            return True, 'Data is good'
        except Exception as e:
            return False, str(e)
