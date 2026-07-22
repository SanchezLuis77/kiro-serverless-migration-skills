"""
Modelo de Servicio: tipos de reparaciones y servicios que ofrece el taller.
Tabla: servicios
"""
from datetime import datetime
from app.extensions import db


class Servicio(db.Model):
    """
    Representa un tipo de servicio/reparación ofrecido por el taller.
    Ejemplos: 'Cambio de pantalla', 'Revisión de placa', 'Limpieza de laptop'

    Relación N:M con OrdenTrabajo a través de la tabla DetalleOrden.
    """
    __tablename__ = 'servicios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    # Precio base sugerido (el técnico puede ajustarlo en el detalle)
    precio_base = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)

    # Tiempo estimado de trabajo en horas
    tiempo_estimado_horas = db.Column(db.Float, nullable=True, default=1.0)

    # Categoría: 'electronico', 'electrodomestico', 'computacion', 'celular', 'otro'
    categoria = db.Column(db.String(50), nullable=False, default='otro')

    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación N:M con OrdenTrabajo a través de DetalleOrden
    detalles = db.relationship(
        'DetalleOrden',
        backref='servicio',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Servicio {self.nombre} [${self.precio_base}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'precio_base': float(self.precio_base),
            'tiempo_estimado_horas': self.tiempo_estimado_horas,
            'categoria': self.categoria,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
