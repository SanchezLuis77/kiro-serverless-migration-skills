"""
Modelos de OrdenTrabajo y DetalleOrden.
Tablas: ordenes_trabajo, detalles_orden

OrdenTrabajo: entidad transaccional central del sistema.
DetalleOrden: líneas de trabajo dentro de una orden (tabla de unión enriquecida).
"""
from datetime import datetime
from app.extensions import db


class OrdenTrabajo(db.Model):
    """
    Representa una orden de trabajo (reparación ingresada al taller).

    Relaciones:
    - N:1 con Cliente  (cliente_id)
    - N:1 con Usuario  (tecnico_id)
    - 1:N con DetalleOrden
    """
    __tablename__ = 'ordenes_trabajo'

    id = db.Column(db.Integer, primary_key=True)

    # Número de orden legible, ej: "OT-2024-0001"
    numero_orden = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Claves foráneas
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # Estado del flujo de trabajo
    # pendiente → en_diagnostico → en_reparacion → completado | cancelado
    estado = db.Column(db.String(20), nullable=False, default='pendiente')

    # Descripción del problema reportada por el cliente
    descripcion_problema = db.Column(db.Text, nullable=False)

    # Notas técnicas internas (no visibles al cliente)
    notas_tecnico = db.Column(db.Text, nullable=True)

    # Tipo de equipo a reparar
    tipo_equipo = db.Column(db.String(100), nullable=True)
    marca_equipo = db.Column(db.String(100), nullable=True)
    modelo_equipo = db.Column(db.String(100), nullable=True)

    # Fechas del ciclo de vida
    fecha_ingreso = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_estimada = db.Column(db.DateTime, nullable=True)
    fecha_completado = db.Column(db.DateTime, nullable=True)

    # Archivo adjunto (foto del equipo, diagnóstico escaneado, etc.)
    # Anti-patrón intencional: ruta local al archivo en el servidor
    archivo_adjunto = db.Column(db.String(300), nullable=True)

    # Total calculado (redundancia intencional — también calculable desde detalles)
    total = db.Column(db.Numeric(10, 2), default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación 1:N con líneas de detalle
    detalles = db.relationship(
        'DetalleOrden',
        backref='orden',
        lazy='joined',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<OrdenTrabajo {self.numero_orden} [{self.estado}]>'

    def calcular_total(self):
        """Recalcula el total sumando los detalles. Anti-patrón: lógica en el modelo."""
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
            # Datos desnormalizados del cliente (anti-patrón típico de PyME)
            'cliente_nombre': self.cliente.nombre_completo() if self.cliente else None,
            'tecnico_nombre': (
                f'{self.tecnico.nombre} {self.tecnico.apellido}' if self.tecnico else 'Sin asignar'
            ),
        }
        if incluir_detalles:
            data['detalles'] = [d.to_dict() for d in self.detalles]
        return data


class DetalleOrden(db.Model):
    """
    Línea de trabajo dentro de una orden: qué servicio se realizó y a qué precio.
    Tabla de unión enriquecida entre OrdenTrabajo y Servicio.
    """
    __tablename__ = 'detalles_orden'

    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'), nullable=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey('servicios.id'), nullable=False)

    # Precio al momento de crear el detalle (puede diferir del precio_base actual)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)

    # Notas específicas del detalle (ej: "se usó repuesto genérico")
    notas = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def subtotal(self):
        return float(self.precio_unitario) * self.cantidad

    def __repr__(self):
        return f'<DetalleOrden orden={self.orden_id} servicio={self.servicio_id}>'

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
