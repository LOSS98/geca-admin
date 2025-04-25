from flask import Flask
from flask_migrate import Migrate
from flask_session import Session
import os
from dotenv import load_dotenv
import logging

from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.users import users_bp
from routes.finances import finances_bp
from routes.locations import locations_bp
from routes.stats import stats_bp
from routes.shotguns import shotguns_bp
from routes.files import files_bp
import pytz

from db import db
from models.role import Role
from models.comment import Comment
from models.statistic import Statistic
from models.shotgun import Shotgun, ShotgunParticipant

from config import Config

def create_app():
    load_dotenv()
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

    os.makedirs(Config.SESSION_FILE_DIR, exist_ok=True)
    import googleapiclient.discovery
    googleapiclient.discovery.BUILD_HTTP_CACHE_DISCOVERY = False

    app = Flask(__name__, static_folder='static')
    app.config['IN_MAINTENANCE'] = os.getenv('IN_MAINTENANCE', '0') == '1'
    app.config['TIMEZONE'] = 'Europe/Paris'

    @app.context_processor
    def inject_maintenance():
        return dict(in_maintenance=app.config['IN_MAINTENANCE'])

    @app.context_processor
    def inject_maintenance():
        return {"maintenance": os.getenv("MAINTENANCE", "0") == "1"}

    app.config.from_object(Config)

    Session(app)
    db.init_app(app)
    migrate = Migrate(app, db)

    if 0:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
            handlers=[
                logging.FileHandler("app.log"),
                logging.StreamHandler()
            ]
        )

    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(tasks_bp, url_prefix='')
    app.register_blueprint(users_bp, url_prefix='')
    app.register_blueprint(finances_bp, url_prefix='')
    app.register_blueprint(locations_bp, url_prefix='')
    app.register_blueprint(stats_bp, url_prefix='')
    app.register_blueprint(shotguns_bp, url_prefix='')
    app.register_blueprint(files_bp, url_prefix='')

    with app.app_context():
        db.create_all()
        Role.initialize_roles()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)