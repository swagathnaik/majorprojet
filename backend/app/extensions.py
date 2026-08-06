"""
Shared Flask extensions.
Initialized here, then bound to the app in create_app().
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
