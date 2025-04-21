from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from models.statistic import Statistic
from routes.auth import is_not_connected
from db import db
from datetime import datetime

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/statistics')
def statistics_page():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    stats = Statistic.get_all()
    stats_dict = {stat.id: stat.to_dict() for stat in stats}

    return render_template('statistics.html', error=error_message, user_info=session['user_info'], stats=stats_dict)


@stats_bp.route('/api/statistics/increment', methods=['POST'])
def increment_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    stat_id = data.get('id')
    amount = data.get('amount', 1)

    if not stat_id:
        return jsonify({'error': 'Statistic ID required'}), 400

    try:
        amount = int(amount)
    except ValueError:
        return jsonify({'error': 'Amount must be a number'}), 400

    success = Statistic.increment(stat_id, amount)
    if not success:
        return jsonify({'error': 'Failed to increment statistic'}), 500

    stat = Statistic.get_by_id(stat_id)
    if not stat:
        return jsonify({'error': 'Statistic not found'}), 404

    return jsonify({'success': True, 'statistic': stat.to_dict()})


@stats_bp.route('/api/statistics/set', methods=['POST'])
def set_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    stat_id = data.get('id')
    value = data.get('value')

    if not stat_id or value is None:
        return jsonify({'error': 'ID and value required'}), 400

    success = Statistic.set_value(stat_id, value)
    if not success:
        return jsonify({'error': 'Failed to set statistic'}), 500

    stat = Statistic.get_by_id(stat_id)
    if not stat:
        return jsonify({'error': 'Statistic not found'}), 404

    return jsonify({'success': True, 'statistic': stat.to_dict()})


@stats_bp.route('/api/statistics/set-order', methods=['POST'])
def set_statistic_order():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    stat_id = data.get('id')
    order = data.get('order')

    if not stat_id or order is None:
        return jsonify({'error': 'ID and order required'}), 400

    try:
        order = int(order)
    except ValueError:
        return jsonify({'error': 'Order must be a number'}), 400

    success = Statistic.set_display_order(stat_id, order)
    if not success:
        return jsonify({'error': 'Failed to set statistic order'}), 500

    stat = Statistic.get_by_id(stat_id)
    if not stat:
        return jsonify({'error': 'Statistic not found'}), 404

    return jsonify({'success': True, 'statistic': stat.to_dict()})


@stats_bp.route('/api/statistics/create', methods=['POST'])
def create_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    label = data.get('label')
    value = data.get('value')
    is_text = data.get('is_text', False)
    display_order = data.get('display_order', 999)

    if not label or value is None:
        return jsonify({'error': 'Label and value are required'}), 400

    existing_stat = Statistic.get_by_label(label)
    if existing_stat:
        return jsonify({'error': 'A statistic with this label already exists'}), 400

    try:
        stat = Statistic.create(value=value, label=label, is_text=is_text, display_order=display_order)
        return jsonify({'success': True, 'statistic': stat.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create statistic: {str(e)}'}), 500


@stats_bp.route('/api/statistics/delete', methods=['POST'])
def delete_statistic():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    stat_id = data.get('id')

    if not stat_id:
        return jsonify({'error': 'Statistic ID required'}), 400

    success = Statistic.delete(stat_id)
    if not success:
        return jsonify({'error': 'Statistic not found or could not be deleted'}), 404

    return jsonify({'success': True})


@stats_bp.route('/api/statistics', methods=['GET'])
def get_statistics():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    stats = Statistic.get_all()
    return jsonify([stat.to_dict() for stat in stats])