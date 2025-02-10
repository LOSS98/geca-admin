from email.policy import default

from flask_sqlalchemy import SQLAlchemy

from db import db


class User(db.Model):
    __tablename__ = 'users'
    email = db.Column(db.String(120), primary_key=True)
    fname = db.Column(db.String(50), nullable=False)
    lname = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    long = db.Column(db.Float, nullable=True)
    lat = db.Column(db.Float, nullable=True)
    location_date = db.Column(db.DateTime, nullable=True)
    notification_token = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), nullable=False, default='member')


    # Self-referencing relationship
    manager_email = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=True)
    manager = db.relationship('User', remote_side=[email], backref='subordinates')

    def __init__(self, email, fname, lname, phone, notification_token=None, long=None, lat=None, location_date=None, role=None, manager_email=None):
        self.email = email
        self.fname = fname
        self.lname = lname
        self.phone = phone
        self.long = long
        self.lat = lat
        self.location_date = location_date
        self.notification_token = notification_token
        self.role = role or 'member'
        self.manager_email = manager_email

    # Getters and setters with database updates
    def get_fname(self):
        return self.fname

    def set_fname(self, fname):
        self.fname = fname
        db.session.commit()

    def get_lname(self):
        return self.lname

    def set_lname(self, lname):
        self.lname = lname
        db.session.commit()

    def get_phone(self):
        return self.phone

    def set_phone(self, phone):
        self.phone = phone
        db.session.commit()

    def set_location(self, long,  lat, location_date):
        self.long = long
        self.lat = lat
        self.location_date = location_date
        db.session.commit()

    def get_email(self):
        return self.email

    def get_notification_token(self):
        return self.notification_token

    def set_notification_token(self, notification_token):
        self.notification_token = notification_token
        db.session.commit()

    def get_role(self):
        return self.role

    def set_role(self, role):
        self.role = role
        db.session.commit()

    def get_manager_email(self):
        return self.manager_email

    def set_manager_email(self, manager_email):
        self.manager_email = manager_email
        db.session.commit()

    def get_location(self):
        return {'long': self.long, 'lat': self.lat, 'location_date': self.location_date}

    @staticmethod
    def create(email, fname, lname, phone, notification_token=None, role=None, manager_email=None):
        new_user = User(email=email, fname=fname, lname=lname, phone=phone,
                        notification_token=notification_token, role=role, manager_email=manager_email)
        db.session.add(new_user)
        db.session.commit()
        return new_user

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_dict(self):
        return {
            'email': self.email,
            'fname': self.fname,
            'lname': self.lname,
            'phone': self.phone,
            'notification_token': self.notification_token,
            'role': self.role,
            'manager_email': self.manager_email
        }

    def __repr__(self):
        return f"<User {self.fname} {self.lname}, Role: {self.role}>"

    @staticmethod
    def get_all_names():
        return [f'{user.lname} {user.fname}' for user in User.query.all()]

    @staticmethod
    def get_all_emails():
        return [user.email for user in User.query.all()]

    @staticmethod
    def get_all_locations():
        return [{'long': user.long, 'lat': user.lat, 'location_date': user.location_date} for user in User.query.all()]

    @staticmethod
    def get_by_email(email):
        return User.query.filter_by(email=email).first()

    @staticmethod
    def get_by_phone(phone):
        return User.query.filter_by(phone=phone).first()
