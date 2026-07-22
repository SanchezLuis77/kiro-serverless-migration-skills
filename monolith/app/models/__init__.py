"""
Exporta todos los modelos para que Flask-Migrate los detecte automáticamente.
"""
from .usuario import Usuario
from .cliente import Cliente
from .servicio import Servicio
from .orden_trabajo import OrdenTrabajo, DetalleOrden
