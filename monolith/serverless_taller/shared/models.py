"""
Modelos SQLAlchemy para entorno serverless.

DIFERENCIA vs monolito:
- No dependen de Flask ni de flask_sqlalchemy.
- Usan declarative_base() de SQLAlchemy puro.
- Los métodos to_dict() son idénticos al monolito (reutilización directa).
- Se eliminó la dependencia de db.Column → Column de sqlalchemy directamente.

GAP IDENTIFICADO:
- Las relaciones lazy='dynamic' del monolito se mantienen pero en Lambda
  pueden causar N+1 queries si no se usan joins explícitos.
- El campo archivo_adjunto ahora almacena una clave S3, no una ruta local.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Float,
    Numeric, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from .db import Base


class Usuario(Base):
    __tablename__ = 'usuarios'

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False, default='tecnico')
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ordenes_asignadas = relationship(
        'OrdenTrabajo',
        back_populates='tecnico',
        foreign_keys='OrdenTrabajo.tecnico_id',
        lazy='select',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'rol': self.rol,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Cliente(Base):
    __tablename__ = 'clientes'

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=True)
    telefono = Column(String(20), nullable=False)
    direccion = Column(String(250), nullable=True)
    documento_identidad = Column(String(30), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ordenes = relationship(
        'OrdenTrabajo',
        back_populates='cliente',
        cascade='all, delete-orphan',
        lazy='select',
    )

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


class Servicio(Base):
    __tablename__ = 'servicios'

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio_base = Column(Numeric(10, 2), nullable=False, default=0.0)
    tiempo_estimado_horas = Column(Float, nullable=True, default=1.0)
    categoria = Column(String(50), nullable=False, default='otro')
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    detalles = relationship(
        'DetalleOrden',
        back_populates='servicio',
        cascade='all, delete-orphan',
        lazy='select',
    )

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


class OrdenTrabajo(Base):
    __tablename__ = 'ordenes_trabajo'

    id = Column(Integer, primary_key=True)
    numero_orden = Column(String(20), unique=True, nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=False)
    tecnico_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    estado = Column(String(20), nullable=False, default='pendiente')
    descripcion_problema = Column(Text, nullable=False)
    notas_tecnico = Column(Text, nullable=True)
    tipo_equipo = Column(String(100), nullable=True)
    marca_equipo = Column(String(100), nullable=True)
    modelo_equipo = Column(String(100), nullable=True)
    fecha_ingreso = Column(DateTime, default=datetime.utcnow)
    fecha_estimada = Column(DateTime, nullable=True)
    fecha_completado = Column(DateTime, nullable=True)
    # CAMBIO: ahora almacena clave S3 en lugar de ruta local
    archivo_adjunto = Column(String(500), nullable=True)
    total = Column(Numeric(10, 2), default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = relationship('Cliente', back_populates='ordenes', lazy='select')
    tecnico = relationship('Usuario', back_populates='ordenes_asignadas', lazy='select')
    detalles = relationship(
        'DetalleOrden',
        back_populates='orden',
        cascade='all, delete-orphan',
        lazy='joined',  # Mantener joined para evitar N+1 en to_dict con detalles
    )

    def calcular_total(self):
        return sum(d.subtotal() for d in self.detalles)

    def to_dict(self, incluir_detalles=False):
        data = {
            'id': self.id,
            'numero_orden': self.numero_orden,
            'estado': self.estado,
            'descripcion_problema': self.descripcion_problema,
            'notas_tecnico': self.notas_tecnico,
            'tipo_equipo': self.tipo_equipo,
            'marca_equipo': self.marca_equipo,
            'modelo_equipo': self.modelo_equipo,
            'total': float(self.total),
            'fecha_ingreso': self.fecha_ingreso.isoformat() if self.fecha_ingreso else None,
            'fecha_estimada': self.fecha_estimada.isoformat() if self.fecha_estimada else None,
            'fecha_completado': self.fecha_completado.isoformat() if self.fecha_completado else None,
            'archivo_adjunto': self.archivo_adjunto,
            'cliente_id': self.cliente_id,
            'tecnico_id': self.tecnico_id,
            'cliente_nombre': self.cliente.nombre_completo() if self.cliente else None,
            'tecnico_nombre': (
                f'{self.tecnico.nombre} {self.tecnico.apellido}' if self.tecnico else 'Sin asignar'
            ),
        }
        if incluir_detalles:
            data['detalles'] = [d.to_dict() for d in self.detalles]
        return data


class DetalleOrden(Base):
    __tablename__ = 'detalles_orden'

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey('ordenes_trabajo.id'), nullable=False)
    servicio_id = Column(Integer, ForeignKey('servicios.id'), nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    notas = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orden = relationship('OrdenTrabajo', back_populates='detalles')
    servicio = relationship('Servicio', back_populates='detalles')

    def subtotal(self):
        return float(self.precio_unitario) * self.cantidad

    def to_dict(self):
        return {
            'id': self.id,
            'servicio_id': self.servicio_id,
            'servicio_nombre': self.servicio.nombre if self.servicio else None,
            'precio_unitario': float(self.precio_unitario),
            'cantidad': self.cantidad,
            'subtotal': self.subtotal(),
            'notas': self.notas,
        }
