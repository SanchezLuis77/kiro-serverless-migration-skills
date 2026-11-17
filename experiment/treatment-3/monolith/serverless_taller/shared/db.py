"""
Gestión de conexión a base de datos para entorno Lambda.

DIFERENCIA CLAVE vs monolito:
- El monolito usa Flask-SQLAlchemy con connection pool gestionado por Gunicorn.
- En Lambda, cada invocación puede ser una instancia nueva (cold start).
- Se usa un patrón de conexión lazy con reutilización entre invocaciones
  del mismo contenedor (warm Lambda).

GAP IDENTIFICADO:
- Flask-Migrate no aplica aquí. Las migraciones deben ejecutarse externamente
  (ej: desde un Lambda de inicialización, GitHub Actions, o RDS Proxy).
- SQLite no es viable en Lambda (filesystem efímero). Se requiere RDS o Aurora Serverless.
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# Base declarativa compartida por todos los modelos
Base = declarative_base()

# Conexión reutilizada entre invocaciones del mismo contenedor Lambda (warm)
_engine = None
_SessionLocal = None


def get_engine():
    """
    Retorna el engine de SQLAlchemy, creándolo si no existe.
    Patrón de reutilización de conexión entre invocaciones Lambda calientes.
    """
    global _engine
    if _engine is None:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError("DATABASE_URL no configurada en variables de entorno")

        # pool_pre_ping verifica que la conexión siga activa (importante en Lambda)
        # pool_size reducido porque Lambda tiene concurrencia limitada por función
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
            pool_recycle=300,  # Reciclar conexiones cada 5 min (evita timeouts de RDS)
            echo=os.environ.get('SQL_ECHO', 'false').lower() == 'true',
        )
        logger.info("Engine de base de datos creado")
    return _engine


def get_session():
    """
    Retorna una sesión de SQLAlchemy.
    IMPORTANTE: el llamador es responsable de cerrar la sesión (usar context manager).
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal()


class DBSession:
    """
    Context manager para sesiones de base de datos en Lambda.
    Garantiza commit en éxito y rollback en error.

    Uso:
        with DBSession() as session:
            cliente = session.query(Cliente).get(1)
    """
    def __enter__(self):
        self.session = get_session()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
            logger.error(f"Rollback por excepción: {exc_type.__name__}: {exc_val}")
        else:
            try:
                self.session.commit()
            except Exception as e:
                self.session.rollback()
                logger.error(f"Error en commit: {e}")
                raise
        finally:
            self.session.close()
        return False  # No suprimir excepciones
