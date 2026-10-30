from pathlib import Path
from flask import Flask
from config import Config
from .extensions import db


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    from .routes.main import bp as main_bp
    from .routes.api import bp as api_bp
    app.register_blueprint(main_bp); app.register_blueprint(api_bp, url_prefix="/api")
    from .cli import register_commands
    register_commands(app)
    with app.app_context(): db.create_all()
    return app
