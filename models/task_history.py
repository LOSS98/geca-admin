from datetime import datetime
from db import db



class TaskHistory(db.Model):
    __tablename__ = 'task_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_email = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)


    task = db.relationship('Task', backref=db.backref('history_entries', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('task_history', lazy='dynamic'))

    def __init__(self, task_id, user_email, action):
        self.task_id = task_id
        self.user_email = user_email
        self.action = action
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_email': self.user_email,
            'action': self.action,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()