"""
Servicio de caché en memoria.

Anti-patrón intencional: estado compartido en un diccionario en memoria.
En un monolito esto funciona porque todo corre en un proceso; al migrar
a Lambda esto se rompe (cada instancia tiene su propio espacio de memoria).

Este es uno de los desafíos clave para el Orquestador DevOps al momento
de proponer la migración a Serverless.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """
    Singleton de caché en memoria con TTL básico.
    Usado transversalmente por múltiples blueprints.
    """
    _instancia = None  # Patrón Singleton

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._cache = {}       # {clave: (valor, expira_en)}
            cls._instancia._estadisticas = {
                'hits': 0,
                'misses': 0,
                'escrituras': 0,
            }
        return cls._instancia

    def get(self, clave: str) -> Optional[Any]:
        """Obtiene un valor del caché. Retorna None si no existe o expiró."""
        entrada = self._cache.get(clave)
        if entrada is None:
            self._estadisticas['misses'] += 1
            logger.debug(f"Cache MISS: {clave}")
            return None

        valor, expira_en = entrada
        if expira_en and datetime.utcnow() > expira_en:
            del self._cache[clave]
            self._estadisticas['misses'] += 1
            logger.debug(f"Cache EXPIRED: {clave}")
            return None

        self._estadisticas['hits'] += 1
        logger.debug(f"Cache HIT: {clave}")
        return valor

    def set(self, clave: str, valor: Any, ttl_segundos: int = 300) -> None:
        """Almacena un valor en el caché con TTL en segundos."""
        expira_en = datetime.utcnow() + timedelta(seconds=ttl_segundos)
        self._cache[clave] = (valor, expira_en)
        self._estadisticas['escrituras'] += 1
        logger.debug(f"Cache SET: {clave} (TTL: {ttl_segundos}s)")

    def delete(self, clave: str) -> None:
        """Elimina una entrada del caché."""
        self._cache.pop(clave, None)

    def invalidar_patron(self, patron: str) -> int:
        """Elimina todas las claves que contienen el patrón dado."""
        claves_a_eliminar = [k for k in self._cache if patron in k]
        for clave in claves_a_eliminar:
            del self._cache[clave]
        return len(claves_a_eliminar)

    def limpiar(self) -> None:
        """Vacía todo el caché."""
        self._cache.clear()
        logger.info("Cache limpiado completamente")

    def estadisticas(self) -> dict:
        """Retorna métricas de uso del caché."""
        return {
            **self._estadisticas,
            'entradas_activas': len(self._cache),
        }


# Instancia global del singleton — importada directamente por otros módulos
# Anti-patrón: acoplamiento fuerte via importación directa
cache_service = CacheService()
