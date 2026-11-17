"""
Servicio de caché distribuido usando ElastiCache Redis.

DIFERENCIA vs monolito:
- El monolito usaba un dict en memoria (CacheService singleton).
- En Lambda, cada instancia tiene su propio espacio de memoria → el caché
  en memoria no se comparte entre invocaciones concurrentes.
- Solución: ElastiCache Redis como caché externo compartido.

GAP IDENTIFICADO:
- ElastiCache Redis solo es accesible desde dentro de una VPC.
- Configurar Lambda dentro de una VPC aumenta el cold start (~500ms extra).
- La URL de Redis debe configurarse como variable de entorno REDIS_URL.
- Si Redis no está disponible, se hace fallback a sin caché (degraded mode).
- No se implementó serialización de objetos complejos (solo JSON-serializable).
"""
import os
import json
import logging
from typing import Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class DecimalDatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisCache:
    """
    Wrapper de Redis para uso en Lambda.
    Implementa la misma interfaz que el CacheService del monolito.
    """
    _client = None

    def _get_client(self):
        """Conexión lazy a Redis, reutilizada entre invocaciones calientes."""
        if self._client is None:
            redis_url = os.environ.get('REDIS_URL')
            if not redis_url:
                logger.warning("REDIS_URL no configurada — caché deshabilitado")
                return None
            try:
                import redis
                self._client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._client.ping()
                logger.info("Conexión a Redis establecida")
            except Exception as e:
                logger.error(f"No se pudo conectar a Redis: {e}")
                self._client = None
        return self._client

    def get(self, clave: str) -> Optional[Any]:
        client = self._get_client()
        if not client:
            return None
        try:
            valor = client.get(clave)
            if valor is None:
                return None
            return json.loads(valor)
        except Exception as e:
            logger.error(f"Error al leer caché Redis [{clave}]: {e}")
            return None

    def set(self, clave: str, valor: Any, ttl_segundos: int = 300) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            serializado = json.dumps(valor, cls=DecimalDatetimeEncoder)
            client.setex(clave, ttl_segundos, serializado)
            return True
        except Exception as e:
            logger.error(f"Error al escribir caché Redis [{clave}]: {e}")
            return False

    def delete(self, clave: str) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            client.delete(clave)
            return True
        except Exception as e:
            logger.error(f"Error al eliminar caché Redis [{clave}]: {e}")
            return False

    def invalidar_patron(self, patron: str) -> int:
        """
        Elimina claves que coincidan con el patrón.
        GAP: Redis SCAN es O(N) — en producción con muchas claves puede ser lento.
        Alternativa: usar prefijos de clave y TTL cortos en lugar de invalidación activa.
        """
        client = self._get_client()
        if not client:
            return 0
        try:
            claves = list(client.scan_iter(f'*{patron}*'))
            if claves:
                client.delete(*claves)
            return len(claves)
        except Exception as e:
            logger.error(f"Error al invalidar patrón [{patron}]: {e}")
            return 0

    def estadisticas(self) -> dict:
        """
        GAP: Redis no expone hit/miss ratio de la misma forma que el dict en memoria.
        Se retorna info básica del servidor Redis.
        """
        client = self._get_client()
        if not client:
            return {'disponible': False}
        try:
            info = client.info('stats')
            return {
                'disponible': True,
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
            }
        except Exception as e:
            return {'disponible': False, 'error': str(e)}


# Instancia global reutilizada entre invocaciones Lambda calientes
cache_service = RedisCache()
