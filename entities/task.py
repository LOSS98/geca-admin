from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import enum
from typing import Dict, Optional, Any, List
import requests
import os
import json

from db import db


class TaskState(enum.Enum):
    ASSIGNED = "assigned"
    DISPUTED = "disputed"
    TO_VALIDATED = "to_validated"
    DONE = "done"
    DELETED = "deleted"

    def __str__(self):
        return self.value


# Association table for many-to-many relationship between Task and User
task_user_association = db.Table(
    'task_user_association',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('user_email', db.String(120), db.ForeignKey('users.email'), primary_key=True)
)


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    assigned_by = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=False)
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    start_date = db.Column(db.DateTime, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    state = db.Column(db.Enum(TaskState), nullable=False, default=TaskState.ASSIGNED)

    # Relationships
    assigner = db.relationship('User', foreign_keys=[assigned_by], backref='assigned_tasks')
    assignees = db.relationship('User', secondary=task_user_association, backref='tasks')

    def __init__(self, data: Dict[str, Any]):
        self.assigned_by = data.get('assigned_by')
        self.assigned_at = datetime.now()
        self.start_date = data.get('start_date')
        self.due_date = data.get('due_date')
        self.subject = data.get('subject')
        self.description = data.get('description')
        self.state = TaskState.ASSIGNED

    def to_dict(self):
        return {
            'id': self.id,
            'assigned_by': self.assigned_by,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'subject': self.subject,
            'description': self.description,
            'state': str(self.state.value) if isinstance(self.state, TaskState) else str(self.state),
            'assignees': [user.email for user in self.assignees],
            'delay': self.calculate_delay() if self.due_date and self.due_date < datetime.now() and self.state != TaskState.DONE else None
        }

    def calculate_delay(self):
        """Calculate the delay in days, hours, and minutes if the task is overdue"""
        if self.due_date > datetime.now() or self.state == TaskState.DONE:
            return None

        delay = datetime.now() - self.due_date
        days = delay.days
        hours, remainder = divmod(delay.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'total_minutes': days * 24 * 60 + hours * 60 + minutes
        }

    def assign_to_users(self, user_emails: List[str]):
        """Assign the task to multiple users"""
        from entities.user import User
        for email in user_emails:
            user = User.query.filter_by(email=email).first()
            if user and user not in self.assignees:
                self.assignees.append(user)
        db.session.add(self)  # Make sure the task is added to the session
        db.session.commit()
        self.notify_assignment()

    def assign_to_role(self, role: str):
        """Assign the task to all users with a specific role"""
        from entities.user import User
        users = User.query.filter_by(role=role).all()
        for user in users:
            if user not in self.assignees:
                self.assignees.append(user)
        db.session.add(self)  # Make sure the task is added to the session
        db.session.commit()
        self.notify_assignment()

    def dispute(self, user_email: str):
        """Mark the task as disputed by a user"""
        self.state = TaskState.DISPUTED
        db.session.commit()
        self.notify_dispute(user_email)

    def mark_to_validate(self, user_email: str):
        """Mark the task as to be validated"""
        self.state = TaskState.TO_VALIDATED
        db.session.commit()
        self.notify_to_validate(user_email)

    def mark_as_done(self):
        """Mark the task as done"""
        self.state = TaskState.DONE
        db.session.commit()

    def delete_task(self):
        """Mark the task as deleted"""
        self.state = TaskState.DELETED
        db.session.commit()

    def remove_assignee(self, user_email: str):
        """Remove a specific assignee from the task"""
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if user and user in self.assignees:
            self.assignees.remove(user)
            db.session.commit()

    def reject_dispute(self):
        """Reject the dispute and set the task back to assigned state"""
        self.state = TaskState.ASSIGNED
        db.session.commit()
        self.notify_dispute_rejected()

    def save_to_db(self):
        """Save the task to the database"""
        db.session.add(self)
        db.session.commit()

    def notify_assignment(self):
        """Notify all assignees about the new task"""
        api_key = "UDvABgmTtdWC"
        base_url = "http://api.textmebot.com/send.php"

        message = f"Vous avez été assigné à une nouvelle tâche: {self.subject}"

        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            # Format phone number (ensure it has country code)
            phone = user.phone
            if not phone.startswith('+'):
                # Add French country code if missing
                phone = '+33' + phone.lstrip('0')

            try:
                # Construct URL with parameters
                params = {
                    'recipient': phone,
                    'apikey': api_key,
                    'text': message
                }

                # Make GET request
                response = requests.get(base_url, params=params)

                # Check response
                if response.status_code != 200:
                    print(f"Error sending SMS notification: {response.text}")
            except Exception as e:
                print(f"Error sending notification: {str(e)}")

    def notify_dispute(self, user_email: str):
        """Notify the assigner about a disputed task"""
        api_key = "UDvABgmTtdWC"
        base_url = "http://api.textmebot.com/send.php"

        # Get the assigner
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            print(f"Assigner {self.assigned_by} has no phone number, skipping notification")
            return

        # Format phone number
        phone = assigner.phone
        if not phone.startswith('+'):
            phone = '+33' + phone.lstrip('0')

        message = f"La tâche '{self.subject}' a été contestée par {user_email}"

        try:
            params = {
                'recipient': phone,
                'apikey': api_key,
                'text': message
            }

            response = requests.get(base_url, params=params)

            if response.status_code != 200:
                print(f"Error sending SMS notification: {response.text}")
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    def notify_to_validate(self, user_email: str):
        """Notify the assigner that a task is ready to be validated"""
        api_key = "UDvABgmTtdWC"
        base_url = "http://api.textmebot.com/send.php"

        # Get the assigner
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            print(f"Assigner {self.assigned_by} has no phone number, skipping notification")
            return

        # Format phone number
        phone = assigner.phone
        if not phone.startswith('+'):
            phone = '+33' + phone.lstrip('0')

        message = f"La tâche '{self.subject}' est prête à être validée par {user_email}"

        try:
            params = {
                'recipient': phone,
                'apikey': api_key,
                'text': message
            }

            response = requests.get(base_url, params=params)

            if response.status_code != 200:
                print(f"Error sending SMS notification: {response.text}")
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    def reopen_task(self):
        """Reopen a completed task (set it back to assigned)"""
        if self.state == TaskState.DONE:
            self.state = TaskState.ASSIGNED
            db.session.commit()
            self.notify_task_reopened()

    def cancel_validation(self):
        """Cancel a to-be-validated task (set it back to assigned)"""
        if self.state == TaskState.TO_VALIDATED:
            self.state = TaskState.ASSIGNED
            db.session.commit()
            self.notify_validation_cancelled()

    def notify_task_reopened(self):
        """Notify all assignees that a task has been reopened"""
        api_url = os.getenv('NOTIFICATION_API_URL', 'https://api.geca.fr/send')
        message = f"La tâche '{self.subject}' a été réouverte par {self.assigned_by}"

        assignee_emails = [user.email for user in self.assignees]

        try:
            requests.post(api_url, json={
                'message': message,
                'users': assignee_emails
            })
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    def reject_validation(self):
        """Reject a validation request and set the task back to assigned state"""
        if self.state == TaskState.TO_VALIDATED:
            self.state = TaskState.ASSIGNED
            db.session.commit()
            self.notify_validation_rejected()

    def notify_validation_rejected(self):
        """Notify all assignees that their validation request was rejected"""
        api_url = os.getenv('NOTIFICATION_API_URL', 'https://api.geca.fr/send')
        message = f"La demande de validation pour la tâche '{self.subject}' a été refusée par {self.assigned_by}"

        assignee_emails = [user.email for user in self.assignees]

        try:
            requests.post(api_url, json={
                'message': message,
                'users': assignee_emails
            })
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    def get_tasks_for_user(user_email: str):
        """Get all non-deleted tasks assigned to a user"""
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return []

        # Use a direct query with a join to ensure we get all tasks
        tasks = Task.query.join(
            task_user_association,
            Task.id == task_user_association.c.task_id
        ).filter(
            task_user_association.c.user_email == user_email,
            Task.state != TaskState.DELETED
        ).all()

        return tasks

    def notify_validation_cancelled(self):
        """Notify all assignees that validation has been cancelled"""
        api_url = os.getenv('NOTIFICATION_API_URL', 'https://api.geca.fr/send')
        message = f"La demande de validation pour la tâche '{self.subject}' a été annulée"

        assignee_emails = [user.email for user in self.assignees]

        try:
            requests.post(api_url, json={
                'message': message,
                'users': assignee_emails
            })
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

    def get_assigned_tasks_by_user(user_email: str):
        """Get all tasks assigned by a specific user"""
        return Task.query.filter_by(assigned_by=user_email).filter(Task.state != TaskState.DELETED).all()