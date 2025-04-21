from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from datetime import datetime
import os
import pandas as pd
import numpy as np
import io
import shutil

from models.shotgun import Shotgun, ShotgunParticipant
from models.user import User
from routes.auth import is_not_connected
from db import db

shotguns_bp = Blueprint('shotguns', __name__)


def is_admin():
    if is_not_connected():
        return False

    user_email = session['user_info']['email']
    user = User.query.filter_by(email=user_email).first()
    return user and user.is_admin


@shotguns_bp.route('/shotguns')
def shotguns_list():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    success_message = None
    if 'success' in request.args:
        success_message = request.args.get('success')

    user_is_admin = is_admin()

    if user_is_admin:
        shotguns = Shotgun.get_all()
    else:
        shotguns = Shotgun.get_published()

    # Vérifier les images pour chaque shotgun
    for shotgun in shotguns:
        shotgun_id = shotgun.id
        shotgun_image_path = check_shotgun_image(shotgun_id)
        if shotgun_image_path:
            shotgun.image_path = shotgun_image_path

    return render_template(
        'shotguns_list.html',
        error=error_message,
        success=success_message,
        user_info=session['user_info'],
        shotguns=shotguns,
        is_admin=user_is_admin
    )


@shotguns_bp.route('/shotguns/create', methods=['GET', 'POST'])
def create_shotgun():
    if is_not_connected():
        return redirect(url_for('auth.login'))

    if not is_admin():
        flash("Accès refusé : vous devez être administrateur pour créer un shotgun.")
        return redirect(url_for('shotguns.shotguns_list'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        max_participants = request.form.get('max_participants')
        event_date_str = request.form.get('event_date')
        is_published = 'is_published' in request.form
        image_path = request.form.get('image_path', '')  # Récupérer le chemin de l'image

        if not title:
            flash("Le titre est obligatoire.")
            return redirect(url_for('shotguns.create_shotgun'))

        if max_participants:
            try:
                max_participants = int(max_participants)
            except ValueError:
                flash("Le nombre maximum de participants doit être un nombre entier.")
                return redirect(url_for('shotguns.create_shotgun'))
        else:
            max_participants = None

        event_date = None
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash("Format de date invalide.")
                return redirect(url_for('shotguns.create_shotgun'))

        shotgun = Shotgun(
            title=title,
            description=description,
            max_participants=max_participants,
            event_date=event_date,
            is_published=is_published,
            created_by=session['user_info']['email']
        )

        shotgun.save_to_db()

        # Gérer l'image si elle existe
        if image_path:
            shotgun.image_path = image_path
            db.session.commit()

        flash("Shotgun créé avec succès!")
        return redirect(url_for('shotguns.edit_shotgun', shotgun_id=shotgun.id))

    return render_template('shotgun_create.html', user_info=session['user_info'])


@shotguns_bp.route('/shotguns/<int:shotgun_id>')
def view_shotgun(shotgun_id):
    if is_not_connected():
        return redirect(url_for('auth.login'))

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        flash("Shotgun non trouvé.")
        return redirect(url_for('shotguns.shotguns_list'))

    if not shotgun.is_published and not is_admin():
        flash("Ce shotgun n'est pas encore publié.")
        return redirect(url_for('shotguns.shotguns_list'))

    participants = ShotgunParticipant.get_by_shotgun(shotgun_id)

    # Vérifier si le shotgun a une image
    shotgun.image_path = check_shotgun_image(shotgun_id)

    return render_template(
        'shotgun_view.html',
        user_info=session['user_info'],
        shotgun=shotgun,
        participants=participants,
        is_admin=is_admin()
    )


@shotguns_bp.route('/shotguns/<int:shotgun_id>/edit', methods=['GET', 'POST'])
def edit_shotgun(shotgun_id):
    if is_not_connected():
        return redirect(url_for('auth.login'))

    if not is_admin():
        flash("Accès refusé : vous devez être administrateur pour modifier un shotgun.")
        return redirect(url_for('shotguns.shotguns_list'))

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        flash("Shotgun non trouvé.")
        return redirect(url_for('shotguns.shotguns_list'))

    error_message = None
    if 'error' in request.args:
        error_message = request.args.get('error')

    success_message = None
    if 'success' in request.args:
        success_message = request.args.get('success')

    if request.method == 'POST':
        if 'update_shotgun' in request.form:
            title = request.form.get('title')
            description = request.form.get('description')
            max_participants = request.form.get('max_participants')
            event_date_str = request.form.get('event_date')
            is_published = 'is_published' in request.form
            image_path = request.form.get('image_path', '')  # Récupérer le chemin de l'image

            if not title:
                flash("Le titre est obligatoire.")
                return redirect(url_for('shotguns.edit_shotgun', shotgun_id=shotgun_id))

            if max_participants:
                try:
                    max_participants = int(max_participants)
                except ValueError:
                    flash("Le nombre maximum de participants doit être un nombre entier.")
                    return redirect(url_for('shotguns.edit_shotgun', shotgun_id=shotgun_id))
            else:
                max_participants = None

            event_date = None
            if event_date_str:
                try:
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash("Format de date invalide.")
                    return redirect(url_for('shotguns.edit_shotgun', shotgun_id=shotgun_id))

            shotgun.update({
                'title': title,
                'description': description,
                'max_participants': max_participants,
                'event_date': event_date,
                'is_published': is_published,
                'image_path': image_path  # Mettre à jour le chemin de l'image
            })

            flash("Shotgun mis à jour avec succès!")
            return redirect(
                url_for('shotguns.edit_shotgun', shotgun_id=shotgun_id, success="Shotgun mis à jour avec succès!"))

    participants = ShotgunParticipant.get_by_shotgun(shotgun_id)
    participants_data = [p.to_dict() for p in participants]

    # Vérifier si le shotgun a une image
    shotgun.image_path = check_shotgun_image(shotgun_id)

    return render_template(
        'shotgun_edit.html',
        user_info=session['user_info'],
        shotgun=shotgun,
        participants=participants_data,
        error=error_message,
        success=success_message
    )


@shotguns_bp.route('/shotguns/<int:shotgun_id>/toggle-publish', methods=['POST'])
def toggle_publish_shotgun(shotgun_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if shotgun.is_published:
        shotgun.unpublish()
        return jsonify({'success': True, 'is_published': False, 'message': 'Shotgun dépublié avec succès'})
    else:
        shotgun.publish()
        return jsonify({'success': True, 'is_published': True, 'message': 'Shotgun publié avec succès'})


@shotguns_bp.route('/shotguns/<int:shotgun_id>/delete', methods=['POST'])
def delete_shotgun(shotgun_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    try:
        # Si le shotgun a une image, la supprimer
        delete_shotgun_images(shotgun_id)

        shotgun.delete_from_db()
        return jsonify({'success': True, 'message': 'Shotgun supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@shotguns_bp.route('/shotguns/<int:shotgun_id>/participants', methods=['GET'])
def get_participants(shotgun_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if not shotgun.is_published and not is_admin():
        return jsonify({'error': 'Ce shotgun n\'est pas encore publié'}), 403

    participants = ShotgunParticipant.get_by_shotgun(shotgun_id)

    return jsonify([participant.to_dict() for participant in participants])


@shotguns_bp.route('/shotguns/<int:shotgun_id>/participants', methods=['POST'])
def add_participant(shotgun_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    data = request.json

    if not data.get('fname') or not data.get('lname'):
        return jsonify({'error': 'Prénom et nom sont obligatoires'}), 400

    if shotgun.max_participants is not None and len(shotgun.participants) >= shotgun.max_participants:
        return jsonify({'error': 'Ce shotgun a atteint sa capacité maximale'}), 400

    try:
        participant = ShotgunParticipant(
            shotgun_id=shotgun_id,
            fname=data.get('fname'),
            lname=data.get('lname'),
            email=data.get('email'),
            phone=data.get('phone'),
            study_year=data.get('study_year')
        )
        participant.save_to_db()

        return jsonify({'success': True, 'participant': participant.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@shotguns_bp.route('/shotguns/<int:shotgun_id>/participants/<int:participant_id>', methods=['PUT'])
def update_participant(shotgun_id, participant_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    participant = ShotgunParticipant.get_by_id(participant_id)
    if not participant or participant.shotgun_id != shotgun_id:
        return jsonify({'error': 'Participant non trouvé'}), 404

    data = request.json

    if not data.get('fname') or not data.get('lname'):
        return jsonify({'error': 'Prénom et nom sont obligatoires'}), 400

    try:
        participant.update({
            'fname': data.get('fname'),
            'lname': data.get('lname'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'study_year': data.get('study_year')
        })

        return jsonify({'success': True, 'participant': participant.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@shotguns_bp.route('/shotguns/<int:shotgun_id>/participants/<int:participant_id>', methods=['DELETE'])
def delete_participant(shotgun_id, participant_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    participant = ShotgunParticipant.get_by_id(participant_id)
    if not participant or participant.shotgun_id != shotgun_id:
        return jsonify({'error': 'Participant non trouvé'}), 404

    try:
        participant.delete_from_db()
        return jsonify({'success': True, 'message': 'Participant supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@shotguns_bp.route('/shotguns/<int:shotgun_id>/import-excel', methods=['POST'])
def import_excel(shotgun_id):
    if is_not_connected():
        return jsonify({'error': 'Non connecté'}), 401

    shotgun = Shotgun.get_by_id(shotgun_id)
    if not shotgun:
        return jsonify({'error': 'Shotgun non trouvé'}), 404

    if not is_admin():
        return jsonify({'error': 'Accès refusé'}), 403

    if 'excel_file' not in request.files:
        return jsonify({'error': 'Aucun fichier n\'a été envoyé'}), 400

    file = request.files['excel_file']

    if file.filename == '':
        return jsonify({'error': 'Aucun fichier n\'a été sélectionné'}), 400

    if not file.filename.endswith(('.xls', '.xlsx')):
        return jsonify({'error': 'Le fichier doit être un document Excel (.xls ou .xlsx)'}), 400

    try:
        df = pd.read_excel(file, engine='openpyxl')

        if shotgun.max_participants:
            current_count = ShotgunParticipant.query.filter_by(shotgun_id=shotgun_id).count()
            remaining_slots = shotgun.max_participants - current_count

            if remaining_slots <= 0:
                return jsonify({
                    'error': f'Impossible d\'importer: le shotgun a atteint sa capacité maximale ({shotgun.max_participants} participants)'}), 400

        mapped_columns = {
            'nom': 'lname',
            'prenom': 'fname',
            'email': 'email',
            'tel': 'phone',
            'telephone': 'phone',
            'annee d\'etude': 'study_year',
            'annee_d_etude': 'study_year',
            'annee': 'study_year'
        }

        # Normaliser les noms de colonnes (retirer les accents, mettre en minuscule)
        normalized_columns = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            import unicodedata
            col_normalized = unicodedata.normalize('NFKD', col_lower).encode('ASCII', 'ignore').decode('utf-8')

            for key in mapped_columns.keys():
                if col_normalized == key or col_lower == key:
                    normalized_columns[col] = mapped_columns[key]
                    break

        data = []
        for _, row in df.iterrows():
            entry = {}
            for col, mapped_col in normalized_columns.items():
                value = row[col]

                if pd.isna(value) or value == '':
                    entry[mapped_col] = None
                else:
                    # Convertir les valeurs numériques en chaînes
                    if isinstance(value, (int, float)):
                        entry[mapped_col] = str(int(value)) if value.is_integer() else str(value)
                    else:
                        entry[mapped_col] = str(value).strip()

            # Vérifier que l'entrée contient au moins les champs obligatoires
            if 'fname' in entry and 'lname' in entry:
                data.append(entry)

        # Si le shotgun a une capacité max, limiter le nombre d'entrées
        if shotgun.max_participants:
            if len(data) > remaining_slots:
                data = data[:remaining_slots]
                success, count = ShotgunParticipant.import_from_excel(shotgun_id, data)
                return jsonify({
                    'success': True,
                    'count': count,
                    'message': f'{count} participants importés avec succès (capacité maximale atteinte)'
                })

        success, count = ShotgunParticipant.import_from_excel(shotgun_id, data)

        if success:
            return jsonify({'success': True, 'count': count, 'message': f'{count} participants importés avec succès'})
        else:
            return jsonify({'error': 'Erreur lors de l\'importation'}), 500

    except Exception as e:
        db.session.rollback()
        print(f"Error importing Excel: {str(e)}")
        return jsonify({'error': str(e)}), 500


def check_shotgun_image(shotgun_id):
    """
    Vérifie si une image existe pour le shotgun et retourne son chemin
    """
    # Chemins possibles à vérifier basés sur les extensions courantes
    image_dir = os.getenv("FILES_DIR", "/var/www/public.losbarryachis.fr/public/shared/shotguns")
    shotgun_image_dir = os.path.join(image_dir, "shotguns")

    # Créer le dossier shotguns s'il n'existe pas
    os.makedirs(shotgun_image_dir, exist_ok=True)

    # Vérifier les extensions courantes
    for ext in ['jpg', 'jpeg', 'png', 'gif']:
        image_path = f"shotguns/{shotgun_id}.{ext}"
        full_path = os.path.join(image_dir, image_path)

        if os.path.exists(full_path):
            return image_path

    return None


def delete_shotgun_images(shotgun_id):
    """
    Supprime toutes les images associées à un shotgun
    """
    image_dir = os.getenv("FILES_DIR", "/var/www/public.losbarryachis.fr/public/shared/shotguns")
    shotgun_image_dir = os.path.join(image_dir, "shotguns")

    # Vérifier les extensions courantes
    for ext in ['jpg', 'jpeg', 'png', 'gif']:
        image_path = os.path.join(shotgun_image_dir, f"{shotgun_id}.{ext}")

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Erreur lors de la suppression de l'image {image_path}: {e}")