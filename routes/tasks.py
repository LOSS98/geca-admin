from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from datetime import datetime

from models.task import Task, TaskState
from models.user import User
from models.task_history import TaskHistory
from routes.auth import is_not_connected
from models import db

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/')
def index():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    user_info = session.get('user_info', {})
    return render_template('dashboard.html', user_info=user_info)

@tasks_bp.route('/tasks')
def tasks_list():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    user_email = session['user_info']['email']
    user_role = session.get('role', 'member')

    return render_template('timeline.html', error=error_message, user_info=session['user_info'], user_role=user_role)

@tasks_bp.route('/createTask')
def create_task_page():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    members = User.get_all_names()
    roles = ['admin', 'member', 'treasurer']  # Add all available roles

    return render_template('createTask.html', error=error_message, user_info=session['user_info'], members=members, roles=roles)

@tasks_bp.route('/available-tasks')
def available_tasks_page():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    user_email = session['user_info']['email']
    user = User.query.filter_by(email=user_email).first()
    user_roles = user.get_roles() if user else []

    return render_template('available-tasks.html', error=error_message, user_info=session['user_info'], user_roles=user_roles)

@tasks_bp.route('/task')
def timeline():
    if is_not_connected():
        return redirect(url_for('auth.login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('timeline old.html', error=error_message, user_info=session['user_info'])

# API routes for tasks
@tasks_bp.route('/api/tasks')
def get_tasks():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')

        tasks_as_assignee = Task.get_tasks_for_user(user_email)

        tasks_as_assigner = Task.get_assigned_tasks_by_user(user_email)

        all_tasks = []
        task_ids = set()

        for task in tasks_as_assignee + tasks_as_assigner:
            if task.id not in task_ids:
                all_tasks.append(task)
                task_ids.add(task.id)

        tasks_data = []
        for task in all_tasks:
            task_dict = task.to_dict()
            task_dict['is_assigner'] = (task.assigned_by == user_email)
            task_dict['can_manage'] = (task.assigned_by == user_email) or (user_role == 'admin')
            tasks_data.append(task_dict)

        return jsonify(tasks_data)
    except Exception as e:
        print(f"Error getting tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/createTask', methods=['POST'])
def create_task_api():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    user_email = session['user_info']['email']

    try:
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%dT%H:%M')
        due_date = datetime.strptime(data['due_date'], '%Y-%m-%dT%H:%M')

        task_data = {
            'assigned_by': user_email,
            'start_date': start_date,
            'due_date': due_date,
            'subject': data['subject'],
            'description': data['description'],
            'priority': data.get('priority', 'medium'),  # Default to medium priority
            'target_roles': []  # Default à une liste vide
        }

        assignment_type = data.get('assignment_type')

        if assignment_type == 'role':
            task_data['target_roles'] = data.get('target_roles', [])

        task = Task(task_data)

        task.save_to_db()

        if assignment_type == 'users':
            assignees = data.get('assignees', [])
            print(f"Selected assignees: {assignees}")
            if assignees:
                user_emails = []
                for assignee_name in assignees:
                    parts = assignee_name.split(' ', 1)
                    if len(parts) == 2:
                        lname, fname = parts
                        user = User.query.filter_by(lname=lname, fname=fname).first()
                        if user:
                            user_emails.append(user.email)

                if user_emails:
                    task.assign_to_users(user_emails)

        return jsonify({'success': True, 'task_id': task.id})

    except Exception as e:
        db.session.rollback()
        print(f"Error creating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/dispute', methods=['POST'])
def dispute_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        task.dispute(user_email)

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error disputing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/validate', methods=['POST'])
def validate_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        task.mark_to_validate(user_email)

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error validating task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        task.mark_as_done()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error completing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/remove-assignee', methods=['POST'])
def remove_assignee(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    user_email = session['user_info']['email']
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.assigned_by != user_email:
        return jsonify({'error': 'Not authorized'}), 403

    assignee_email = data.get('assignee_email')
    if assignee_email:
        task.remove_assignee(assignee_email)

    return jsonify({'success': True})

@tasks_bp.route('/api/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        task.delete_task()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/cancel-validation', methods=['POST'])
def cancel_validation(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Not authorized'}), 403

        task.cancel_validation()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling validation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/reject-validation', methods=['POST'])
def reject_validation(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email:
            return jsonify({'error': 'Not authorized'}), 403

        task.reject_validation()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting validation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/reject-dispute', methods=['POST'])
def reject_dispute(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email:
            return jsonify({'error': 'Not authorized'}), 403

        task.reject_dispute()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting dispute: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/reopen', methods=['POST'])
def reopen_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        task.reopen_task()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error reopening task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/priority', methods=['POST'])
def change_task_priority(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user_role = session.get('role', 'member')
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.assigned_by != user_email and user_role != 'admin':
            return jsonify({'error': 'Not authorized'}), 403

        data = request.json
        new_priority = data.get('priority')

        if not new_priority or new_priority not in ['low', 'medium', 'high']:
            return jsonify({'error': 'Invalid priority value'}), 400

        result = task.set_priority(new_priority)

        if not result:
            return jsonify({'error': 'Failed to update priority'}), 500

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error changing task priority: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/available-tasks')
def get_available_tasks():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify([])

        user_roles = user.get_roles()

        all_tasks = Task.query.filter(
            Task.state == TaskState.ASSIGNED
        ).all()

        available_tasks = []
        for task in all_tasks:
            if len(task.assignees) > 0:
                continue

            is_available = False

            if not task.target_roles:
                is_available = True
            else:
                target_role_names = [role.name for role in task.target_roles]
                if any(role in target_role_names for role in user_roles):
                    is_available = True

            if is_available:
                task_dict = task.to_dict()

                task_dict['previous_assignees'] = []

                available_tasks.append(task_dict)

        return jsonify(available_tasks)
    except Exception as e:
        print(f"Error getting available tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/take', methods=['POST'])
def take_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        if task.state != TaskState.ASSIGNED or len(task.assignees) > 0:
            return jsonify({'error': 'Cette tâche n\'est plus disponible'}), 400

        is_available = True
        if task.target_roles:
            user_roles = user.get_roles()
            target_role_names = [role.name for role in task.target_roles]
            if not any(role in target_role_names for role in user_roles):
                is_available = False

        if not is_available:
            return jsonify({'error': 'Vous n\'avez pas les rôles requis pour cette tâche'}), 403

        task.assignees.append(user)

        history_entry = TaskHistory(
            task_id=task.id,
            user_email=user_email,
            action="self_assigned"
        )
        history_entry.save_to_db()

        db.session.commit()

        try:
            creator = User.query.filter_by(email=task.assigned_by).first()
            if creator and creator.phone:
                message = f"Votre tâche '{task.subject}' a été prise par {user.fname} {user.lname}."
                task._send_notification(creator.phone, message)
        except Exception as e:
            print(f"Erreur lors de la notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error taking task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/remind', methods=['POST'])
def remind_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        if task.assigned_by != user_email:
            return jsonify({'error': 'Non autorisé'}), 403

        for user in task.assignees:
            if hasattr(user, 'phone') and user.phone:
                message = task._format_message("reminder", user_email,
                                               "Ce rappel a été envoyé par le créateur de la tâche.")
                task._send_notification(user.phone, message)

        return jsonify({'success': True})
    except Exception as e:
        print(f"Error sending reminder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/request-transfer', methods=['POST'])
def request_task_transfer(task_id):
    """API pour demander une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        data = request.json
        new_user_email = data.get('new_user_email')

        if not new_user_email:
            return jsonify({'error': 'Email du nouvel utilisateur manquant'}), 400

        new_user = User.query.filter_by(email=new_user_email).first()
        if not new_user:
            return jsonify({'error': 'Utilisateur cible non trouvé'}), 404

        success, message = task.request_transfer(user_email, new_user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error requesting task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/approve-transfer', methods=['POST'])
def approve_task_transfer(task_id):
    """API pour approuver une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        success, message = task.approve_transfer(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error approving task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/reject-transfer', methods=['POST'])
def reject_task_transfer(task_id):
    """API pour rejeter une cession de tâche"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        success, message = task.reject_transfer(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting task transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/release', methods=['POST'])
def release_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        user = User.query.filter_by(email=user_email).first()
        if user not in task.assignees:
            return jsonify({'error': 'Vous n\'êtes pas assigné à cette tâche'}), 403

        task.assignees.remove(user)

        if len(task.assignees) == 0 and task.state not in [TaskState.DONE, TaskState.DELETED]:
            task.state = TaskState.ASSIGNED

        db.session.commit()

        try:
            creator = User.query.filter_by(email=task.assigned_by).first()
            if creator and creator.phone:
                message = f"La tâche '{task.subject}' a été libérée par {user.fname} {user.lname} et est maintenant disponible pour d'autres personnes."
                task._send_notification(creator.phone, message)
        except Exception as e:
            print(f"Erreur d'envoi de notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error releasing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/transfer-ownership', methods=['POST'])
def transfer_task_ownership(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        if task.assigned_by != user_email:
            return jsonify({'error': 'Vous n\'êtes pas autorisé à transférer la propriété de cette tâche'}), 403

        data = request.json
        new_owner_email = data.get('new_owner')

        if not new_owner_email:
            return jsonify({'error': 'Veuillez sélectionner un nouveau propriétaire'}), 400

        new_owner = User.query.filter_by(email=new_owner_email).first()

        if not new_owner:
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        old_owner = task.assigned_by
        task.assigned_by = new_owner_email
        db.session.commit()

        try:
            if new_owner.phone:
                message = f"La propriété de la tâche '{task.subject}' vous a été transférée par {user_email}. Vous êtes maintenant responsable de cette tâche."
                task._send_notification(new_owner.phone, message)
        except Exception as e:
            print(f"Erreur d'envoi de notification: {str(e)}")

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error transferring task ownership: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/release-api', methods=['POST'])
def release_task_api(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        success, message = task.release_task(user_email)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error releasing task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/tasks/<int:task_id>/reassign', methods=['POST'])
def reassign_task(task_id):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        task = Task.query.get(task_id)

        if not task:
            return jsonify({'error': 'Tâche non trouvée'}), 404

        data = request.json
        assignment_type = data.get('assignment_type')

        if assignment_type not in ['users', 'roles', 'all']:
            return jsonify({'error': 'Type d\'assignation invalide'}), 400

        reassignment_data = {}

        if assignment_type == 'users':
            assignees = data.get('assignees', [])

            assignee_emails = []

            for assignee in assignees:
                if '@' in assignee:
                    user = User.query.filter_by(email=assignee).first()
                    if user:
                        assignee_emails.append(assignee)
                else:
                    parts = assignee.split(' ', 1)
                    if len(parts) == 2:
                        lname, fname = parts
                        user = User.query.filter_by(lname=lname, fname=fname).first()
                        if user:
                            assignee_emails.append(user.email)

            reassignment_data['assignees'] = assignee_emails

        elif assignment_type == 'roles':
            reassignment_data['target_roles'] = data.get('target_roles', [])

        success, message = task.reassign(user_email, assignment_type, reassignment_data)

        if not success:
            return jsonify({'error': message}), 400

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        print(f"Error reassigning task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/members/<string:email>/assigned-tasks', methods=['GET'])
def get_member_assigned_tasks(email):
    """API pour récupérer les tâches assignées à un membre"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        tasks = Task.get_tasks_for_user(email)
        tasks_data = [task.to_dict() for task in tasks]
        return jsonify(tasks_data)
    except Exception as e:
        print(f"Error getting member assigned tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/members/<string:email>/created-tasks', methods=['GET'])
def get_member_created_tasks(email):
    """API pour récupérer les tâches créées par un membre"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        tasks = Task.get_assigned_tasks_by_user(email)
        tasks_data = [task.to_dict() for task in tasks]
        return jsonify(tasks_data)
    except Exception as e:
        print(f"Error getting member created tasks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@tasks_bp.route('/api/users', methods=['GET'])
def get_users():
    """API pour récupérer la liste des utilisateurs (pour la sélection lors de la cession)"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        users = User.query.order_by(User.lname, User.fname).all()
        users_data = [{'email': user.email, 'name': f"{user.lname} {user.fname}"} for user in users]
        return jsonify(users_data)
    except Exception as e:
        print(f"Error getting users: {str(e)}")
        return jsonify({'error': str(e)}), 500