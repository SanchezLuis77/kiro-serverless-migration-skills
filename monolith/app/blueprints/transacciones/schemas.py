"""
Esquemas de validación para el módulo de transacciones (órdenes de trabajo).
"""
from marshmallow import Schema, fields, validate

ESTADOS_VALIDOS = ['pendiente', 'en_diagnostico', 'en_reparacion', 'completado', 'cancelado']


class DetalleOrdenSchema(Schema):
    """Línea de detalle dentro de una orden de trabajo."""
    servicio_id = fields.Integer(required=True)
    precio_unitario = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))
    cantidad = fields.Integer(load_default=1, validate=validate.Range(min=1))
    notas = fields.String(allow_none=True, load_default=None)


class OrdenTrabajoSchema(Schema):
    """Valida la creación de una nueva orden de trabajo."""
    cliente_id = fields.Integer(required=True)
    tecnico_id = fields.Integer(allow_none=True, load_default=None)
    descripcion_problema = fields.String(required=True, validate=validate.Length(min=10))
    tipo_equipo = fields.String(allow_none=True, load_default=None)
    marca_equipo = fields.String(allow_none=True, load_default=None)
    modelo_equipo = fields.String(allow_none=True, load_default=None)
    fecha_estimada = fields.DateTime(allow_none=True, load_default=None)
    # Lista de servicios a incluir en la orden
    detalles = fields.List(fields.Nested(DetalleOrdenSchema), load_default=[])


class OrdenUpdateSchema(Schema):
    """Actualización parcial de una orden."""
    tecnico_id = fields.Integer(allow_none=True)
    descripcion_problema = fields.String(validate=validate.Length(min=10))
    notas_tecnico = fields.String(allow_none=True)
    tipo_equipo = fields.String(allow_none=True)
    marca_equipo = fields.String(allow_none=True)
    modelo_equipo = fields.String(allow_none=True)
    fecha_estimada = fields.DateTime(allow_none=True)


class CambioEstadoSchema(Schema):
    """Valida un cambio de estado de la orden."""
    estado = fields.String(required=True, validate=validate.OneOf(ESTADOS_VALIDOS))
    notas_tecnico = fields.String(allow_none=True, load_default=None)


orden_schema = OrdenTrabajoSchema()
orden_update_schema = OrdenUpdateSchema()
cambio_estado_schema = CambioEstadoSchema()
