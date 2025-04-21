from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, send_file
import requests
import os
from urllib.parse import urljoin
from routes.auth import is_not_connected

files_bp = Blueprint('files', __name__)

API_URL = os.getenv("FILES_API_URL", "http://localhost:7000")
API_KEY = os.getenv("FILES_API_KEY", "")


@files_bp.route('/files-manager')
def files_manager():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    success_message = None
    if 'success' in request.args:
        success_message = request.args.get('success')

    directory = request.args.get('directory', '')

    return render_template(
        'files_manager.html',
        error=error_message,
        success=success_message,
        user_info=session['user_info'],
        current_directory=directory
    )


@files_bp.route('/api/files', methods=['GET'])
def get_files():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    directory = request.args.get('directory', '')

    try:
        url = urljoin(API_URL, "/files")
        params = {}
        if directory:
            params['directory'] = directory

        response = requests.get(
            url,
            headers={"X-API-KEY": API_KEY},
            params=params
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': f"Erreur lors de la récupération des fichiers: {response.status_code}"
            }), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/api/files/upload', methods=['POST'])
def upload_file():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']
    directory = request.form.get('directory', '')

    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400

    try:
        url = urljoin(API_URL, "/files/upload")

        files = {'file': (file.filename, file.read(), file.content_type)}
        data = {}
        if directory:
            data['directory'] = directory

        response = requests.post(
            url,
            headers={"X-API-KEY": API_KEY},
            files=files,
            data=data
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                'error': f"Erreur lors du téléversement: {response.status_code}"
            }), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/api/files/delete/<path:file_path>', methods=['DELETE'])
def delete_file(file_path):
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    try:
        url = urljoin(API_URL, f"/files/{file_path}")

        response = requests.delete(
            url,
            headers={"X-API-KEY": API_KEY}
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_message = f"Erreur lors de la suppression: {response.status_code}"
            if response.content:
                try:
                    error_json = response.json()
                    if 'detail' in error_json:
                        error_message = error_json['detail']
                except:
                    pass
            return jsonify({'error': error_message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/api/files/rename', methods=['POST'])
def rename_file():
    if is_not_connected():
        return jsonify({'error': 'Not connected'}), 401

    data = request.json
    old_path = data.get('old_path')
    new_name = data.get('new_name')

    if not old_path or not new_name:
        return jsonify({'error': 'Chemin actuel et nouveau nom requis'}), 400

    try:
        url = urljoin(API_URL, "/files/rename")

        response = requests.post(
            url,
            headers={
                "X-API-KEY": API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "old_path": old_path,
                "new_name": new_name
            }
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_message = f"Erreur lors du renommage: {response.status_code}"
            if response.content:
                try:
                    error_json = response.json()
                    if 'detail' in error_json:
                        error_message = error_json['detail']
                except:
                    pass
            return jsonify({'error': error_message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@files_bp.route('/files/download/<path:file_path>')
def download_file(file_path):
    if is_not_connected():
        return redirect(url_for('auth.login'))

    inline = request.args.get('inline', 'false').lower() == 'true'

    try:
        url = urljoin(API_URL, f"/files/{file_path}")

        params = {}
        if inline:
            params['inline'] = 'true'

        response = requests.get(
            url,
            headers={"X-API-KEY": API_KEY},
            params=params,
            stream=True
        )

        if response.status_code == 200:
            file_name = file_path.split('/')[-1]
            mimetype = response.headers.get('Content-Type', 'application/octet-stream')

            return send_file(
                response.raw,
                download_name=file_name,
                as_attachment=not inline,
                mimetype=mimetype
            )
        else:
            return redirect(
                url_for('files.files_manager', error=f"Erreur lors du téléchargement: {response.status_code}"))
    except Exception as e:
        return redirect(url_for('files.files_manager', error=str(e)))