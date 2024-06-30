from typing import Any, Dict, Optional
from classes.GoogleAPIConnector import GoogleAPIConnector
import os
from datetime import datetime

class Income():
    def __init__(self, data: Dict[str, Optional[Any]] = {'date': None, 'givenBy': None, 'beneficiary': None, 'subject': None, 'amount': None, 'description': None, 'addedBy': None, 'members': None}):
        self.date = data.get('date')
        self.givenBy = data.get('givenBy')
        self.beneficiary = data.get('beneficiary')
        self.subject = data.get('subject')
        self.amount = float(data.get('amount'))
        self.description = data.get('description')
        self.addedBy = data.get('addedBy')
        self.members = data.get('members')
        self.script_id = os.getenv('INCOME_SCRIPT_ID')
        self.function_name = "addIncome"

    def toDict(self) -> Dict[str, Optional[Any]]:
        return {
            'date': self.date,
            'beneficiary': self.beneficiary,
            'givenBy': self.givenBy,
            'subject': self.subject,
            'amount': self.amount,
            'description': self.description,
            'addedBy': self.addedBy
        }
    def toList(self):
        return [
            self.date,
            self.beneficiary,
            self.givenBy,
            self.subject,
            self.amount,
            self.description,
            self.addedBy
        ]

    def addIncome(self, connector: GoogleAPIConnector):
        is_valid, message = self.validate_data()
        if not is_valid:
            print(f"Validation Error: {message}")
            return
        try:
            self.date = datetime.strptime(self.date, '%Y-%m-%d').strftime('%d/%m/%Y')
            connector.run_script(self.script_id, self.function_name, self.toList())
        except Exception as e:
            print(f"Erreur lors de l'exécution du script : {e}")

    def validate_data(self) -> (bool, str):
        if self.amount is None or self.amount <= 0.01:
            return False, 'Amount error'
        if self.beneficiary not in self.members:
            return False, 'beneficiary error'

        try:
            datetime.strptime(self.date, '%Y-%m-%d')
        except ValueError as e:
            return False, 'Date Error'

        return True, 'Data is good'