"""
Modelo de Usuario: técnicos y administradores del taller.
Tabla: usuarios
"""
from datetime import datetime
from app.extensions import db


class Usuario(db.Model):
    """
    Representa a un empleado del taller (técnico o administrador).
    Usado para autenticación JWT y asignación de órdenes de trabajo.
    """
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Rol: 'admin' puede ver reportes y gestionar todo;
    # 'tecnico' solo gestiona sus órdenes asignadas
    rol = db.Column(db.String(20), nullable=False, default='tecnico')

    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación 1:N con órdenes de trabajo asignadas
    ordenes_asignadas = db.relationship(
        'OrdenTrabajo',
        backref='tecnico',
        lazy='dynamic',
        foreign_keys='OrdenTrabajo.tecnico_id'
    )

    def __repr__(self):
        return f'<Usuario {self.email} [{self.rol}]>'

    def to_dict(self):
        """Serialización básica — sin exponer password_hash."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'rol': self.rol,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
