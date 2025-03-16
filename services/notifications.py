import requests
import os
import logging
import time
import threading
import queue
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# File d'attente pour les notifications
notification_queue = queue.Queue()
# Verrou pour l'accès aux ressources partagées
lock = threading.Lock()


class NotificationService:
    def __init__(self):
        """Initialise le service de notification"""
        self.api_key = os.getenv('WHATSAPP_API_KEY', 'UDvABgmTtdWC')  # Clé API par défaut
        self.api_url = os.getenv('WHATSAPP_API_URL', 'http://api.textmebot.com/send.php')
        self.logger = logging.getLogger(__name__)

        # Démarrer le worker de traitement des notifications
        self._start_notification_worker()

    def _start_notification_worker(self):
        """Démarre un thread qui traite les notifications en file d'attente"""

        def worker():
            while True:
                try:
                    # Récupérer la prochaine notification
                    notification_data = notification_queue.get()
                    if notification_data is None:  # Signal pour arrêter le thread
                        break

                    recipient, message = notification_data

                    # Effectuer l'envoi réel
                    self._perform_send(recipient, message)

                    # Marquer la tâche comme terminée
                    notification_queue.task_done()

                    # Attendre 7 secondes avant de traiter la prochaine notification
                    time.sleep(7)
                except Exception as e:
                    self.logger.error(f"Erreur dans le worker de notifications: {str(e)}")
                    # Continuer malgré les erreurs

        # Démarrer le thread en arrière-plan
        notification_thread = threading.Thread(target=worker, daemon=True)
        notification_thread.start()

    def _perform_send(self, recipient_phone: str, message: str) -> bool:
        """Effectue l'envoi réel du SMS via l'API"""
        if not recipient_phone.startswith('+'):
            # Ajouter le code pays français si absent
            recipient_phone = '+33' + recipient_phone.lstrip('0')

        try:
            params = {
                'recipient': recipient_phone,
                'apikey': self.api_key,
                'text': message
            }

            response = requests.get(self.api_url, params=params)

            if response.status_code != 200:
                self.logger.error(f"Erreur lors de l'envoi de la notification: {response.text}")
                return False

            self.logger.info(f"Notification envoyée avec succès à {recipient_phone}")
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            return False

    def send_sms(self, recipient_phone: str, message: str) -> bool:
        """Ajoute un SMS à la file d'attente"""
        try:
            # Ajouter la notification à la file d'attente
            notification_queue.put((recipient_phone, message))
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout de la notification à la file d'attente: {str(e)}")
            return False

    def send_bulk_sms(self, recipient_phones: List[str], message: str) -> Dict[str, bool]:
        """Envoie un SMS à plusieurs destinataires"""
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
        """Envoie une notification concernant une tâche"""
        emoji_map = {
            "assignment": "📋",
            "validation": "✅",
            "dispute": "⚠️",
            "completed": "🎉",
            "reminder": "⏰",
            "deleted": "🗑️",
            "priority": "🔄",
            "transfer": "↔️",
            "task_taken": "👋"
        }

        emoji = emoji_map.get(task_type, "📌")
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")

        if task_type == "assignment":
            message = f"{emoji} La tâche '{task_subject}' vous a été assignée par {actor_name} le {current_time}"
        elif task_type == "validation":
            message = f"{emoji} La tâche '{task_subject}' a été marquée prête pour validation par {actor_name} le {current_time}"
        elif task_type == "dispute":
            message = f"{emoji} La tâche '{task_subject}' a été contestée par {actor_name} le {current_time}"
        elif task_type == "completed":
            message = f"{emoji} La tâche '{task_subject}' a été marquée comme terminée par {actor_name} le {current_time}"
        elif task_type == "reminder":
            message = f"{emoji} RAPPEL: La tâche '{task_subject}' requiert votre attention. {actor_name} vous a envoyé ce rappel le {current_time}"
        elif task_type == "deleted":
            message = f"{emoji} La tâche '{task_subject}' a été supprimée par {actor_name} le {current_time}"
        elif task_type == "priority":
            message = f"{emoji} La priorité de la tâche '{task_subject}' a été modifiée par {actor_name} le {current_time}"
        elif task_type == "transfer":
            message = f"{emoji} La tâche '{task_subject}' est en cours de transfert."
        elif task_type == "task_taken":
            message = f"{emoji} La tâche '{task_subject}' a été prise par {actor_name} le {current_time}"
        else:
            message = f"{emoji} Mise à jour de la tâche '{task_subject}' par {actor_name} le {current_time}"

        if additional_info:
            message += f"\n\n{additional_info}"

        return self.send_bulk_sms(phones, message)

    def format_financial_notification(self,
                                      transaction_type: str,
                                      amount: float,
                                      subject: str,
                                      actor: str) -> str:
        """Formate une notification financière"""
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")

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

        message += f"\nAjouté par {actor} le {current_time}"

        return "⚠️ Vérifie dans le Gsheet tréso des membres ⚠️\n"+message

    def notify_financial_transaction(self,
                                     transaction_type: str,
                                     amount: float,
                                     subject: str,
                                     actor: str,
                                     recipients: List[str]) -> Dict[str, bool]:
        """Notifie une transaction financière"""
        message = self.format_financial_notification(transaction_type, amount, subject, actor)
        return self.send_bulk_sms(recipients, message)

    def get_user_by_name(self, full_name: str):
        """Obtient un utilisateur par son nom complet"""
        try:
            from models.user import User
            parts = full_name.split(' ', 1)
            if len(parts) == 2:
                lname, fname = parts
                return User.query.filter_by(lname=lname, fname=fname).first()
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche de l'utilisateur par nom: {e}")
        return None

    def get_user_by_email(self, email: str):
        """Obtient un utilisateur par son email"""
        try:
            from models.user import User
            return User.query.filter_by(email=email).first()
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche de l'utilisateur par email: {e}")
        return None

    def notify_income(self, income):
        """Notifie une recette"""
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
        """Notifie une dépense"""
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
        """Notifie un transfert interne"""
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


# Instanciation du service de notification
notification_service = NotificationService()