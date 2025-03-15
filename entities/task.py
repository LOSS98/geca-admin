from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import enum
from typing import Dict, Optional, Any, List
import requests
import os
import json
from entities.task_history import TaskHistory


from db import db

# Création d'une table d'association task_roles
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
    TRANSFER_PENDING = "transfer_pending"  # État pour les cessions en attente

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
    priority = db.Column(db.Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)

    # Colonnes pour la cession de tâches
    transfer_from = db.Column(db.String(120), nullable=True)
    transfer_to = db.Column(db.String(120), nullable=True)

    # Relation avec les rôles cibles
    target_roles = db.relationship('Role', secondary=task_roles, backref=db.backref('tasks', lazy='dynamic'))

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
        self.target_roles = []
        self.transfer_from = None
        self.transfer_to = None

        # Ajouter les rôles cibles si fournis
        target_roles = data.get('target_roles', [])
        if target_roles:
            from entities.role import Role
            for role_name in target_roles:
                role = Role.query.filter_by(name=role_name).first()
                if role:
                    self.target_roles.append(role)

        # Définir la priorité (par défaut: MEDIUM)
        priority_str = data.get('priority', 'medium').lower()
        if priority_str == 'low' or priority_str == 'faible':
            self.priority = TaskPriority.LOW
        elif priority_str == 'high' or priority_str == 'haute':
            self.priority = TaskPriority.HIGH
        else:
            self.priority = TaskPriority.MEDIUM

    # Méthodes de gestion des rôles cibles
    def add_target_role(self, role_name):
        """Ajoute un rôle cible à la tâche s'il n'existe pas déjà"""
        from entities.role import Role
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)

        if role not in self.target_roles:
            self.target_roles.append(role)
            db.session.commit()

    def remove_target_role(self, role_name):
        """Supprime un rôle cible de la tâche"""
        from entities.role import Role
        role = Role.query.filter_by(name=role_name).first()
        if role and role in self.target_roles:
            self.target_roles.remove(role)
            db.session.commit()

    def get_target_roles(self):
        """Renvoie la liste des noms de rôles cibles de la tâche"""
        return [role.name for role in self.target_roles]

    def is_available_for_user(self, user):
        """Vérifie si la tâche est disponible pour un utilisateur en fonction de ses rôles"""
        # Si la tâche n'a pas de rôles cibles, elle est disponible pour tous
        if not self.target_roles:
            return True

        # Si la tâche a des rôles cibles, vérifier si l'utilisateur a au moins un de ces rôles
        for role in self.target_roles:
            if user.has_role(role.name):
                return True

        return False

    def release_task(self, user_email):
        """Libère une tâche pour la rendre disponible à nouveau"""
        from entities.user import User
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return False, "Utilisateur non trouvé"

        if user not in self.assignees:
            return False, "Vous n'êtes pas assigné à cette tâche"

        # Retirer l'utilisateur des assignés
        self.assignees.remove(user)

        # Si la tâche n'a plus d'assignés et n'est pas en état "done" ou "deleted"
        if len(self.assignees) == 0 and self.state not in [TaskState.DONE, TaskState.DELETED]:
            # Remettre la tâche à l'état "assigned" (disponible)
            self.state = TaskState.ASSIGNED

        # Enregistrer l'action dans l'historique
        history_entry = TaskHistory(
            task_id=self.id,
            user_email=user_email,
            action="released"
        )
        history_entry.save_to_db()

        # Sauvegarder les changements
        db.session.commit()

        # Notifier le créateur
        try:
            self.notify_task_released(user_email)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return True, "Tâche libérée avec succès"

    # Méthode pour réassigner une tâche
    def reassign_task(self, new_assignee_emails):
        """Réassigne la tâche à de nouveaux utilisateurs"""
        if not new_assignee_emails:
            return False, "Aucun destinataire spécifié"

        # Enregistrer l'action dans l'historique pour chaque assigné actuel
        for user in self.assignees:
            history_entry = TaskHistory(
                task_id=self.id,
                user_email=user.email,
                action="unassigned"
            )
            history_entry.save_to_db()

        # Supprimer les assignations actuelles
        self.assignees = []

        # Ajouter les nouveaux assignés
        from entities.user import User
        new_assignees = []

        for email in new_assignee_emails:
            user = User.query.filter_by(email=email).first()
            if user:
                self.assignees.append(user)
                new_assignees.append(user)

                # Enregistrer l'action dans l'historique
                history_entry = TaskHistory(
                    task_id=self.id,
                    user_email=user.email,
                    action="reassigned"
                )
                history_entry.save_to_db()

        # Remettre l'état à "assigned" si ce n'est pas déjà le cas
        if self.state not in [TaskState.DONE, TaskState.DELETED]:
            self.state = TaskState.ASSIGNED

        # Sauvegarder les changements
        db.session.commit()

        # Notifier les nouveaux assignés
        try:
            self.notify_task_reassigned(new_assignees)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return True, "Tâche réassignée avec succès"

    # Méthode pour transférer la propriété d'une tâche
    def transfer_ownership(self, new_owner_email):
        """Transfère la propriété d'une tâche à un autre utilisateur"""
        from entities.user import User

        # Vérifier que le nouvel utilisateur existe
        new_owner = User.query.filter_by(email=new_owner_email).first()

        if not new_owner:
            return False, "Utilisateur introuvable"

        # Enregistrer l'action dans l'historique
        history_entry = TaskHistory(
            task_id=self.id,
            user_email=new_owner_email,
            action="ownership_transferred"
        )
        history_entry.save_to_db()

        # Sauvegarder l'ancien propriétaire pour la notification
        old_owner = self.assigned_by

        # Mettre à jour le propriétaire
        self.assigned_by = new_owner_email

        # Sauvegarder les changements
        db.session.commit()

        # Notifier le nouveau propriétaire
        try:
            self.notify_ownership_transfer(old_owner, new_owner_email)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return True, "Propriété transférée avec succès"

    # Mettre à jour la méthode to_dict pour inclure l'historique
    def to_dict(self):
        time_info = self.get_time_info()

        # Récupérer l'historique des assignations
        from entities.task_history import TaskHistory
        history = TaskHistory.query.filter_by(task_id=self.id).order_by(TaskHistory.timestamp.desc()).all()

        # Récupérer les utilisateurs précédemment assignés
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
            'history': [entry.to_dict() for entry in history[:10]]  # Limiter à 10 entrées pour la performance
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
            # Par défaut, on garde la priorité actuelle
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

        # Si la tâche est terminée, pas besoin d'information sur le temps
        if self.state == TaskState.DONE or self.state == TaskState.DELETED:
            return {
                'status': 'completed',
                'message': 'Tâche terminée'
            }

        # Si la date d'échéance est passée, calculer le retard
        if self.due_date < now:
            delay = now - self.due_date
            days = delay.days
            hours, remainder = divmod(delay.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            delay_str = ""
            if days > 0:
                delay_str += f"{days} jour{'s' if days > 1 else ''} "
            if hours > 0 or days > 0:  # Inclure les heures si on a des jours ou des heures
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

        # Sinon, calculer le temps restant
        time_remaining = self.due_date - now
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        time_str = ""
        if days > 0:
            time_str += f"{days} jour{'s' if days > 1 else ''} "
        if hours > 0 or days > 0:  # Inclure les heures si on a des jours ou des heures
            time_str += f"{hours} heure{'s' if hours > 1 else ''} "
        time_str += f"{minutes} minute{'s' if minutes > 1 else ''}"

        # Définir l'urgence en fonction du temps restant et de la priorité
        total_minutes = days * 24 * 60 + hours * 60 + minutes
        urgency = 'low'  # Par défaut

        # Ajuster l'urgence en fonction de la priorité de la tâche
        if self.priority == TaskPriority.HIGH:
            if total_minutes <= 24 * 60 * 2:  # Moins de 2 jours pour une tâche haute priorité
                urgency = 'critical'
            elif total_minutes <= 24 * 60 * 5:  # Moins de 5 jours pour une tâche haute priorité
                urgency = 'high'
            else:
                urgency = 'medium'
        elif self.priority == TaskPriority.MEDIUM:
            if total_minutes <= 60:  # Moins d'une heure
                urgency = 'critical'
            elif total_minutes <= 24 * 60:  # Moins d'un jour
                urgency = 'high'
            elif total_minutes <= 3 * 24 * 60:  # Moins de 3 jours
                urgency = 'medium'
        else:  # LOW priority
            if total_minutes <= 24 * 60 / 2:  # Moins de 12 heures
                urgency = 'critical'
            elif total_minutes <= 24 * 60 / 4 * 3:  # Moins de 18 heures
                urgency = 'high'
            elif total_minutes <= 24 * 60:  # Moins d'un jour
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
            return "🔴"  # Rouge pour haute priorité
        elif self.priority == TaskPriority.MEDIUM:
            return "🟠"  # Orange pour priorité moyenne
        else:
            return "🟢"  # Vert pour faible priorité

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
        from entities.role import Role
        users = User.get_users_by_role(role)
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
        self.notify_task_completed()

    def delete_task(self):
        """Mark the task as deleted"""
        self.state = TaskState.DELETED
        db.session.commit()
        self.notify_task_deleted()

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

    def request_transfer(self, current_user_email: str, new_user_email: str):
        """Demande de céder la tâche à un autre utilisateur"""
        # Vérifier que l'utilisateur actuel est bien un assigné de la tâche
        from entities.user import User
        current_user = User.query.filter_by(email=current_user_email).first()
        new_user = User.query.filter_by(email=new_user_email).first()

        if not current_user or not new_user:
            return False, "Utilisateur non trouvé"

        if current_user not in self.assignees:
            return False, "Vous n'êtes pas assigné à cette tâche"

        # Stocker l'information de cession dans un attribut temporaire
        self.transfer_from = current_user_email
        self.transfer_to = new_user_email

        # Changer l'état de la tâche
        self.state = TaskState.TRANSFER_PENDING
        db.session.commit()

        # Notifier le créateur de la tâche
        self.notify_transfer_request(current_user_email, new_user_email)

        return True, "Demande de cession envoyée avec succès"

    def approve_transfer(self, approver_email: str):
        """Approuver la demande de cession de tâche"""
        # Vérifier que l'approbateur est bien le créateur de la tâche
        if self.assigned_by != approver_email:
            return False, "Vous n'êtes pas autorisé à approuver cette cession"

        if self.state != TaskState.TRANSFER_PENDING:
            return False, "Cette tâche n'est pas en attente de cession"

        from entities.user import User
        current_assignee = User.query.filter_by(email=self.transfer_from).first()
        new_assignee = User.query.filter_by(email=self.transfer_to).first()

        if not current_assignee or not new_assignee:
            return False, "Utilisateur non trouvé"

        # Retirer l'assigné actuel
        if current_assignee in self.assignees:
            self.assignees.remove(current_assignee)

        # Ajouter le nouvel assigné
        if new_assignee not in self.assignees:
            self.assignees.append(new_assignee)

        # Remettre l'état à assigned
        self.state = TaskState.ASSIGNED
        db.session.commit()

        # Notifier les deux utilisateurs
        self.notify_transfer_approved(self.transfer_from, self.transfer_to)

        # Nettoyer les attributs temporaires
        self.transfer_from = None
        self.transfer_to = None
        db.session.commit()

        return True, "Cession approuvée avec succès"

    def reject_transfer(self, approver_email: str):
        """Rejeter la demande de cession de tâche"""
        # Vérifier que l'approbateur est bien le créateur de la tâche
        if self.assigned_by != approver_email:
            return False, "Vous n'êtes pas autorisé à rejeter cette cession"

        if self.state != TaskState.TRANSFER_PENDING:
            return False, "Cette tâche n'est pas en attente de cession"

        # Remettre l'état à assigned
        self.state = TaskState.ASSIGNED

        # Notifier l'utilisateur du rejet
        self.notify_transfer_rejected(self.transfer_from, self.transfer_to)

        # Nettoyer les attributs temporaires
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

    def _get_api_details(self):
        """Get API details from environment variables"""
        api_key = os.getenv('WHATSAPP_API_KEY', 'UDvABgmTtdWC')  # Fallback to hardcoded value if not set
        api_url = os.getenv('WHATSAPP_API_URL', 'http://api.textmebot.com/send.php')
        return api_key, api_url

    def _send_notification(self, recipient_phone, message):
        """Send notification via TextMeBot API"""
        api_key, api_url = self._get_api_details()

        # Format phone number (ensure it has country code)
        if not recipient_phone.startswith('+'):
            # Add French country code if missing
            recipient_phone = '+33' + recipient_phone.lstrip('0')

        try:
            # Construct URL with parameters
            params = {
                'recipient': recipient_phone,
                'apikey': api_key,
                'text': message
            }

            # Make GET request
            response = requests.get(api_url, params=params)

            # Check response
            if response.status_code != 200:
                print(f"Error sending SMS notification: {response.text}")
                return False
            return True
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return False

    def _get_user_full_name(self, email):
        """Get the full name of a user by email"""
        from entities.user import User
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

        # Construire le début du message en fonction du type
        if message_type == "assignment":
            message = f"{priority_icon} La tâche '{self.subject}' vous a été assignée par {actor_name} le {current_time}"
        elif message_type == "dispute":
            message = f"{priority_icon} La tâche '{self.subject}' a été contestée par {actor_name} le {current_time}"
        elif message_type == "validation_request":
            message = f"{priority_icon} La tâche '{self.subject}' a été marquée prête pour validation par {actor_name} le {current_time}"
        elif message_type == "task_reopened":
            message = f"{priority_icon} La tâche '{self.subject}' a été rouverte par {actor_name} le {current_time}"
        elif message_type == "validation_cancelled":
            message = f"{priority_icon} La demande de validation pour la tâche '{self.subject}' a été annulée par {actor_name} le {current_time}"
        elif message_type == "dispute_rejected":
            message = f"{priority_icon} La contestation de la tâche '{self.subject}' a été rejetée par {actor_name} le {current_time}"
        elif message_type == "validation_rejected":
            message = f"{priority_icon} La validation de la tâche '{self.subject}' a été rejetée par {actor_name} le {current_time}"
        elif message_type == "task_completed":
            message = f"{priority_icon} La tâche '{self.subject}' a été marquée comme terminée par {actor_name} le {current_time}"
        elif message_type == "task_deleted":
            message = f"{priority_icon} La tâche '{self.subject}' a été supprimée par {actor_name} le {current_time}"
        elif message_type == "task_validated":
            message = f"{priority_icon} La tâche '{self.subject}' a été validée par {actor_name} le {current_time}"
        elif message_type == "priority_changed":
            message = f"{priority_icon} La priorité de la tâche '{self.subject}' a été changée à {priority_text} par {actor_name} le {current_time}"
        elif message_type == "reminder":
            message = f"{priority_icon} RAPPEL: La tâche '{self.subject}' requiert votre attention. {actor_name} vous a envoyé ce rappel le {current_time}"
        elif message_type == "task_taken":
            message = f"{priority_icon} La tâche '{self.subject}' a été prise par {actor_name} le {current_time}"
        # Types de messages pour les cessions
        elif message_type == "transfer_request":
            message = f"{priority_icon} DEMANDE DE CESSION: La tâche '{self.subject}' est en attente de cession. {actor_name} a fait cette demande le {current_time}"
        elif message_type == "transfer_approved":
            message = f"{priority_icon} CESSION APPROUVÉE: Votre demande de céder la tâche '{self.subject}' a été approuvée par {actor_name} le {current_time}"
        elif message_type == "transfer_approved_new":
            message = f"{priority_icon} NOUVELLE TÂCHE: La tâche '{self.subject}' vous a été cédée et approuvée par {actor_name} le {current_time}"
        elif message_type == "transfer_rejected":
            message = f"{priority_icon} CESSION REJETÉE: Votre demande de céder la tâche '{self.subject}' a été rejetée par {actor_name} le {current_time}"
        else:
            # Message générique au cas où
            message = f"{priority_icon} Mise à jour de la tâche '{self.subject}' par {actor_name} le {current_time}"

        # Ajouter les détails de la tâche
        message += "\nDétail de la tâche :\n"
        message += f"{self.description or 'Aucune description fournie'}"

        # Ajouter l'information de priorité sauf pour le changement de priorité
        if message_type != "priority_changed":
            message += f"\n\nPriorité: {priority_text}"

        # Ajouter l'information de temps si ce n'est pas une tâche terminée ou supprimée
        if message_type not in ["task_completed", "task_deleted", "task_validated"]:
            message += f"\n{time_info_str}"

        # Ajouter des informations supplémentaires si fournies
        if additional_info:
            message += f"\n\n{additional_info}"

        return message

    def notify_assignment(self):
        """Notify all assignees about the new task"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            # Information supplémentaire : date d'échéance
            additional_info = f"Date d'échéance: {self.due_date.strftime('%d/%m/%Y à %H:%M')}"
            message = self._format_message("assignment", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_task_taken(self, user_email: str):
        """Notify the task creator that someone has taken the task"""
        # Get the assigner
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        taker = User.query.filter_by(email=user_email).first()

        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            print(f"Assigner {self.assigned_by} has no phone number, skipping notification")
            return

        taker_name = f"{taker.fname} {taker.lname}" if taker else user_email

        # Formater le message de notification
        message = self._format_message("task_taken", user_email, f"La tâche a été prise par {taker_name}")

        # Envoyer la notification
        self._send_notification(assigner.phone, message)

    def notify_priority_change(self):
        """Notify all assignees about priority change"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            message = self._format_message("priority_changed", self.assigned_by)
            self._send_notification(user.phone, message)

    def notify_dispute(self, user_email: str):
        """Notify the assigner about a disputed task"""
        # Get the assigner
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            print(f"Assigner {self.assigned_by} has no phone number, skipping notification")
            return

        message = self._format_message("dispute", user_email)
        self._send_notification(assigner.phone, message)

    def notify_to_validate(self, user_email: str):
        """Notify the assigner that a task is ready to be validated"""
        # Get the assigner
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        if not assigner or not hasattr(assigner, 'phone') or not assigner.phone:
            print(f"Assigner {self.assigned_by} has no phone number, skipping notification")
            return

        message = self._format_message("validation_request", user_email)
        self._send_notification(assigner.phone, message)

    def notify_task_reopened(self):
        """Notify all assignees that a task has been reopened"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Cette tâche a été rouverte et nécessite à nouveau votre attention."
            message = self._format_message("task_reopened", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_validation_cancelled(self):
        """Notify all assignees that validation has been cancelled"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Vous devez continuer à travailler sur cette tâche."
            message = self._format_message("validation_cancelled", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_dispute_rejected(self):
        """Notifier tous les assignés que leur contestation a été rejetée"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Vous devez continuer à travailler sur cette tâche malgré la contestation."
            message = self._format_message("dispute_rejected", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_validation_rejected(self):
        """Notifier tous les assignés que leur demande de validation a été rejetée"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "La tâche n'est pas considérée comme terminée. Veuillez apporter les corrections nécessaires."
            message = self._format_message("validation_rejected", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_task_completed(self):
        """Notifier tous les assignés que la tâche a été marquée comme terminée"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Félicitations ! Cette tâche a été clôturée avec succès."
            message = self._format_message("task_completed", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_task_deleted(self):
        """Notifier tous les assignés que la tâche a été supprimée"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Cette tâche a été supprimée et ne nécessite plus votre attention."
            message = self._format_message("task_deleted", self.assigned_by, additional_info)
            self._send_notification(user.phone, message)

    def notify_task_validated(self, validator_email):
        """Notifier tous les assignés que la tâche a été validée"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            additional_info = "Félicitations ! Votre travail sur cette tâche a été validé."
            message = self._format_message("task_validated", validator_email, additional_info)
            self._send_notification(user.phone, message)

    def send_reminder(self):
        """Send a reminder to all assignees"""
        for user in self.assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            message = f"⏰ RAPPEL: La tâche '{self.subject}' nécessite votre attention!"

            # Add task details
            message += "\nDétail de la tâche :\n"
            message += f"{self.description or 'Aucune description fournie'}"

            # Add time info
            time_info_str = self.format_time_remaining()
            message += f"\n{time_info_str}"

            # Add due date
            message += f"\nDate d'échéance: {self.due_date.strftime('%d/%m/%Y à %H:%M')}"

            # Add message from assigner
            message += "\n\nCe rappel a été envoyé par le créateur de la tâche."

            self._send_notification(user.phone, message)

    def notify_transfer_request(self, from_email: str, to_email: str):
        """Notifier le créateur qu'un utilisateur souhaite céder sa tâche"""
        from entities.user import User
        assigner = User.query.filter_by(email=self.assigned_by).first()
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not assigner or not current_user or not new_user:
            print(f"Utilisateur manquant pour la notification de demande de cession")
            return

        if not assigner.phone:
            print(f"Créateur sans numéro de téléphone: {self.assigned_by}")
            return

        # Information supplémentaire
        current_name = f"{current_user.fname} {current_user.lname}"
        new_name = f"{new_user.fname} {new_user.lname}"

        additional_info = f"{current_name} souhaite céder cette tâche à {new_name}. Veuillez approuver ou rejeter cette demande."

        message = self._format_message("transfer_request", from_email, additional_info)
        self._send_notification(assigner.phone, message)

    def notify_transfer_approved(self, from_email: str, to_email: str):
        """Notifier les deux utilisateurs que la cession a été approuvée"""
        from entities.user import User
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not current_user or not new_user:
            print(f"Utilisateur manquant pour la notification d'approbation de cession")
            return

        # Notifier l'utilisateur précédent
        if current_user.phone:
            current_name = f"{current_user.fname} {current_user.lname}"
            new_name = f"{new_user.fname} {new_user.lname}"
            additional_info = f"Votre demande de céder cette tâche à {new_name} a été approuvée."
            message = self._format_message("transfer_approved", self.assigned_by, additional_info)
            self._send_notification(current_user.phone, message)

        # Notifier le nouvel utilisateur
        if new_user.phone:
            current_name = f"{current_user.fname} {current_user.lname}"
            additional_info = f"Vous avez reçu cette tâche de {current_name}. La cession a été approuvée."
            message = self._format_message("transfer_approved_new", self.assigned_by, additional_info)
            self._send_notification(new_user.phone, message)

    def notify_transfer_rejected(self, from_email: str, to_email: str):
        """Notifier l'utilisateur que sa demande de cession a été rejetée"""
        from entities.user import User
        current_user = User.query.filter_by(email=from_email).first()
        new_user = User.query.filter_by(email=to_email).first()

        if not current_user:
            print(f"Utilisateur manquant pour la notification de rejet de cession")
            return

        if current_user.phone:
            new_name = f"{new_user.fname} {new_user.lname}" if new_user else to_email
            additional_info = f"Votre demande de céder cette tâche à {new_name} a été rejetée. Vous êtes toujours responsable de cette tâche."
            message = self._format_message("transfer_rejected", self.assigned_by, additional_info)
            self._send_notification(current_user.phone, message)

    @staticmethod
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

    def notify_task_released(self, user_email):
        """Notifier le créateur de la tâche qu'un utilisateur a libéré la tâche"""
        from entities.user import User
        creator = User.query.filter_by(email=self.assigned_by).first()
        releaser = User.query.filter_by(email=user_email).first()

        if not creator or not releaser:
            print(f"Créateur ou utilisateur libérant non trouvé")
            return

        if not creator.phone:
            print(f"Créateur sans numéro de téléphone: {self.assigned_by}")
            return

        # Formater le message
        message = f"La tâche '{self.subject}' a été libérée par {releaser.fname} {releaser.lname}. "
        message += "Elle est maintenant disponible pour d'autres personnes."

        # Envoyer la notification
        self._send_notification(creator.phone, message)

    # Méthode pour notifier un réassignement de tâche
    def notify_task_reassigned(self, new_assignees):
        """Notifier les nouveaux assignés qu'ils ont été assignés à cette tâche"""
        for user in new_assignees:
            # Skip if user has no phone
            if not hasattr(user, 'phone') or not user.phone:
                print(f"User {user.email} has no phone number, skipping notification")
                continue

            # Information supplémentaire : date d'échéance
            additional_info = f"Date d'échéance: {self.due_date.strftime('%d/%m/%Y à %H:%M')}"
            message = self._format_message("assignment", self.assigned_by, additional_info)
            message += "\n\nVous avez été réassigné à cette tâche par le créateur."
            self._send_notification(user.phone, message)

    # Méthode pour notifier un transfert de propriété
    def notify_ownership_transfer(self, old_owner, new_owner_email):
        """Notifier le nouveau propriétaire du transfert de propriété"""
        from entities.user import User
        new_owner = User.query.filter_by(email=new_owner_email).first()
        if not new_owner or not new_owner.phone:
            print(f"Nouveau propriétaire sans numéro ou introuvable: {new_owner_email}")
            return

        # Formater le message
        message = f"La propriété de la tâche '{self.subject}' vous a été transférée par {old_owner}. "
        message += "Vous êtes maintenant responsable de cette tâche et pouvez la gérer."

        # Envoyer la notification
        self._send_notification(new_owner.phone, message)

    @staticmethod
    def get_assigned_tasks_by_user(user_email: str):
        """Get all tasks assigned by a specific user"""
        return Task.query.filter_by(assigned_by=user_email).filter(Task.state != TaskState.DELETED).all()