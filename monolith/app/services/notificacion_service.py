"""
Servicio de notificaciones (simulado).

Anti-patrón intencional: servicio singleton que simula envío de emails/SMS.
En producción real conectaría a un SMTP o servicio de mensajería.
Al migrar a Lambda habría que reemplazarlo por SNS/SES de AWS.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class NotificacionService:
    """
    Singleton para gestión de notificaciones al cliente.
    Por ahora solo loguea — no envía nada real.
    """
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._historial = []  # Estado en memoria (anti-patrón)
        return cls._instancia

    def notificar_orden_creada(self, cliente_email: str, numero_orden: str) -> bool:
        """Notifica al cliente que su orden fue registrada."""
        mensaje = (
            f"Estimado cliente, su orden de trabajo {numero_orden} "
            f"ha sido registrada exitosamente. Lo contactaremos pronto."
        )
        return self._enviar(cliente_email, f"Orden {numero_orden} recibida", mensaje)

    def notificar_cambio_estado(
        self, cliente_email: str, numero_orden: str,
        estado_nuevo: str, notas: Optional[str] = None
    ) -> bool:
        """Notifica al cliente sobre un cambio de estado de su orden."""
        estados_legibles = {
            'en_diagnostico': 'En diagnóstico',
            'en_reparacion': 'En reparación',
            'completado': 'Completado - puede retirar su equipo',
            'cancelado': 'Cancelado',
        }
        estado_texto = estados_legibles.get(estado_nuevo, estado_nuevo)
        mensaje = f"Su orden {numero_orden} cambió de estado: {estado_texto}."
        if notas:
            mensaje += f" Nota del técnico: {notas}"
        return self._enviar(cliente_email, f"Actualización orden {numero_orden}", mensaje)

    def notificar_orden_lista(self, cliente_email: str, numero_orden: str, total: float) -> bool:
        """Notifica al cliente que su equipo está listo para retirar."""
        mensaje = (
            f"Su equipo (orden {numero_orden}) está listo. "
            f"Total a pagar: ${total:.2f}. "
            f"Horario de atención: Lunes a Viernes 9:00-18:00."
        )
        return self._enviar(cliente_email, f"Equipo listo para retirar - {numero_orden}", mensaje)

    def _enviar(self, destinatario: str, asunto: str, cuerpo: str) -> bool:
        """
        Simulación de envío. En producción usaría SMTP o un servicio externo.
        Guarda el historial en memoria (estado compartido — problema para Lambda).
        """
        registro = {
            'timestamp': datetime.utcnow().isoformat(),
            'destinatario': destinatario,
            'asunto': asunto,
            'cuerpo': cuerpo,
        }
        self._historial.append(registro)
        logger.info(f"[NOTIFICACION] Para: {destinatario} | Asunto: {asunto}")
        return True

    def obtener_historial(self) -> list:
        """Retorna el historial de notificaciones enviadas (solo en memoria)."""
        return list(self._historial)


# Singleton global
notificacion_service = NotificacionService()
