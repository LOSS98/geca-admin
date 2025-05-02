from db import db
from datetime import datetime


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_email = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)

    task = db.relationship('Task', backref=db.backref('comments', lazy='dynamic', cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('comments', lazy='dynamic'))

    def __init__(self, task_id, user_email, content):
        self.task_id = task_id
        self.user_email = user_email
        self.content = content
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_email': self.user_email,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_name': f"{self.user.fname} {self.user.lname}" if self.user else self.user_email
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def notify_task_comment(self):
        from services.notifications import notification_service
        DEBUG = True

        if DEBUG:
            print("Starting comment notification")

        try:
            task = self.task

            if DEBUG:
                print(f"Task ID: {task.id}, Subject: {task.subject}")
                print(f"Total assignees: {len(task.assignees)}")
                print(f"Current user email: {self.user_email}")


            assigned_users = [f"{user.fname} {user.lname}" for user in task.assignees if
                              user.email != self.user_email]

            if DEBUG:
                print(f"Assignees to notify: {assigned_users}")


            if not assigned_users:
                from models.user import User
                creator = User.query.filter_by(email=task.assigned_by).first()

                if DEBUG:
                    print(f"No assignees found, notifying creator: {task.assigned_by}")

                if creator and creator.email != self.user_email:
                    assigned_users = [f"{creator.fname} {creator.lname}"]

                    if DEBUG:
                        print(f"Added creator to notification list: {assigned_users}")

            if assigned_users:
                if DEBUG:
                    print(f"Sending notifications to: {assigned_users}")

                notification_service.send_task_comment_notification(
                    task_subject=task.subject,
                    comment_author=f"{self.user.fname} {self.user.lname}",
                    comment_text=self.content,
                    assigned_users=assigned_users
                )
            else:
                if DEBUG:
                    print("No users to notify (commenter is the only person involved with the task)")

        except Exception as e:
            if DEBUG:
                print(f"Error during comment notification: {e}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")