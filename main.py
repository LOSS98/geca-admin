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

from db import db
from models.role import Role

from config import Config

#Main file
def create_app():
    load_dotenv()
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

    os.makedirs(Config.SESSION_FILE_DIR, exist_ok=True)
    import googleapiclient.discovery
    googleapiclient.discovery.BUILD_HTTP_CACHE_DISCOVERY = False


    app = Flask(__name__, static_folder='static')

    app.config.from_object(Config)

    Session(app)
    db.init_app(app)
    migrate = Migrate(app, db)

    if 0 :
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
            handlers=[
                logging.FileHandler("app.log"),
                logging.StreamHandler()
            ]
        )

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(tasks_bp, url_prefix='')
    app.register_blueprint(users_bp, url_prefix='')
    app.register_blueprint(finances_bp, url_prefix='')
    app.register_blueprint(locations_bp, url_prefix='')

    # Init db
    with app.app_context():
        db.create_all()
        Role.initialize_roles()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)