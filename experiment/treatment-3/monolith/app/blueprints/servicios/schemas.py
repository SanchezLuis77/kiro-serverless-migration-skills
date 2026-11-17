"""
Esquemas de validación para el módulo de servicios.
"""
from marshmallow import Schema, fields, validate

CATEGORIAS_VALIDAS = ['electronico', 'electrodomestico', 'computacion', 'celular', 'otro']


class ServicioSchema(Schema):
    """Valida creación y actualización de servicios."""
    id = fields.Integer(dump_only=True)
    nombre = fields.String(required=True, validate=validate.Length(min=3, max=150))
    descripcion = fields.String(allow_none=True, load_default=None)
    precio_base = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0)
    )
    tiempo_estimado_horas = fields.Float(load_default=1.0, validate=validate.Range(min=0))
    categoria = fields.String(
        load_default='otro',
        validate=validate.OneOf(CATEGORIAS_VALIDAS)
    )
    activo = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ServicioUpdateSchema(Schema):
    """Permite actualización parcial de un servicio."""
    nombre = fields.String(validate=validate.Length(min=3, max=150))
    descripcion = fields.String(allow_none=True)
    precio_base = fields.Decimal(places=2, validate=validate.Range(min=0))
    tiempo_estimado_horas = fields.Float(validate=validate.Range(min=0))
    categoria = fields.String(validate=validate.OneOf(CATEGORIAS_VALIDAS))
    activo = fields.Boolean()


servicio_schema = ServicioSchema()
servicios_schema = ServicioSchema(many=True)
servicio_update_schema = ServicioUpdateSchema()
