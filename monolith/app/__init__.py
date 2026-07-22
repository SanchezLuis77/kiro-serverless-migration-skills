"""
Factory principal de la aplicación Flask - Taller PyME.
Dominio: Taller de reparaciones electrónicas y de electrodomésticos.
"""
import os
import logging
from flask import Flask
from .config import config
from .extensions import db, migrate, jwt, bcrypt


def create_app(env_name: str = 'default') -> Flask:
    """
    Crea y configura la instancia de Flask usando el patrón Application Factory.
    """
    app = Flask(__name__, instance_relative_config=False)

    # Cargar configuración según entorno
    app.config.from_object(config[env_name])

    # Asegurar que la carpeta de uploads exista
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ---------------------------------------------------------------
    # Configurar logging centralizado
    # ---------------------------------------------------------------
    _configurar_logging(app)

    # ---------------------------------------------------------------
    # Inicializar extensiones con la app
    # ---------------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # ---------------------------------------------------------------
    # Registrar blueprints
    # ---------------------------------------------------------------
    _registrar_blueprints(app)

    # ---------------------------------------------------------------
    # Registrar comandos CLI personalizados
    # ---------------------------------------------------------------
    _registrar_comandos_cli(app)

    # ---------------------------------------------------------------
    # Manejadores de errores globales
    # ---------------------------------------------------------------
    _registrar_manejadores_error(app)

    app.logger.info(f"Aplicación iniciada en modo: {env_name}")
    return app


def _configurar_logging(app: Flask) -> None:
    """Configura el sistema de logging centralizado de la aplicación."""
    nivel = getattr(logging, app.config.get('LOG_LEVEL', 'DEBUG'))
    logging.basicConfig(
        level=nivel,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    app.logger.setLevel(nivel)


def _registrar_blueprints(app: Flask) -> None:
    """Registra todos los blueprints de la aplicación."""
    from .blueprints.auth.routes import auth_bp
    from .blueprints.clientes.routes import clientes_bp
    from .blueprints.servicios.routes import servicios_bp
    from .blueprints.transacciones.routes import transacciones_bp
    from .blueprints.reportes.routes import reportes_bp

    app.register_blueprint(auth_bp,          url_prefix='/api/auth')
    app.register_blueprint(clientes_bp,      url_prefix='/api/clientes')
    app.register_blueprint(servicios_bp,     url_prefix='/api/servicios')
    app.register_blueprint(transacciones_bp, url_prefix='/api/transacciones')
    app.register_blueprint(reportes_bp,      url_prefix='/api/reportes')


def _registrar_comandos_cli(app: Flask) -> None:
    """Registra comandos Flask CLI personalizados."""
    import click

    @app.cli.command('seed')
    @click.option('--reset', is_flag=True, default=False,
                  help='Elimina todos los datos antes de insertar')
    def seed_command(reset):
        """Pobla la base de datos con datos de prueba."""
        from seeds.seed_data import ejecutar_seed
        ejecutar_seed(app, reset=reset)
        click.echo("Seed completado exitosamente.")

    @app.cli.command('init-db')
    def init_db_command():
        """Crea todas las tablas (solo para desarrollo sin migraciones)."""
        db.create_all()
        click.echo("Base de datos inicializada.")


def _registrar_manejadores_error(app: Flask) -> None:
    """Registra manejadores de errores HTTP globales."""
    from flask import jsonify

    @app.errorhandler(404)
    def no_encontrado(e):
        return jsonify({'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(400)
    def solicitud_invalida(e):
        return jsonify({'error': 'Solicitud inválida', 'detalle': str(e)}), 400

    @app.errorhandler(500)
    def error_interno(e):
        app.logger.error(f"Error interno: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
