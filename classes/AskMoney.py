from typing import Any, Dict, Optional
from classes.GoogleAPIConnector import GoogleAPIConnector
import os
from datetime import date
import logging

class AskMoney():
    def __init__(self, data: Dict[str, Optional[Any]] = {'toBeGivenBy': None, 'beneficiary': None, 'subject': None, 'amount': None, 'description': None, 'askedBy': None, 'members': None}):
        self.date = None
        self.toBeGivenBy = data.get('toBeGivenBy')
        self.beneficiary = data.get('beneficiary')
        self.reason = data.get('reason')
        self.amount = float(data.get('amount'))
        self.description = data.get('description')
        self.askedBy = data.get('askedBy')
        self.members = data.get('members')
        self.script_id = os.getenv('ASKMONEY_SCRIPT_ID')
        self.function_name = "askForMoney"

    def toDict(self) -> Dict[str, Optional[Any]]:
        return {
            'date': self.date,
            'toBeGivenBy': self.toBeGivenBy,
            'beneficiary': self.beneficiary,
            'reason': self.reason,
            'amount': self.amount,
            'description': self.description,
            'askedBy': self.askedBy
        }
    def toList(self):
        return [
            self.date,
            self.toBeGivenBy,
            self.beneficiary,
            self.reason,
            self.amount,
            self.description,
            self.askedBy
        ]

    def askForMoney(self, connector: GoogleAPIConnector):
        is_valid, message = self.validate_data()
        logging.debug(f'Valid : {is_valid} - {message}')
        if not is_valid:
            print(f"Validation Error: {message}")
            return
        try:
            datetime = date.today()
            self.date = datetime.strftime('%d/%m/%Y')
            connector.run_script(self.script_id, self.function_name, self.toList())
        except Exception as e:
            print(f"Erreur lors de l'exécution du script : {e}")

    def validate_data(self) -> (bool, str):
        if self.amount is None or self.amount <= 0.01:
            return False, 'Amount error'
        if self.beneficiary not in self.members:
            return False, 'Beneficiary error'
        return True, 'Data is good'