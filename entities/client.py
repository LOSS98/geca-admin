from db import db
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fname = db.Column(db.String(50), nullable=False)
    lname = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    birthdate = db.Column(db.Date, nullable=True)
    study_year = db.Column(db.Integer, nullable=True)
    study_field = db.Column(db.String(100), nullable=True)

    def __init__(self, fname, lname, phone, email, birthdate, study_year, study_field):
        self.fname = fname
        self.lname = lname
        self.phone = phone
        self.email = email
        self.birthdate = birthdate
        self.study_year = study_year
        self.study_field = study_field

    def to_dict(self):
        return {
            'id': self.id,
            'fname': self.fname,
            'lname': self.lname,
            'phone': self.phone,
            'email': self.email,
            'birthdate': self.birthdate,
            'study_year': self.study_year,
            'study_field': self.study_field
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

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

    def get_email(self):
        return self.email

    def set_email(self, email):
        self.email = email
        db.session.commit()

    def get_birthdate(self):
        return self.birthdate

    def set_birthdate(self, birthdate):
        self.birthdate = birthdate
        db.session.commit()

    def get_study_year(self):
        return self.study_year

    def set_study_year(self, study_year):
        self.study_year = study_year
        db.session.commit()

    def get_study_field(self):
        return self.study_field

    def set_study_field(self, study_field):
        self.study_field = study_field
        db.session.commit()

    @staticmethod
    def create(fname, lname, phone=None, email=None, birthdate=None, study_year=None, study_field=None):
        new_client = Client(fname=fname, lname=lname, phone=phone,
                        email=email, birthdate=birthdate, study_year=study_year, study_field=study_field)
        db.session.add(new_client)
        db.session.commit()
        return new_client

    @staticmethod
    def get_all_names():
        return [f'{client.lname} {client.fname}' for client in Client.query.all()]

    @staticmethod
    def get_all_emails():
        return [client.email for client in Client.query.all()]

    @staticmethod
    def get_all_phones():
        return [client.phone for client in Client.query.all()]

    @staticmethod
    def get_by_email(email):
        return Client.query.filter_by(email=email).first()

    @staticmethod
    def get_by_phone(phone):
        return Client.query.filter_by(phone=phone).first()