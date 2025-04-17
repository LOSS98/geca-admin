from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from models.statistic import Statistic
from routes.auth import is_not_connected
from db import db

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/statistics')
def statistics_page():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    stats = Statistic.get_all()
    stats_dict = {stat.key: stat.to_dict() for stat in stats}

    return render_template('statistics.html', error=error_message, user_info=session['user_info'], stats=stats_dict)

@stats_bp.route('/api/statistics/increment', methods=['POST'])
def increment_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    key = data.get('key')
    amount = data.get('amount', 1)

    if not key:
        return jsonify({'error': 'Key required'}), 400

    try:
        amount = int(amount)
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    success = Statistic.increment(key, amount)
    if not success:
        return jsonify({'error': 'Failed to increment statistic'}), 500

    # Récupérer la statistique mise à jour
    stat = Statistic.get_by_key(key)
    if not stat:
        return jsonify({'error': 'Statistic not found'}), 404

    return jsonify({'success': True, 'statistic': stat.to_dict()})

@stats_bp.route('/api/statistics/set', methods=['POST'])
def set_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    key = data.get('key')
    value = data.get('value')

    if not key or value is None:
        return jsonify({'error': 'Key and value required'}), 400

    success = Statistic.set_value(key, value)
    if not success:
        return jsonify({'error': 'Failed to set statistic'}), 500

    # Récupérer la statistique mise à jour
    stat = Statistic.get_by_key(key)
    if not stat:
        return jsonify({'error': 'Statistic not found'}), 404

    return jsonify({'success': True, 'statistic': stat.to_dict()})

@stats_bp.route('/api/statistics', methods=['GET'])
def get_statistics():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    stats = Statistic.get_all()
    return jsonify([stat.to_dict() for stat in stats])