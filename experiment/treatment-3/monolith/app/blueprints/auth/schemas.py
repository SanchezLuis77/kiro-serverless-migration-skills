"""
Esquemas de validación para el módulo de autenticación.
Usa Marshmallow para serialización/deserialización.
"""
from marshmallow import Schema, fields, validate, ValidationError


class LoginSchema(Schema):
    """Valida los datos del formulario de login."""
    email = fields.Email(required=True, error_messages={'required': 'El email es requerido'})
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=6, error='La contraseña debe tener al menos 6 caracteres')
    )


class RegistroSchema(Schema):
    """Valida los datos para registrar un nuevo usuario (técnico/admin)."""
    nombre = fields.String(required=True, validate=validate.Length(min=2, max=100))
    apellido = fields.String(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=6)
    )
    rol = fields.String(
        load_default='tecnico',
        validate=validate.OneOf(['admin', 'tecnico'])
    )


class CambiarPasswordSchema(Schema):
    """Valida el cambio de contraseña."""
    password_actual = fields.String(required=True, load_only=True)
    password_nueva = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=6)
    )


# Instancias reutilizables
login_schema = LoginSchema()
registro_schema = RegistroSchema()
cambiar_password_schema = CambiarPasswordSchema()
