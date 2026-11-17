"""
Servicio de notificaciones usando AWS SNS/SES.

DIFERENCIA vs monolito:
- El monolito usaba un singleton con historial en memoria (solo logueaba).
- En Lambda, el historial en memoria no persiste entre invocaciones.
- Solución: SNS para publicar eventos → SES para envío de emails.

GAP IDENTIFICADO:
- Requiere que el email remitente esté verificado en SES (proceso manual en AWS Console).
- En sandbox de SES, solo se pueden enviar emails a direcciones verificadas.
- El ARN del topic SNS debe configurarse como variable de entorno SNS_TOPIC_ARN.
- No se implementó SMS (el monolito tampoco lo hacía realmente).
- El historial de notificaciones no se persiste (requeriría DynamoDB adicional).
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SES_SENDER = os.environ.get('SES_SENDER_EMAIL', 'noreply@taller.com')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')


def _get_ses_client():
    """Retorna cliente SES de boto3."""
    import boto3
    return boto3.client('ses', region_name=AWS_REGION)


def notificar_orden_creada(cliente_email: str, numero_orden: str) -> bool:
    """Envía email de confirmación de orden creada via SES."""
    asunto = f"Orden {numero_orden} recibida"
    cuerpo = (
        f"Estimado cliente, su orden de trabajo {numero_orden} "
        f"ha sido registrada exitosamente. Lo contactaremos pronto."
    )
    return _enviar_email(cliente_email, asunto, cuerpo)


def notificar_cambio_estado(
    cliente_email: str, numero_orden: str,
    estado_nuevo: str, notas: Optional[str] = None
) -> bool:
    """Envía email de cambio de estado via SES."""
    estados_legibles = {
        'en_diagnostico': 'En diagnóstico',
        'en_reparacion': 'En reparación',
        'completado': 'Completado - puede retirar su equipo',
        'cancelado': 'Cancelado',
    }
    estado_texto = estados_legibles.get(estado_nuevo, estado_nuevo)
    cuerpo = f"Su orden {numero_orden} cambió de estado: {estado_texto}."
    if notas:
        cuerpo += f" Nota del técnico: {notas}"
    return _enviar_email(cliente_email, f"Actualización orden {numero_orden}", cuerpo)


def notificar_orden_lista(cliente_email: str, numero_orden: str, total: float) -> bool:
    """Envía email de equipo listo para retirar via SES."""
    cuerpo = (
        f"Su equipo (orden {numero_orden}) está listo. "
        f"Total a pagar: ${total:.2f}. "
        f"Horario de atención: Lunes a Viernes 9:00-18:00."
    )
    return _enviar_email(cliente_email, f"Equipo listo para retirar - {numero_orden}", cuerpo)


def _enviar_email(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """
    Envía un email usando AWS SES.
    GAP: requiere verificación del dominio/email en SES.
    En modo sandbox solo funciona con emails verificados.
    """
    try:
        ses = _get_ses_client()
        ses.send_email(
            Source=SES_SENDER,
            Destination={'ToAddresses': [destinatario]},
            Message={
                'Subject': {'Data': asunto, 'Charset': 'UTF-8'},
                'Body': {'Text': {'Data': cuerpo, 'Charset': 'UTF-8'}},
            },
        )
        logger.info(f"[SES] Email enviado a {destinatario}: {asunto}")
        return True
    except Exception as e:
        # GAP: si SES falla, la notificación se pierde silenciosamente.
        # En producción debería publicar a una cola SQS de reintentos.
        logger.error(f"[SES] Error al enviar email a {destinatario}: {e}")
        return False
