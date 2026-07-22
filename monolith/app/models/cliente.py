"""
Modelo de Cliente: personas que traen equipos al taller.
Tabla: clientes
"""
from datetime import datetime
from app.extensions import db


class Cliente(db.Model):
    """
    Representa a un cliente del taller.
    Relación 1:N con OrdenTrabajo (un cliente puede tener múltiples órdenes).
    """
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    telefono = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(250), nullable=True)

    # Identificación fiscal (RUT/DNI) — útil para facturación
    documento_identidad = db.Column(db.String(30), nullable=True)

    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación 1:N con órdenes de trabajo
    ordenes = db.relationship(
        'OrdenTrabajo',
        backref='cliente',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Cliente {self.nombre} {self.apellido}>'

    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'nombre_completo': self.nombre_completo(),
            'email': self.email,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'documento_identidad': self.documento_identidad,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
