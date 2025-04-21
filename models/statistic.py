from db import db
from datetime import datetime


class Statistic(db.Model):
    __tablename__ = 'statistics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=False, unique=True)
    is_text = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    display_order = db.Column(db.Integer, default=999)

    def __init__(self, value, label, is_text=False, display_order=999):
        self.value = str(value)
        self.label = label
        self.is_text = is_text
        self.updated_at = datetime.now()
        self.display_order = display_order

    def to_dict(self):
        return {
            'id': self.id,
            'value': self.value,
            'label': self.label,
            'is_text': self.is_text,
            'display_order': self.display_order,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_all():
        return Statistic.query.order_by(Statistic.display_order.asc(), Statistic.id.asc()).all()

    @staticmethod
    def get_by_id(id):
        return Statistic.query.get(id)

    @staticmethod
    def get_by_label(label):
        return Statistic.query.filter_by(label=label).first()

    @staticmethod
    def increment(id, amount=1):
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
            return False

    @staticmethod
    def set_value(id, value):
        stat = Statistic.get_by_id(id)
        if not stat:
            return False

        stat.value = str(value)
        stat.updated_at = datetime.now()
        db.session.commit()
        return True

    @staticmethod
    def set_display_order(id, order):
        stat = Statistic.get_by_id(id)
        if not stat:
            return False

        try:
            stat.display_order = int(order)
            db.session.commit()
            return True
        except ValueError:
            return False

    @staticmethod
    def create(value, label, is_text=False, display_order=999):
        try:
            stat = Statistic(value=value, label=label, is_text=is_text, display_order=display_order)
            db.session.add(stat)
            db.session.commit()
            return stat
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete(id):
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
        default_stats = [
            {'value': '0', 'label': 'Crêpes commandées', 'is_text': False, 'display_order': 1},
            {'value': '0', 'label': 'Trajets en taxi', 'is_text': False, 'display_order': 2},
            {'value': '0', 'label': 'Appels au standard', 'is_text': False, 'display_order': 3},
            {'value': '0', 'label': 'Nombre d\'accidents', 'is_text': False, 'display_order': 4},
            {'value': '-', 'label': 'Le plus d\'appel au standard', 'is_text': True, 'display_order': 5}
        ]

        for stat_data in default_stats:
            existing_stat = Statistic.query.filter_by(label=stat_data['label']).first()
            if not existing_stat:
                stat = Statistic(
                    value=stat_data['value'],
                    label=stat_data['label'],
                    is_text=stat_data['is_text'],
                    display_order=stat_data.get('display_order', 999)
                )
                db.session.add(stat)

        db.session.commit()