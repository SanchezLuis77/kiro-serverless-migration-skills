"""
Punto de entrada de la aplicación Taller PyME.
Ejecutar con: python run.py
"""
import os
from app import create_app

# Seleccionar configuración según variable de entorno
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', False)
    )
