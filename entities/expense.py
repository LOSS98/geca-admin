from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from typing import Dict, Optional, Any
import os

from db import db

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime, nullable=False)
    debited_from = db.Column(db.String(100), nullable=False)
    beneficiary = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    added_by = db.Column(db.String(100), db.ForeignKey('users.email'), nullable=False)
    validated = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', backref='expenses', lazy='joined')

    def __init__(self, data: Dict[str, Optional[Any]]):
        self.date = data.get('date')
        self.debited_from = data.get('debitedfrom')
        self.beneficiary = data.get('beneficiary')
        self.subject = data.get('subject')
        self.amount = float(data.get('amount'))
        self.description = data.get('description')
        self.added_by = data.get('addedBy')
        self.script_id = os.getenv('EXPENSE_SCRIPT_ID')
        self.validated = data.get('validated', False)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date,
            'debited_from': self.debited_from,
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
            self.debited_from,
            self.beneficiary,
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

    def add_to_sheet(self, connector):
        try:
            formatted_date = datetime.strptime(self.date, '%Y-%m-%d').strftime('%d/%m/%Y')
            data = self.to_list()
            data[0] = formatted_date  # Update the date format for the sheet
            connector.run_script(self.script_id, "addExpense", data)
        except Exception as e:
            print(f"Error adding expense to sheet: {e}")
