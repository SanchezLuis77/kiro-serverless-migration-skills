"""
Esquemas de validación para el módulo de clientes.
"""
from marshmallow import Schema, fields, validate


class ClienteSchema(Schema):
    """Valida creación y actualización de clientes."""
    id = fields.Integer(dump_only=True)
    nombre = fields.String(required=True, validate=validate.Length(min=2, max=100))
    apellido = fields.String(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(allow_none=True, load_default=None)
    telefono = fields.String(required=True, validate=validate.Length(min=7, max=20))
    direccion = fields.String(allow_none=True, load_default=None)
    documento_identidad = fields.String(allow_none=True, load_default=None)
    activo = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ClienteUpdateSchema(Schema):
    """Valida actualizaciones parciales de cliente (todos los campos opcionales)."""
    nombre = fields.String(validate=validate.Length(min=2, max=100))
    apellido = fields.String(validate=validate.Length(min=2, max=100))
    email = fields.Email(allow_none=True)
    telefono = fields.String(validate=validate.Length(min=7, max=20))
    direccion = fields.String(allow_none=True)
    documento_identidad = fields.String(allow_none=True)


# Instancias
cliente_schema = ClienteSchema()
clientes_schema = ClienteSchema(many=True)
cliente_update_schema = ClienteUpdateSchema()
