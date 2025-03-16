from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import enum
from typing import Dict, Optional, Any, List
import os
import json
from models.task_history import TaskHistory
from services.notifications import notification_service

from db import db

task_roles = db.Table('task_roles',
                      db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
                      db.Column('role_name', db.String(50), db.ForeignKey('roles.name'), primary_key=True)
                      )


class TaskState(enum.Enum):
    ASSIGNED = "assigned"
    DISPUTED = "disputed"
    TO_VALIDATED = "to_validated"
    DONE = "done"
    DELETED = "deleted"
    TRANSFER_PENDING = "transfer_pending"

    def __str__(self):
        return self.value


class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __str__(self):
        return self.value

    @staticmethod
    def get_display_name(priority):
        if priority == TaskPriority.LOW:
            return "Faible"
        elif priority == TaskPriority.MEDIUM:
            return "Moyenne"
        elif priority == TaskPriority.HIGH:
            return "Haute"
        return "Non définie"


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
    priority = db.Column(db.Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)

    transfer_from = db.Column(db.String(120), nullable=True)
    transfer_to = db.Column(db.String(120), nullable=True)

    target_roles = db.relationship('Role', secondary=task_roles, backref=db.backref('tasks', lazy='dynamic'))

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
        self.target_roles = []
        self.transfer_from = None
        self.transfer_to = None

        target_roles = data.get('target_roles', [])
        if target_roles:
            from models.role import Role
            for role_name in target_roles:
                role = Role.query.filter_by(name=role_name).first()
                if role:
                    self.target_roles.append(role)

        priority_str = data.get('priority', 'medium').lower()
        if priority_str == 'low' or priority_str == 'faible':
            self.priority = TaskPriority.LOW
        elif priority_str == 'high' or priority_str == 'haute':
            self.priority = TaskPriority.HIGH
        else:
            self.priority = TaskPriority.MEDIUM

    def add_target_role(self, role_name):
        """Ajoute un rôle cible à la tâche s'il n'existe pas déjà"""
        from models.role import Role
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)

        if role not in self.target_roles:
            self.target_roles.append(role)
            db.session.commit()

    def remove_target_role(self, role_name):
        """Supprime un rôle cible de la tâche"""
        from models.role import Role
        role = Role.query.filter_by(name=role_name).first()
        if role and role in self.target_roles:
            self.target_roles.remove(role)
            db.session.commit()

    def get_target_roles(self):
        """Renvoie la liste des noms de rôles cibles de la tâche"""
        return [role.name for role in self.target_roles]

    def is_available_for_user(self, user):
        """Vérifie si la tâche est disponible pour un utilisateur en fonction de ses rôles"""
        if not self.target_roles:
            return True

        for role in self.target_roles:
            if user.has_role(role.name):
                return True

        return False

    def release_task(self, user_email):
        """Libère une tâche pour la rendre disponible à nouveau, en préservant les restrictions de rôle"""
        from models.user import User
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return False, "Utilisateur non trouvé"

        if user not in self.assignees:
            return False, "Vous n'êtes pas assigné à cette tâche"

        is_task_assignable = len(self.target_roles) > 0 or len(self.assignees) == 0

        if not is_task_assignable:
            return False, "Cette tâche vous a été attribuée directement et ne peut pas être libérée"

        self.assignees.remove(user)

        if len(self.assignees) == 0 and self.state not in [TaskState.DONE, TaskState.DELETED]:
            self.state = TaskState.ASSIGNED

        from models.task_history import TaskHistory
        history_entry = TaskHistory(
            task_id=self.id,
            user_email=user_email,
            action="released"
        )
        history_entry.save_to_db()

        db.session.commit()

        try:
            self.notify_task_released(user_email)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return True, "Tâche libérée avec succès"

    def reassign(self, user_email, assignment_type, reassignment_data):
        """Permet à un assigné de réattribuer la tâche à d'autres personnes, équipes ou à tout le monde"""
        from models.user import User
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return False, "Utilisateur non trouvé"

        from models.task_history import TaskHistory
        history_entry = TaskHistory(
            task_id=self.id,
            user_email=user_email,
            action="reassigned"
        )
        history_entry.save_to_db()

        if user in self.assignees:
            self.assignees.remove(user)

        if assignment_type == 'users':
            new_assignee_emails = reassignment_data.get('assignees', [])

            for email in new_assignee_emails:
                new_user = User.query.filter_by(email=email).first()
                if new_user and new_user not in self.assignees:
                    self.assignees.append(new_user)

                    history_entry = TaskHistory(
                        task_id=self.id,
                        user_email=email,
                        action="assigned_by_peer"
                    )
                    history_entry.save_to_db()

        elif assignment_type == 'roles':
            self.target_roles = []
            role_names = reassignment_data.get('target_roles', [])

            from models.role import Role
            for role_name in role_names:
                role = Role.query.filter_by(name=role_name).first()
                if role:
                    self.target_roles.append(role)

            if len(self.assignees) == 0:
                self.state = TaskState.ASSIGNED

        elif assignment_type == 'all':
            self.target_roles = []

            if len(self.assignees) == 0:
                self.state = TaskState.ASSIGNED

        db.session.commit()

        if assignment_type == 'users' and len(self.assignees) > 0:
            try:
                self.notify_reassignment_by_peer(user_email)
            except Exception as e:
                print(f"Erreur lors de la notification: {str(e)}")

        return True, "Tâche réassignée avec succès"

    def transfer_ownership(self, new_owner_email):
        """Transfère la propriété d'une tâche à un autre utilisateur"""
        from models.user import User

        new_owner = User.query.filter_by(email=new_owner_email).first()

        if not new_owner:
            return False, "Utilisateur introuvable"

        history_entry = TaskHistory(
            task_id=self.id,
            user_email=new_owner_email,
            action="ownership_transferred"
        )
        history_entry.save_to_db()

        old_owner = self.assigned_by

        self.assigned_by = new_owner_email

        db.session.commit()

        try:
            self.notify_ownership_transfer(old_owner, new_owner_email)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return True, "Propriété transférée avec succès"

    def to_dict(self):
        time_info = self.get_time_info()

        from models.task_history import TaskHistory
        history = TaskHistory.query.filter_by(task_id=self.id).order_by(TaskHistory.timestamp.desc()).all()

        previous_assignees = []
        for entry in history:
            if entry.action in ["released", "unassigned"]:
                if entry.user_email not in previous_assignees:
                    previous_assignees.append(entry.user_email)

        return {
            'id': self.id,
            'assigned_by': self.assigned_by,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'subject': self.subject,
            'description': self.description,
            'state': str(self.state.value) if isinstance(self.state, TaskState) else str(self.state),
            'priority': str(self.priority.value) if isinstance(self.priority, TaskPriority) else str(self.priority),
            'priority_display': TaskPriority.get_display_name(self.priority),
            'assignees': [user.email for user in self.assignees],
            'target_roles': self.get_target_roles(),
            'delay': self.calculate_delay() if self.due_date and self.due_date < datetime.now() and self.state != TaskState.DONE else None,
            'time_info': time_info,
            'transfer_from': self.transfer_from,
            'transfer_to': self.transfer_to,
            'previous_assignees': previous_assignees,
            'history': [entry.to_dict() for entry in history[:10]]
        }

    def set_priority(self, priority_str):
        """Update the priority of the task"""
        priority_str = priority_str.lower()
        if priority_str == 'low' or priority_str == 'faible':
            self.priority = TaskPriority.LOW
        elif priority_str == 'high' or priority_str == 'haute':
            self.priority = TaskPriority.HIGH
        elif priority_str == 'medium' or priority_str == 'moyenne':
            self.priority = TaskPriority.MEDIUM
        else:
            return False

        db.session.commit()
        self.notify_priority_change()
        return True

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

    def get_time_info(self):
        """Get information about time remaining or delay"""
        now = datetime.now()

        if self.state == TaskState.DONE or self.state == TaskState.DELETED:
            return {
                'status': 'completed',
                'message': 'Tâche terminée'
            }

        if self.due_date < now:
            delay = now - self.due_date
            days = delay.days
            hours, remainder = divmod(delay.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            delay_str = ""
            if days > 0:
                delay_str += f"{days} jour{'s' if days > 1 else ''} "
            if hours > 0 or days > 0:
                delay_str += f"{hours} heure{'s' if hours > 1 else ''} "
            delay_str += f"{minutes} minute{'s' if minutes > 1 else ''}"

            return {
                'status': 'overdue',
                'delay': {
                    'days': days,
                    'hours': hours,
                    'minutes': minutes,
                    'total_minutes': days * 24 * 60 + hours * 60 + minutes
                },
                'message': f"Retard de {delay_str}"
            }

        time_remaining = self.due_date - now
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        time_str = ""
        if days > 0:
            time_str += f"{days} jour{'s' if days > 1 else ''} "
        if hours > 0 or days > 0:
            time_str += f"{hours} heure{'s' if hours > 1 else ''} "
        time_str += f"{minutes} minute{'s' if minutes > 1 else ''}"

        total_minutes = days * 24 * 60 + hours * 60 + minutes
        urgency = 'low'

        if self.priority == TaskPriority.HIGH:
            if total_minutes <= 24 * 60 * 2:
                urgency = 'critical'
            elif total_minutes <= 24 * 60 * 5:
                urgency = 'high'
            else:
                urgency = 'medium'
        elif self.priority == TaskPriority.MEDIUM:
            if total_minutes <= 60:
                urgency = 'critical'
            elif total_minutes <= 24 * 60:
                urgency = 'high'
            elif total_minutes <= 3 * 24 * 60:
                urgency = 'medium'
        else:
            if total_minutes <= 24 * 60 / 2:
                urgency = 'critical'
            elif total_minutes <= 24 * 60 / 4 * 3:
                urgency = 'high'
            elif total_minutes <= 24 * 60:
                urgency = 'medium'

        return {
            'status': 'upcoming',
            'remaining': {
                'days': days,
                'hours': hours,
                'minutes': minutes,
                'total_minutes': total_minutes
            },
            'urgency': urgency,
            'message': f"Temps restant: {time_str}"
        }

    def format_time_remaining(self):
        """Format time remaining or delay for human readability"""
        time_info = self.get_time_info()

        if time_info['status'] == 'completed':
            return "Tâche terminée"
        elif time_info['status'] == 'overdue':
            return time_info['message']
        else:
            urgent_msg = ""
            if time_info['urgency'] == 'critical':
                urgent_msg = " ⚠️ URGENT"
            elif time_info['urgency'] == 'high':
                urgent_msg = " ⚠️ Prioritaire"

            return f"{time_info['message']}{urgent_msg}"

    def get_priority_icon(self):
        """Get icon for priority level"""
        if self.priority == TaskPriority.HIGH:
            return "🔴"
        elif self.priority == TaskPriority.MEDIUM:
            return "🟠"
        else:
            return "🟢"

    def assign_to_users(self, user_emails: List[str]):
        """Assign the task to multiple users"""
        from models.user import User
        for email in user_emails:
            user = User.query.filter_by(email=email).first()
            if user and user not in self.assignees:
                self.assignees.append(user)

        # Assurez-vous que les changements sont enregistrés dans la base de données
        db.session.add(self)
        db.session.commit()

        # Optionnel: Notifier les utilisateurs de l'assignation
        self.notify_assignment()

        # Log pour le débogage
        print(f"Task {self.id} assigned to users: {[user.email for user in self.assignees]}")
        return True

    def assign_to_role(self, role: str):
        """Assign the task to all users with a specific role"""
        from models.user import User
        from models.role import Role
        users = User.get_users_by_role(role)
        for user in users:
            if user not in self.assignees:
                self.assignees.append(user)
        db.session.add(self)
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
        self.notify_task_completed()

    def delete_task(self):
        """Mark the task as deleted"""
        self.state = TaskState.DELETED
        db.session.commit()
        self.notify_task_deleted()

    def remove_assignee(self, user_email: str):
        """Remove a specific assignee from the task"""
        from models.user import User
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

    def request_transfer(self, current_user_email: str, new_user_email: str):
        """Demande de céder la tâche à un autre utilisateur"""
        from models.user import User
        current_user = User.query.filter_by(email=current_user_email).first()
        new_user = User.query.filter_by(email=new_user_email).first()

        if not current_user or not new_user:
            return False, "Utilisateur non trouvé"

        if current_user not in self.assignees:
            return False, "Vous n'êtes pas assigné à cette tâche"

        self.transfer_from = current_user_email
        self.transfer_to = new_user_email

        self.state = TaskState.TRANSFER_PENDING
        db.session.commit()

        self.notify_transfer_request(current_user_email, new_user_email)

        return True, "Demande de cession envoyée avec succès"

    def approve_transfer(self, approver_email: str):
        """Approuver la demande de cession de tâche"""
        if self.assigned_by != approver_email:
            return False, "Vous n'êtes pas autorisé à approuver cette cession"

        if self.state != TaskState.TRANSFER_PENDING:
            return False, "Cette tâche n'est pas en attente de cession"

        from models.user import User
        current_assignee = User.query.filter_by(email=self.transfer_from).first()
        new_assignee = User.query.filter_by(email=self.transfer_to).first()

        if not current_assignee or not new_assignee:
            return False, "Utilisateur non trouvé"

        if current_assignee in self.assignees:
            self.assignees.remove(current_assignee)

        if new_assignee not in self.assignees:
            self.assignees.append(new_assignee)

        self.state = TaskState.ASSIGNED
        db.session.commit()

        self.notify_transfer_approved(self.transfer_from, self.transfer_to)

        self.transfer_from = None
        self.transfer_to = None
        db.session.commit()

        return True, "Cession approuvée avec succès"

    def reject_transfer(self, approver_email: str):
        """Rejeter la demande de cession de tâche"""
        if self.assigned_by != approver_email:
            return False, "Vous n'êtes pas autorisé à rejeter cette cession"

        if self.state != TaskState.TRANSFER_PENDING:
            return False, "Cette tâche n'est pas en attente de cession"

        self.state = TaskState.ASSIGNED

        self.notify_transfer_rejected(self.transfer_from, self.transfer_to)

        self.transfer_from = None
        self.transfer_to = None
        db.session.commit()

        return True, "Cession rejetée"

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

    def validate_task(self, user_email: str):
        """Validate a task and mark it as done"""
        if self.state == TaskState.TO_VALIDATED:
            self.state = TaskState.DONE
            db.session.commit()
            self.notify_task_validated(user_email)

    def reject_validation(self):
        """Reject a validation request and set the task back to assigned state"""
        if self.state == TaskState.TO_VALIDATED:
            self.state = TaskState.ASSIGNED
            db.session.commit()
            self.notify_validation_rejected()

    # Méthodes de notification
    def notify_assignment(self):
        """Notify all assignees about the new task"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("assignment", self.assigned_by)

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="assignment",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_dispute(self, user_email: str):
        """Notify the assigner about a disputed task"""
        from models.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            return

        formatted_message = self._format_message("dispute", user_email)

        notification_service.send_task_notification(
            phones=[assigner.phone],
            task_subject=self.subject,
            task_type="dispute",
            actor_name=self._get_user_full_name(user_email),
            additional_info=formatted_message
        )

    def notify_to_validate(self, user_email: str):
        """Notify the assigner that a task is ready to be validated"""
        from models.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            return

        formatted_message = self._format_message("validation_request", user_email)

        notification_service.send_task_notification(
            phones=[assigner.phone],
            task_subject=self.subject,
            task_type="validation",
            actor_name=self._get_user_full_name(user_email),
            additional_info=formatted_message
        )

    def notify_task_reopened(self):
        """Notify all assignees that a task has been reopened"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("task_reopened", self.assigned_by,
                                                     "Cette tâche a été rouverte et nécessite à nouveau votre attention.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="assignment",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_validation_cancelled(self):
        """Notify all assignees that validation has been cancelled"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("validation_cancelled", self.assigned_by,
                                                     "Vous devez continuer à travailler sur cette tâche.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="validation",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_dispute_rejected(self):
        """Notifier tous les assignés que leur contestation a été rejetée"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("dispute_rejected", self.assigned_by,
                                                     "Vous devez continuer à travailler sur cette tâche malgré la contestation.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="dispute",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_validation_rejected(self):
        """Notifier tous les assignés que leur demande de validation a été rejetée"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("validation_rejected", self.assigned_by,
                                                     "La tâche n'est pas considérée comme terminée. Veuillez apporter les corrections nécessaires.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="validation",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_task_completed(self):
        """Notifier tous les assignés que la tâche a été marquée comme terminée"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("task_completed", self.assigned_by,
                                                     "Félicitations ! Cette tâche a été clôturée avec succès.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="completed",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_task_deleted(self):
        """Notifier tous les assignés que la tâche a été supprimée"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones = []
                for user in self.assignees:
                    if hasattr(user, 'phone') and user.phone:
                        phones.append(user.phone)

                if phones:
                    formatted_message = self._format_message("task_deleted", self.assigned_by,
                                                             "Cette tâche a été supprimée et ne nécessite plus votre attention.")

                    notification_service.send_task_notification(
                        phones=phones,
                        task_subject=self.subject,
                        task_type="deleted",
                        actor_name=self._get_user_full_name(self.assigned_by),
                        additional_info=formatted_message
                    )

    def notify_priority_change(self):
        """Notify all assignees about priority change"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("priority_changed", self.assigned_by,
                                                     f"La priorité a été changée à {TaskPriority.get_display_name(self.priority)}")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="priority",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_transfer_request(self, from_email: str, to_email: str):
        """Notifier le créateur qu'un utilisateur souhaite céder sa tâche"""
        from models.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not assigner or not current_user or not new_user or not assigner.phone:
            return

        current_name = f"{current_user.fname} {current_user.lname}"
        new_name = f"{new_user.fname} {new_user.lname}"

        formatted_message = self._format_message("transfer_request", from_email,
                                                 f"{current_name} souhaite céder cette tâche à {new_name}. Veuillez approuver ou rejeter cette demande.")

        notification_service.send_task_notification(
            phones=[assigner.phone],
            task_subject=self.subject,
            task_type="transfer",
            actor_name=self._get_user_full_name(from_email),
            additional_info=formatted_message
        )

    def notify_transfer_approved(self, from_email: str, to_email: str):
        """Notifier les deux utilisateurs que la cession a été approuvée"""
        from models.user import User
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not current_user or not new_user:
            return

        if current_user.phone:
            new_name = f"{new_user.fname} {new_user.lname}"
            formatted_message = self._format_message("transfer_approved", self.assigned_by,
                                                     f"Votre demande de céder cette tâche à {new_name} a été approuvée.")

            notification_service.send_task_notification(
                phones=[current_user.phone],
                task_subject=self.subject,
                task_type="transfer",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

        if new_user.phone:
            current_name = f"{current_user.fname} {current_user.lname}"
            formatted_message = self._format_message("transfer_approved_new", self.assigned_by,
                                                     f"Vous avez reçu cette tâche de {current_name}. La cession a été approuvée.")

            notification_service.send_task_notification(
                phones=[new_user.phone],
                task_subject=self.subject,
                task_type="transfer",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_transfer_rejected(self, from_email: str, to_email: str):
        """Notifier l'utilisateur que sa demande de cession a été rejetée"""
        from models.user import User
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not current_user or not current_user.phone:
            return

        new_name = f"{new_user.fname} {new_user.lname}" if new_user else to_email
        formatted_message = self._format_message("transfer_rejected", self.assigned_by,
                                                 f"Votre demande de céder cette tâche à {new_name} a été rejetée. Vous êtes toujours responsable de cette tâche.")

        notification_service.send_task_notification(
            phones=[current_user.phone],
            task_subject=self.subject,
            task_type="transfer",
            actor_name=self._get_user_full_name(self.assigned_by),
            additional_info=formatted_message
        )

    def notify_task_validated(self, validator_email):
        """Notifier tous les assignés que la tâche a été validée"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("task_validated", validator_email,
                                                     "Félicitations ! Votre travail sur cette tâche a été validé.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="completed",
                actor_name=self._get_user_full_name(validator_email),
                additional_info=formatted_message
            )

    def send_reminder(self):
        """Send a reminder to all assignees"""
        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("reminder", self.assigned_by,
                                                     "Ce rappel a été envoyé par le créateur de la tâche.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="reminder",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_task_released(self, user_email):
        """Notifier le créateur de la tâche qu'un utilisateur a libéré la tâche"""
        from models.user import User
        creator = User.query.filter_by(email=self.assigned_by).first()
        releaser = User.query.filter_by(email=user_email).first()

        if not creator or not releaser or not creator.phone:
            return

        releaser_name = f"{releaser.fname} {releaser.lname}"
        formatted_message = self._format_message("transfer", user_email,
                                                 f"La tâche a été libérée par {releaser_name} et est maintenant disponible pour d'autres personnes.")

        notification_service.send_task_notification(
            phones=[creator.phone],
            task_subject=self.subject,
            task_type="transfer",
            actor_name=releaser_name,
            additional_info=formatted_message
        )

    def notify_task_reassigned(self, new_assignees):
        """Notifier les nouveaux assignés qu'ils ont été assignés à cette tâche"""
        phones = []
        for user in new_assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("assignment", self.assigned_by,
                                                     "Vous avez été réassigné à cette tâche par le créateur.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="assignment",
                actor_name=self._get_user_full_name(self.assigned_by),
                additional_info=formatted_message
            )

    def notify_ownership_transfer(self, old_owner, new_owner_email):
        """Notifier le nouveau propriétaire du transfert de propriété"""
        from models.user import User
        new_owner = User.query.filter_by(email=new_owner_email).first()
        if not new_owner or not new_owner.phone:
            return

        formatted_message = self._format_message("transfer", old_owner,
                                                 f"La propriété de la tâche vous a été transférée par {old_owner}. Vous êtes maintenant responsable de cette tâche et pouvez la gérer.")

        notification_service.send_task_notification(
            phones=[new_owner.phone],
            task_subject=self.subject,
            task_type="transfer",
            actor_name=old_owner,
            additional_info=formatted_message
        )

    def notify_reassignment_by_peer(self, reassigner_email):
        """Notifie les nouveaux assignés qu'un pair leur a assigné la tâche"""
        from models.user import User
        reassigner = User.query.filter_by(email=reassigner_email).first()
        reassigner_name = f"{reassigner.fname} {reassigner.lname}" if reassigner else reassigner_email

        phones = []
        for user in self.assignees:
            if hasattr(user, 'phone') and user.phone:
                phones.append(user.phone)

        if phones:
            formatted_message = self._format_message("assignment", reassigner_email,
                                                     f"Cette tâche vous a été assignée par {reassigner_name}, qui était précédemment assigné à cette tâche.")

            notification_service.send_task_notification(
                phones=phones,
                task_subject=self.subject,
                task_type="assignment",
                actor_name=reassigner_name,
                additional_info=formatted_message
            )

    def _get_user_full_name(self, email):
        """Get the full name of a user by email"""
        from models.user import User
        user = User.query.filter_by(email=email).first()
        if user:
            return f"{user.fname} {user.lname}"
        return email

    def _format_message(self, message_type, actor_email, additional_info=None):
        """Format a notification message based on the specific message type"""
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M")
        actor_name = self._get_user_full_name(actor_email)

        # Récupérer les informations de temps pour les inclure dans les notifications
        time_info_str = self.format_time_remaining()

        # Récupérer l'icône de priorité
        priority_icon = self.get_priority_icon()
        priority_text = TaskPriority.get_display_name(self.priority)

        # Construire le message complet
        message = f"{priority_icon} La tâche *'{self.subject}'* "

        if message_type == "assignment":
            message += f"vous a été assignée par {actor_name} le {current_time}"
        elif message_type == "dispute":
            message += f"a été contestée par {actor_name} le {current_time}"
        elif message_type == "validation_request":
            message += f"a été marquée prête pour validation par {actor_name} le {current_time}"
        elif message_type == "task_reopened":
            message += f"a été rouverte par {actor_name} le {current_time}"
        elif message_type == "validation_cancelled":
            message += f"a eu sa demande de validation annulée par {actor_name} le {current_time}"
        elif message_type == "dispute_rejected":
            message += f"a eu sa contestation rejetée par {actor_name} le {current_time}"
        elif message_type == "validation_rejected":
            message += f"a eu sa validation rejetée par {actor_name} le {current_time}"
        elif message_type == "task_completed":
            message += f"a été marquée comme terminée par {actor_name} le {current_time}"
        elif message_type == "task_deleted":
            message += f"a été supprimée par {actor_name} le {current_time}"
        elif message_type == "task_validated":
            message += f"a été validée par {actor_name} le {current_time}"
        elif message_type == "priority_changed":
            message += f"a eu sa priorité changée à {priority_text} par {actor_name} le {current_time}"
        elif message_type == "reminder":
            message += f"requiert votre attention. {actor_name} vous a envoyé ce rappel le {current_time}"
        elif message_type == "transfer_request":
            message += f"est en attente de cession. {actor_name} a fait cette demande le {current_time}"
        elif message_type == "transfer_approved":
            message += f"a eu sa demande de cession approuvée par {actor_name} le {current_time}"
        elif message_type == "transfer_approved_new":
            message += f"vous a été cédée et approuvée par {actor_name} le {current_time}"
        elif message_type == "transfer_rejected":
            message += f"a eu sa demande de cession rejetée par {actor_name} le {current_time}"
        elif message_type == "transfer":
            message += f"a été transférée. {actor_name} est impliqué dans ce transfert le {current_time}"
        else:
            message += f"a été mise à jour par {actor_name} le {current_time}"

        # Ajouter les détails de la tâche
        message += f"\n*Détail de la tâche :*\n{self.description or 'Pas de description fournie'}"

        # Ajouter l'information de priorité
        message += f"\n\n*Priorité:* {priority_text}"

        # Ajouter l'information de temps si ce n'est pas une tâche terminée ou supprimée
        if message_type not in ["task_completed", "task_deleted", "task_validated"]:
            message += f"\n*{time_info_str}*"

        # Ajouter la date d'échéance
        due_date_str = self.due_date.strftime("%d/%m/%Y à %H:%M") if self.due_date else "Non définie"
        message += f"\n\n*Date d'échéance:* {due_date_str}"

        # Ajouter des informations supplémentaires si fournies
        if additional_info:
            message += f"\n\n{additional_info}"

        return message

    @staticmethod
    def get_tasks_for_user(user_email: str):
        """Get all non-deleted tasks assigned to a user"""
        from models.user import User
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f"User with email {user_email} not found")
            return []

        # Utiliser une requête directe avec un join pour s'assurer de récupérer toutes les tâches
        tasks = Task.query.join(
            task_user_association,
            Task.id == task_user_association.c.task_id
        ).filter(
            task_user_association.c.user_email == user_email,
            Task.state != TaskState.DELETED
        ).all()

        # Log pour le débogage
        print(f"Found {len(tasks)} tasks for user {user_email}")

        # Alternative si la méthode ci-dessus ne fonctionne pas correctement
        if not tasks:
            print("Using alternative method to find tasks")
            tasks = []
            all_tasks = Task.query.filter(Task.state != TaskState.DELETED).all()
            for task in all_tasks:
                if user in task.assignees:
                    tasks.append(task)
            print(f"Alternative method found {len(tasks)} tasks")

        return tasks

    @staticmethod
    def get_assigned_tasks_by_user(user_email: str):
        """Get all tasks assigned by a specific user"""
        return Task.query.filter_by(assigned_by=user_email).filter(Task.state != TaskState.DELETED).all()