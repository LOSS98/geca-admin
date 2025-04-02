import requests
import os
import logging
import time
import threading
import queue
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

notification_queue = queue.Queue()
lock = threading.Lock()


class NotificationService:
    DEBUG = True

    def __init__(self):
        self.api_key = os.getenv('WHATSAPP_API_KEY')
        self.api_url = os.getenv('WHATSAPP_API_URL')
        self.logger = logging.getLogger(__name__)
        self._start_notification_worker()

    def _start_notification_worker(self):
        def worker():
            while True:
                try:
                    notification_data = notification_queue.get()
                    if notification_data is None:
                        break

                    recipient, message = notification_data

                    if self.DEBUG:
                        print(f"DEBUG: Processing notification for recipient: {recipient}")

                    self._perform_send(recipient, message)
                    notification_queue.task_done()

                    if self.DEBUG:
                        print(f"DEBUG: Notification processing complete, waiting 7 seconds before next")

                    time.sleep(7)
                except Exception as e:
                    if self.DEBUG:
                        print(f"DEBUG: Error in notification worker: {str(e)}")
                        import traceback
                        print(f"DEBUG: Worker traceback: {traceback.format_exc()}")
                    self.logger.error(f"Error in notification worker: {str(e)}")

        notification_thread = threading.Thread(target=worker, daemon=True)
        notification_thread.start()

        if self.DEBUG:
            print("DEBUG: Notification worker thread started")

    def _perform_send(self, recipient_phone: str, message: str) -> bool:
        if not recipient_phone.startswith('+'):
            recipient_phone = '+33' + recipient_phone.lstrip('0')
            if self.DEBUG:
                print(f"DEBUG: Formatted phone number to {recipient_phone}")

        try:
            params = {
                'recipient': recipient_phone,
                'apikey': self.api_key,
                'text': message
            }

            if self.DEBUG:
                print(f"DEBUG: Sending API request to {self.api_url}")
                print(f"DEBUG: Message length: {len(message)} characters")

            response = requests.get(self.api_url, params=params)

            if response.status_code != 200:
                if self.DEBUG:
                    print(f"DEBUG: API request failed with status {response.status_code}")
                    print(f"DEBUG: Response text: {response.text}")
                self.logger.error(f"Error sending notification: {response.text}")
                return False

            if self.DEBUG:
                print(f"DEBUG: Notification sent successfully to {recipient_phone}")

            self.logger.info(f"Notification sent successfully to {recipient_phone}")
            return True
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Exception during send: {str(e)}")
                import traceback
                print(f"DEBUG: Send traceback: {traceback.format_exc()}")
            self.logger.error(f"Error sending notification: {str(e)}")
            return False

    def send_sms(self, recipient_phone: str, message: str) -> bool:
        try:
            if self.DEBUG:
                print(f"DEBUG: Queueing SMS for {recipient_phone}")
                print(f"DEBUG: Message preview: {message[:50]}...")

            notification_queue.put((recipient_phone, message))
            return True
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error queueing notification: {str(e)}")
            self.logger.error(f"Error adding notification to queue: {str(e)}")
            return False

    def send_bulk_sms(self, recipient_phones: List[str], message: str) -> Dict[str, bool]:
        results = {}

        if self.DEBUG:
            print(f"DEBUG: Sending bulk SMS to {len(recipient_phones)} recipients")

        for phone in recipient_phones:
            success = self.send_sms(phone, message)
            results[phone] = success

            if self.DEBUG:
                print(f"DEBUG: SMS to {phone} queued: {success}")

        return results

    def send_task_comment_notification(self,
                                       task_subject: str,
                                       comment_author: str,
                                       comment_text: str,
                                       assigned_users: List[str]) -> Dict[str, bool]:
        emoji = "💬"
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")

        if self.DEBUG:
            print(f"DEBUG: Preparing comment notification for task: {task_subject}")
            print(f"DEBUG: Comment by: {comment_author}")
            print(f"DEBUG: Assigned users: {assigned_users}")

        message = f"""*{emoji} Nouveau commentaire sur la tâche :*'{task_subject}'\n\n*Auteur :* {comment_author}\n*Commentaire :* {comment_text}\n*Date :* {current_time}\n\nConsultez le site du GECA pour plus de détails."""

        phones = []
        for full_name in assigned_users:
            if self.DEBUG:
                print(f"DEBUG: Looking up user by name: {full_name}")

            user = self.get_user_by_name(full_name)
            if user and user.phone:
                if self.DEBUG:
                    print(f"DEBUG: Found phone number for {full_name}: {user.phone}")
                phones.append(user.phone)
            elif self.DEBUG:
                print(f"DEBUG: No phone number found for {full_name}")

        if self.DEBUG:
            print(f"DEBUG: Found {len(phones)} phone numbers for notification")

        return self.send_bulk_sms(phones, message) if phones else {}

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
            "transfer": "↔️",
            "task_taken": "👋"
        }

        emoji = emoji_map.get(task_type, "📌")
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")

        if self.DEBUG:
            print(f"DEBUG: Creating task notification of type: {task_type}")
            print(f"DEBUG: Task subject: {task_subject}")
            print(f"DEBUG: Actor: {actor_name}")

        if task_type == "assignment":
            message = f"*{emoji} Nouvelle tâche : '{task_subject}'*"
        elif task_type == "validation":
            message = f"*{emoji} À valider : '{task_subject}'*"
        elif task_type == "dispute":
            message = f"*{emoji} Contestation : '{task_subject}'*"
        elif task_type == "completed":
            message = f"*{emoji} Terminée : '{task_subject}'*"
        elif task_type == "reminder":
            message = f"*{emoji} RAPPEL : '{task_subject}'*"
        elif task_type == "deleted":
            message = f"*{emoji} Supprimée : '{task_subject}'*"
        elif task_type == "priority":
            message = f"*{emoji} Changement de priorité : '{task_subject}'*"
        elif task_type == "transfer":
            message = f"*{emoji} Transferée : '{task_subject}'*"
        elif task_type == "task_taken":
            message = f"*{emoji} Task prise : '{task_subject}'*"
        else:
            message = f"*{emoji} Mise à jour : '{task_subject}'*"

        if additional_info:
            message += f"\n\n{additional_info}"

        if self.DEBUG:
            print(f"DEBUG: Message created, sending to {len(phones)} recipients")

        return self.send_bulk_sms(phones, message)

    def format_financial_notification(self,
                                      transaction_type: str,
                                      amount: float,
                                      subject: str,
                                      actor: str) -> str:
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")

        if self.DEBUG:
            print(f"DEBUG: Formatting financial notification of type: {transaction_type}")
            print(f"DEBUG: Amount: {amount:.2f}€, Subject: {subject}")

        if transaction_type == "income":
            emoji = "💰"
            message = f"*{emoji} RECETTE:* {amount:.2f}€ - {subject}"
        elif transaction_type == "expense":
            emoji = "💸"
            message = f"*{emoji} DÉPENSE:* {amount:.2f}€ - {subject}"
        elif transaction_type == "transfer":
            emoji = "🔄"
            message = f"*{emoji} TRANSFERT INTERNE:* {amount:.2f}€ - {subject}"
        else:
            emoji = "💶"
            message = f"*{emoji} TRANSACTION:* {amount:.2f}€ - {subject}"

        message += f"\nAjouté par {actor} le {current_time}"

        return "⚠️ Vérifie dans le Gsheet tréso des membres ⚠️\n" + message

    def notify_financial_transaction(self,
                                     transaction_type: str,
                                     amount: float,
                                     subject: str,
                                     actor: str,
                                     recipients: List[str]) -> Dict[str, bool]:
        if self.DEBUG:
            print(f"DEBUG: Notifying financial transaction to {len(recipients)} recipients")

        message = self.format_financial_notification(transaction_type, amount, subject, actor)
        return self.send_bulk_sms(recipients, message)

    def get_user_by_name(self, full_name: str):
        try:
            if self.DEBUG:
                print(f"DEBUG: Looking up user by name: {full_name}")

            from models.user import User
            parts = full_name.split(' ', 1)
            if len(parts) == 2:
                fname, lname = parts

                if self.DEBUG:
                    print(f"DEBUG: Parsed name - Last: {lname}, First: {fname}")

                user = User.query.filter_by(lname=lname, fname=fname).first()

                if self.DEBUG:
                    if user:
                        print(f"DEBUG: Found user with Email: {user.email}")
                    else:
                        print(f"DEBUG: No user found with name {full_name}")

                return user
            elif self.DEBUG:
                print(f"DEBUG: Invalid name format: {full_name}")
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error looking up user by name: {e}")
                import traceback
                print(f"DEBUG: Lookup traceback: {traceback.format_exc()}")
            self.logger.error(f"Error looking up user by name: {e}")
        return None

    def get_user_by_email(self, email: str):
        try:
            if self.DEBUG:
                print(f"DEBUG: Looking up user by email: {email}")

            from models.user import User
            user = User.query.filter_by(email=email).first()

            if self.DEBUG:
                if user:
                    print(f"DEBUG: Found user with Name: {user.fname} {user.lname}")
                else:
                    print(f"DEBUG: No user found with email {email}")

            return user
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error looking up user by email: {e}")
                import traceback
                print(f"DEBUG: Lookup traceback: {traceback.format_exc()}")
            self.logger.error(f"Error looking up user by email: {e}")
        return None

    def notify_income(self, income):
        try:
            if self.DEBUG:
                print(
                    f"DEBUG: Processing income notification for ID: {income.id if hasattr(income, 'id') else 'unknown'}")

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

            if self.DEBUG:
                print(f"DEBUG: Found {len(phones)} recipients for income notification")

            if phones:
                self.notify_financial_transaction(
                    transaction_type="income",
                    amount=income.amount,
                    subject=income.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error notifying income: {e}")
                import traceback
                print(f"DEBUG: Income notification traceback: {traceback.format_exc()}")
            self.logger.error(f"Error notifying income: {e}")

    def notify_expense(self, expense):
        try:
            if self.DEBUG:
                print(
                    f"DEBUG: Processing expense notification for ID: {expense.id if hasattr(expense, 'id') else 'unknown'}")

            debited_from_name = expense.debited_from
            added_by_email = expense.added_by

            phones = []

            debited_user = self.get_user_by_name(debited_from_name)
            if debited_user and debited_user.phone:
                phones.append(debited_user.phone)

            added_by_user = self.get_user_by_email(added_by_email)
            if added_by_user and added_by_user.phone:
                if not debited_user or debited_user.email != added_by_user.email:
                    phones.append(added_by_user.phone)

            if self.DEBUG:
                print(f"DEBUG: Found {len(phones)} recipients for expense notification")

            if phones:
                self.notify_financial_transaction(
                    transaction_type="expense",
                    amount=expense.amount,
                    subject=expense.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error notifying expense: {e}")
                import traceback
                print(f"DEBUG: Expense notification traceback: {traceback.format_exc()}")
            self.logger.error(f"Error notifying expense: {e}")

    def notify_internal_transfer(self, expense, income):
        try:
            if self.DEBUG:
                print(f"DEBUG: Processing internal transfer notification")

            debited_from_name = expense.debited_from
            beneficiary_name = income.beneficiary
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

            if self.DEBUG:
                print(f"DEBUG: Found {len(phones)} unique recipients for transfer notification")

            if phones:
                self.notify_financial_transaction(
                    transaction_type="transfer",
                    amount=expense.amount,
                    subject=expense.subject,
                    actor=added_by_email,
                    recipients=phones
                )
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error notifying internal transfer: {e}")
                import traceback
                print(f"DEBUG: Transfer notification traceback: {traceback.format_exc()}")
            self.logger.error(f"Error notifying internal transfer: {e}")

    def notify_blocked_user(self, user):
        try:
            if self.DEBUG:
                print(
                    f"DEBUG: Sending blocked user notification to: {user.email if hasattr(user, 'email') else 'unknown'}")

            if user and user.phone:
                self.send_sms(user.phone,
                              "🔐 Votre compte GECA a été bloqué.\nContactez l'administrateur pour plus d'informations.")
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error notifying blocked user: {e}")
                import traceback
                print(f"DEBUG: Block notification traceback: {traceback.format_exc()}")
            self.logger.error(f"Error notifying blocked user: {e}")

    def notify_unblocked_user(self, user):
        try:
            if self.DEBUG:
                print(
                    f"DEBUG: Sending unblocked user notification to: {user.email if hasattr(user, 'email') else 'unknown'}")

            if user and user.phone:
                self.send_sms(user.phone, "🔓 Votre compte GECA a été débloqué.\nVous pouvez vous reconnecter.")
        except Exception as e:
            if self.DEBUG:
                print(f"DEBUG: Error notifying unblocked user: {e}")
                import traceback
                print(f"DEBUG: Unblock notification traceback: {traceback.format_exc()}")
            self.logger.error(f"Error notifying unblocked user: {e}")


notification_service = NotificationService()