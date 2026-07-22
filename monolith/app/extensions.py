"""
Instancias de extensiones Flask compartidas.
Se inicializan aquí y se vinculan a la app en create_app().
Patrón típico de PyME: extensiones globales para simplicidad.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

# ORM principal
db = SQLAlchemy()

# Gestor de migraciones de base de datos
migrate = Migrate()

# Autenticación mediante JWT
jwt = JWTManager()

# Hash seguro de contraseñas
bcrypt = Bcrypt()
