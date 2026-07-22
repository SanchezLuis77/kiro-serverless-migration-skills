"""
Configuración de la aplicación Flask.
Se leen variables de entorno desde el archivo .env
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base compartida por todos los entornos."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-cambiar-en-produccion')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///taller.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-cambiar-en-produccion')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB máximo por archivo

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')

    # Extensiones permitidas para archivos adjuntos
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}


class DevelopmentConfig(Config):
    """Configuración de desarrollo: debug activo."""
    DEBUG = True
    SQLALCHEMY_ECHO = False  # True para ver SQL generado


class ProductionConfig(Config):
    """Configuración de producción: sin debug."""
    DEBUG = False
    SQLALCHEMY_ECHO = False


# Mapa de configuraciones disponibles
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
