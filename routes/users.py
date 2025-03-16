from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify

from models.user import User
from models.task import Task
from routes.auth import is_not_connected
from models import db

users_bp = Blueprint('users', __name__)

@users_bp.route('/singleUser')
def single_user():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    user_email = session['user_info']['email']
    user = User.query.filter_by(email=user_email).first()

    if not user:
        return redirect(url_for('tasks.index', error="Utilisateur non trouvé"))

    user_roles = user.get_roles()

    return render_template('singleUser.html', error=error_message, user_info=session['user_info'], user=user, user_roles=user_roles)

@users_bp.route('/users')
def users_list():
    if is_not_connected():
        return redirect(url_for('auth.login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error=error_message, user_info=session['user_info'])

@users_bp.route('/createUser')
def create_user():
    if is_not_connected():
        return redirect(url_for('auth.login'))
    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')
    return render_template('users.html', error=error_message, user_info=session['user_info'])

@users_bp.route('/members-management')
def members_management():
    """Page de gestion des membres"""
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    return render_template('members-management.html', error=error_message, user_info=session['user_info'])

@users_bp.route('/api/updateUserRole', methods=['POST'])
def update_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        new_role = data.get('role')

        valid_roles = [
            'Team Bureau', 'Team Partenariat', 'Team Com', 'Team BDA', 'Team BDS',
            'Team Soirée', 'Team FISA', 'Team Opé', 'Team Argent', 'Team Logistique',
            'Team Orga', 'Team Animation', 'Team Sécu', 'Team Film', 'Team E-BDS',
            'Team Silencieuses', 'Team Standard', 'Team Goodies', 'Team INFO', 'Team A&C'
        ]

        if new_role and new_role not in valid_roles:
            return jsonify({'error': 'Rôle invalide'}), 400

        user.role = new_role
        db.session.commit()

        session['role'] = new_role

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating user role: {str(e)}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/addUserRole', methods=['POST'])
def add_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        new_role = data.get('role')

        valid_roles = [
            'Team Bureau', 'Team Partenariat', 'Team Com', 'Team BDA', 'Team BDS',
            'Team Soirée', 'Team FISA', 'Team Opé', 'Team Argent', 'Team Logistique',
            'Team Orga', 'Team Animation', 'Team Sécu', 'Team Film', 'Team E-BDS',
            'Team Silencieuses', 'Team Standard', 'Team Goodies', 'Team INFO', 'Team A&C'
        ]

        if not new_role or new_role not in valid_roles:
            return jsonify({'error': 'Rôle invalide'}), 400

        if user.has_role(new_role):
            return jsonify({'error': 'Vous avez déjà ce rôle'}), 400

        user.add_role(new_role)

        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error adding user role: {str(e)}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/removeUserRole', methods=['POST'])
def remove_user_role():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        data = request.json
        role_to_remove = data.get('role')

        if not user.has_role(role_to_remove):
            return jsonify({'error': 'Vous n\'avez pas ce rôle'}), 400

        user.remove_role(role_to_remove)

        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error removing user role: {str(e)}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/members/add-role', methods=['POST'])
def add_member_role():
    """API pour ajouter un rôle à un membre"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        data = request.json
        email = data.get('email')
        role = data.get('role')

        if not email or not role:
            return jsonify({'error': 'Email et rôle requis'}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        user.add_role(role)

        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        print(f"Error adding member role: {str(e)}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/members/remove-role', methods=['POST'])
def remove_member_role():
    """API pour supprimer un rôle d'un membre"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        data = request.json
        email = data.get('email')
        role = data.get('role')

        if not email or not role:
            return jsonify({'error': 'Email et rôle requis'}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        user.remove_role(role)

        return jsonify({
            'success': True,
            'roles': user.get_roles()
        })
    except Exception as e:
        print(f"Error removing member role: {str(e)}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/members-management', methods=['GET'])
def get_members_management():
    """API pour récupérer tous les membres avec leurs informations"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        from models.task import Task
        users = User.query.order_by(User.fname, User.lname).all()
        members_data = []
        for user in users:
            task_count = len(Task.get_tasks_for_user(user.email))

            members_data.append({
                'email': user.email,
                'fname': user.fname,
                'lname': user.lname,
                'phone': user.phone,
                'lat': user.lat,
                'long': user.long,
                'location_date': user.location_date.isoformat() if user.location_date else None,
                'roles': user.get_roles(),
                'task_count': task_count
            })

        return jsonify(members_data)
    except Exception as e:
        print(f"Error getting members data: {str(e)}")
        return jsonify({'error': str(e)}), 500