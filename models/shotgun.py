from db import db
from datetime import datetime


class Shotgun(db.Model):
    __tablename__ = 'shotguns'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_participants = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    event_date = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=False)
    image_path = db.Column(db.String(255), nullable=True)

    creator = db.relationship('User', backref=db.backref('created_shotguns', lazy=True))
    participants = db.relationship('ShotgunParticipant', backref='shotgun', lazy=True, cascade="all, delete-orphan")

    def __init__(self, title, description=None, max_participants=None, event_date=None, is_published=False,
                 created_by=None, image_path=None):
        self.title = title
        self.description = description
        self.max_participants = max_participants
        self.event_date = event_date
        self.is_published = is_published
        self.created_by = created_by
        self.created_at = datetime.now()
        self.image_path = image_path

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'max_participants': self.max_participants,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'is_published': self.is_published,
            'created_by': self.created_by,
            'participants_count': len(self.participants),
            'image_path': self.image_path
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

    def update(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def publish(self):
        self.is_published = True
        db.session.commit()

    def unpublish(self):
        self.is_published = False
        db.session.commit()

    @staticmethod
    def get_by_id(shotgun_id):
        return Shotgun.query.get(shotgun_id)

    @staticmethod
    def get_all():
        return Shotgun.query.order_by(Shotgun.created_at.desc()).all()

    @staticmethod
    def get_published():
        return Shotgun.query.filter_by(is_published=True).order_by(Shotgun.created_at.desc()).all()


class ShotgunParticipant(db.Model):
    __tablename__ = 'shotgun_participants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shotgun_id = db.Column(db.Integer, db.ForeignKey('shotguns.id'), nullable=False)
    fname = db.Column(db.String(50), nullable=False)
    lname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    study_year = db.Column(db.String(20), nullable=True)
    registration_time = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def __init__(self, shotgun_id, fname, lname, email=None, phone=None, study_year=None):
        self.shotgun_id = shotgun_id
        self.fname = fname
        self.lname = lname
        self.email = email
        self.phone = phone
        self.study_year = study_year
        self.registration_time = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'shotgun_id': self.shotgun_id,
            'fname': self.fname,
            'lname': self.lname,
            'email': self.email,
            'phone': self.phone,
            'study_year': self.study_year,
            'registration_time': self.registration_time.isoformat() if self.registration_time else None
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

    def update(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    @staticmethod
    def get_by_id(participant_id):
        return ShotgunParticipant.query.get(participant_id)

    @staticmethod
    def get_by_shotgun(shotgun_id):
        return ShotgunParticipant.query.filter_by(shotgun_id=shotgun_id).order_by(
            ShotgunParticipant.registration_time).all()

    @staticmethod
    def import_from_excel(shotgun_id, data):
        count = 0
        for entry in data:
            if not entry.get('fname') or not entry.get('lname'):
                continue

            if not any([
                entry.get('email'),
                entry.get('phone'),
                entry.get('study_year')
            ]):
                continue

            participant = ShotgunParticipant(
                shotgun_id=shotgun_id,
                fname=entry.get('fname'),
                lname=entry.get('lname'),
                email=entry.get('email'),
                phone=entry.get('phone'),
                study_year=entry.get('study_year')
            )
            participant.save_to_db()
            count += 1

        return True, count