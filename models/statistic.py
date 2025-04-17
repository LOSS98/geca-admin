from db import db
from datetime import datetime


class Statistic(db.Model):
    __tablename__ = 'statistics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __init__(self, key, value, label):
        self.key = key
        self.value = str(value)
        self.label = label
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'label': self.label,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_all():
        return Statistic.query.all()

    @staticmethod
    def get_by_key(key):
        return Statistic.query.filter_by(key=key).first()

    @staticmethod
    def increment(key, amount=1):
        stat = Statistic.get_by_key(key)
        if not stat:
            return False

        try:
            current_value = int(stat.value)
            current_value += amount
            stat.value = str(current_value)
            stat.updated_at = datetime.now()
            db.session.commit()
            return True
        except ValueError:
            return False

    @staticmethod
    def set_value(key, value):
        stat = Statistic.get_by_key(key)
        if not stat:
            return False

        stat.value = str(value)
        stat.updated_at = datetime.now()
        db.session.commit()
        return True

    @staticmethod
    def initialize_stats():
        default_stats = [
            {'key': 'crepes', 'value': '1895', 'label': 'Crêpes commandées'},
            {'key': 'taxis', 'value': '57', 'label': 'Trajets en taxi'},
            {'key': 'appels', 'value': '368', 'label': 'Appels au standard'},
            {'key': 'accidents', 'value': '10', 'label': 'Nombre d\'accidents'},
            {'key': 'top_caller', 'value': 'Kevin', 'label': 'Le plus d\'appel au standard'}
        ]

        for stat_data in default_stats:
            stat = Statistic.get_by_key(stat_data['key'])
            if not stat:
                stat = Statistic(
                    key=stat_data['key'],
                    value=stat_data['value'],
                    label=stat_data['label']
                )
                db.session.add(stat)

        db.session.commit()