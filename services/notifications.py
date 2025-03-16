import requests
import os
import logging
from typing import List, Optional, Dict, Any, Union
from models.user import User  # Importer User du bon package


class NotificationService:


    def __init__(self):
        """Initialise le service de notification"""
        self.api_key = os.getenv('WHATSAPP_API_KEY', 'UDvABgmTtdWC')
        self.api_url = os.getenv('WHATSAPP_API_URL', 'http://api.textmebot.com/send.php')

        self.logger = logging.getLogger(__name__)

    def send_sms(self, recipient_phone: str, message: str) -> bool:

        if not recipient_phone.startswith('+'):
            recipient_phone = '+33' + recipient_phone.lstrip('0')

        try:
            params = {
                'recipient': recipient_phone,
                'apikey': self.api_key,
                'text': message
            }

            response = requests.get(self.api_url, params=params)

            if response.status_code != 200:
                self.logger.error(f"Error sending SMS notification: {response.text}")
                return False

            self.logger.info(f"SMS notification sent successfully to {recipient_phone}")
            return True
        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
            return False

    def send_bulk_sms(self, recipient_phones: List[str], message: str) -> Dict[str, bool]:

        results = {}

        for phone in recipient_phones:
            success = self.send_sms(phone, message)
            results[phone] = success

        return results

    def send_task_notification(self,
                               phones: List[str],
                               task_subject: str,
                               task_type: str,
                               actor_name: str,
                               additional_info: Optional[str] = None) -> Dict[str, bool]:

        emoji_map = {
            "assignment": "📋",
            "validation": "✅",
            "dispute": "⚠️",
            "completed": "🎉",
            "reminder": "⏰",
            "deleted": "🗑️",
            "priority": "🔄",
            "transfer": "↔️"
        }

        emoji = emoji_map.get(task_type, "📌")

        if task_type == "assignment":
            message = f"{emoji} La tâche '{task_subject}' vous a été assignée par {actor_name}."
        elif task_type == "validation":
            message = f"{emoji} La tâche '{task_subject}' a été marquée comme prête pour validation par {actor_name}."
        elif task_type == "dispute":
            message = f"{emoji} La tâche '{task_subject}' a été contestée par {actor_name}."
        elif task_type == "completed":
            message = f"{emoji} La tâche '{task_subject}' a été marquée comme terminée par {actor_name}."
        elif task_type == "reminder":
            message = f"{emoji} RAPPEL: La tâche '{task_subject}' requiert votre attention."
        elif task_type == "deleted":
            message = f"{emoji} La tâche '{task_subject}' a été supprimée par {actor_name}."
        elif task_type == "priority":
            message = f"{emoji} La priorité de la tâche '{task_subject}' a été modifiée par {actor_name}."
        elif task_type == "transfer":
            message = f"{emoji} La tâche '{task_subject}' est en cours de transfert."
        else:
            message = f"{emoji} Mise à jour de la tâche '{task_subject}' par {actor_name}."

        if additional_info:
            message += f"\n\n{additional_info}"

        return self.send_bulk_sms(phones, message)

    def format_financial_notification(self,
                                      transaction_type: str,
                                      amount: float,
                                      subject: str,
                                      actor: str) -> str:

        if transaction_type == "income":
            emoji = "💰"
            message = f"{emoji} RECETTE: {amount:.2f}€ - {subject}"
        elif transaction_type == "expense":
            emoji = "💸"
            message = f"{emoji} DÉPENSE: {amount:.2f}€ - {subject}"
        elif transaction_type == "transfer":
            emoji = "🔄"
            message = f"{emoji} TRANSFERT INTERNE: {amount:.2f}€ - {subject}"
        else:
            emoji = "💶"
            message = f"{emoji} TRANSACTION: {amount:.2f}€ - {subject}"

        message += f"\nAjouté par {actor}"

        return message

    def notify_financial_transaction(self,
                                     transaction_type: str,
                                     amount: float,
                                     subject: str,
                                     actor: str,
                                     recipients: List[str]) -> Dict[str, bool]:

        message = self.format_financial_notification(transaction_type, amount, subject, actor)
        return self.send_bulk_sms(recipients, message)

    def get_user_by_name(self, full_name: str) -> Optional[User]:
        try:
            parts = full_name.split(' ', 1)
            if len(parts) == 2:
                lname, fname = parts
                return User.query.filter_by(lname=lname, fname=fname).first()
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche de l'utilisateur par nom: {e}")
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        try:
            return User.query.filter_by(email=email).first()
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche de l'utilisateur par email: {e}")
        return None

    def notify_income(self, income):
        try:
            beneficiary_name = income.beneficiary
            added_by_email = income.added_by

            phones = []

            beneficiary_user = self.get_user_by_name(beneficiary_name)
            if beneficiary_user and beneficiary_user.phone:
                phones.append(beneficiary_user.phone)

            added_by_user = self.get_user_by_email(added_by_email)
            if added_by_user and added_by_user.phone:
                if not beneficiary_user or beneficiary_user.email != added_by_user.email:
                    phones.append(added_by_user.phone)

            if phones:
                self.notify_financial_transaction(
                    transaction_type="income",
                    amount=income.amount,
                    subject=income.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            self.logger.error(f"Erreur lors de la notification de recette: {e}")

    def notify_expense(self, expense):
        try:
            debited_from_name = expense.debited_from  # Nom complet
            added_by_email = expense.added_by

            phones = []

            debited_user = self.get_user_by_name(debited_from_name)
            if debited_user and debited_user.phone:
                phones.append(debited_user.phone)

            added_by_user = self.get_user_by_email(added_by_email)
            if added_by_user and added_by_user.phone:
                if not debited_user or debited_user.email != added_by_user.email:
                    phones.append(added_by_user.phone)

            if phones:
                self.notify_financial_transaction(
                    transaction_type="expense",
                    amount=expense.amount,
                    subject=expense.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            self.logger.error(f"Erreur lors de la notification de dépense: {e}")

    def notify_internal_transfer(self, expense, income):
        try:
            debited_from_name = expense.debited_from  # Nom complet
            beneficiary_name = income.beneficiary  # Nom complet
            added_by_email = expense.added_by

            phones_set = set()

            debited_user = self.get_user_by_name(debited_from_name)
            if debited_user and debited_user.phone:
                phones_set.add(debited_user.phone)

            beneficiary_user = self.get_user_by_name(beneficiary_name)
            if beneficiary_user and beneficiary_user.phone:
                phones_set.add(beneficiary_user.phone)

            added_by_user = self.get_user_by_email(added_by_email)
            if added_by_user and added_by_user.phone:
                phones_set.add(added_by_user.phone)

            phones = list(phones_set)

            if phones:
                self.notify_financial_transaction(
                    transaction_type="transfer",
                    amount=expense.amount,
                    subject=expense.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            self.logger.error(f"Erreur lors de la notification de transfert interne: {e}")


notification_service = NotificationService()