from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from datetime import datetime

from models.user import User
from routes.auth import is_not_connected
from models import db

locations_bp = Blueprint('locations', __name__)


@locations_bp.route('/users-map')
def users_map():
    """Page de carte des utilisateurs"""
    if is_not_connected():
        return redirect(url_for('auth.login'))


    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    focus_user = request.args.get('focus')

    return render_template('users-map.html', error=error_message, user_info=session['user_info'], focus_user=focus_user)


@locations_bp.route('/save-location', methods=['POST'])
def save_location():
    """API pour sauvegarder la localisation d'un utilisateur"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json  # Receive JSON data from client
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    email = session['user_info']['email']

    if latitude is not None and longitude is not None:
        try:
            current_datetime = datetime.now()
            user = User.query.filter_by(email=email).first()

            if not user:
                return jsonify({'status': 'error', 'message': 'User not found'}), 404

            user.set_location(longitude, latitude, current_datetime)
            return jsonify({'status': 'success', 'message': 'Location saved successfully!'}), 201
        except Exception as e:
            print(f"Error saving location: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Error saving location: {str(e)}'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid data - latitude or longitude missing'}), 400


@locations_bp.route('/api/users-locations', methods=['GET'])
def get_users_locations():
    """API pour récupérer la localisation de tous les utilisateurs"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        users = User.query.order_by(User.lname, User.fname).all()

        users_with_location = []
        for user in users:
            if user.lat is not None and user.long is not None:
                users_with_location.append({
                    'email': user.email,
                    'fname': user.fname,
                    'lname': user.lname,
                    'phone': user.phone,
                    'lat': user.lat,
                    'long': user.long,
                    'location_date': user.location_date.isoformat() if user.location_date else None
                })

        return jsonify(users_with_location)
    except Exception as e:
        print(f"Error getting users locations: {str(e)}")
        return jsonify({'error': str(e)}), 500


@locations_bp.route('/api/user/location/<string:email>', methods=['GET'])
def get_specific_user_location(email):
    """API pour récupérer la localisation d'un utilisateur spécifique"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        if user.lat is None or user.long is None:
            return jsonify({'error': 'No location data available for this user'}), 404

        return jsonify({
            'email': user.email,
            'fname': user.fname,
            'lname': user.lname,
            'lat': user.lat,
            'long': user.long,
            'location_date': user.location_date.isoformat() if user.location_date else None
        })
    except Exception as e:
        print(f"Error getting user location: {str(e)}")
        return jsonify({'error': str(e)}), 500


@locations_bp.route('/update-location-settings', methods=['POST'])
def update_location_settings():
    """API pour mettre à jour les paramètres de localisation d'un utilisateur"""
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    enable_location = data.get('enable_location', True)

    try:
        user_email = session['user_info']['email']
        user = User.query.filter_by(email=user_email).first()

        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        if not enable_location:
            user.set_location(None, None, None)


        return jsonify({'status': 'success', 'message': 'Location settings updated'})
    except Exception as e:
        print(f"Error updating location settings: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500