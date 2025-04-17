from db import db
from datetime import datetime


class Statistic(db.Model):
    __tablename__ = 'statistics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=False, unique=True)
    is_text = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __init__(self, value, label, is_text=False):
        self.value = str(value)
        self.label = label
        self.is_text = is_text
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'value': self.value,
            'label': self.label,
            'is_text': self.is_text,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_all():
        """Récupère toutes les statistiques de la base de données"""
        return Statistic.query.order_by(Statistic.id.asc()).all()

    @staticmethod
    def get_by_id(id):
        """Récupère une statistique par son ID"""
        return Statistic.query.get(id)

    @staticmethod
    def get_by_label(label):
        """Récupère une statistique par son libellé"""
        return Statistic.query.filter_by(label=label).first()

    @staticmethod
    def increment(id, amount=1):
        """Incrémente la valeur d'une statistique du montant spécifié

        Accepte également des valeurs négatives pour décrémenter
        """
        stat = Statistic.get_by_id(id)
        if not stat or stat.is_text:
            return False

        try:
            current_value = int(stat.value)
            current_value += amount
            stat.value = str(current_value)
            stat.updated_at = datetime.now()
            db.session.commit()
            return True
        except ValueError:
            # Si la valeur n'est pas un nombre, ne rien faire
            return False

    @staticmethod
    def set_value(id, value):
        """Définit la valeur d'une statistique à la valeur spécifiée"""
        stat = Statistic.get_by_id(id)
        if not stat:
            return False

        stat.value = str(value)
        stat.updated_at = datetime.now()
        db.session.commit()
        return True

    @staticmethod
    def create(value, label, is_text=False):
        """Crée une nouvelle statistique"""
        try:
            stat = Statistic(value=value, label=label, is_text=is_text)
            db.session.add(stat)
            db.session.commit()
            return stat
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete(id):
        """Supprime une statistique par son ID"""
        stat = Statistic.get_by_id(id)
        if not stat:
            return False

        try:
            db.session.delete(stat)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def initialize_stats():
        """Initialise les statistiques par défaut dans la base de données"""
        default_stats = [
            {'value': '0', 'label': 'Crêpes commandées', 'is_text': False},
            {'value': '0', 'label': 'Trajets en taxi', 'is_text': False},
            {'value': '368', 'label': 'Appels au standard', 'is_text': False},
            {'value': '10', 'label': 'Nombre d\'accidents', 'is_text': False},
            {'value': 'khalil', 'label': 'Le plus d\'appel au standard', 'is_text': True}
        ]

        for stat_data in default_stats:
            existing_stat = Statistic.query.filter_by(label=stat_data['label']).first()
            if not existing_stat:
                stat = Statistic(
                    value=stat_data['value'],
                    label=stat_data['label'],
                    is_text=stat_data['is_text']
                )
                db.session.add(stat)

        db.session.commit()