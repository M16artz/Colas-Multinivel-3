# -*- coding: utf-8 -*-
"""
Capa de MODELO
==============
Define la entidad Proceso y sus estados. No contiene lógica de planificación
ni de interfaz: solo la estructura de datos y utilidades básicas asociadas
a un proceso individual.
"""

from dataclasses import dataclass, field
from typing import List, Optional


class EstadoProceso:
    LISTO = "Listo"
    EJECUCION = "Ejecución"
    BLOQUEADO = "Bloqueado (E/S)"
    TERMINADO = "Terminado"


@dataclass
class Proceso:
    pid: int
    arrival_time: int              # tiempo de llegada al sistema
    nivel: int                     # 1, 2 o 3 (cola de origen, fija)
    prioridad_inicial: int         # solo relevante para nivel 1
    rafaga_total: int              # ráfaga total de CPU requerida
    puntos_io: List[int]           # tiempos ACUMULADOS de CPU en los que pide E/S
    duraciones_io: List[int]       # duración de cada E/S, mismo orden que puntos_io
    nombre: str = ""                # nombre visible del proceso (si viene vacío, se usa "Pn")

    # ---- estado interno de simulación (no se setean al crear el proceso) ----
    prioridad_actual: int = field(init=False, default=0)
    rafaga_restante: int = field(init=False, default=0)
    cpu_ejecutado_total: int = field(init=False, default=0)
    siguiente_io_idx: int = field(init=False, default=0)
    estado: str = field(init=False, default=EstadoProceso.LISTO)
    tiempo_ingreso_cola: int = field(init=False, default=0)
    ha_ejecutado_primera_vez: bool = field(init=False, default=False)
    pasos_envejecimiento_aplicados: int = field(init=False, default=0)
    quantum_usado: int = field(init=False, default=0)
    tiempo_fin_io: Optional[int] = field(init=False, default=None)
    es_llegada_nueva: bool = field(init=False, default=True)  # para desempate regla 9
    tiempo_finalizacion: Optional[int] = field(init=False, default=None)

    def __post_init__(self):
        self.prioridad_actual = self.prioridad_inicial
        self.rafaga_restante = self.rafaga_total
        self.tiempo_ingreso_cola = self.arrival_time
        if not self.nombre or not str(self.nombre).strip():
            self.nombre = f"P{self.pid}"

    def reset(self):
        """Reinicia todo el estado dinámico del proceso (para 'Reiniciar' simulación)."""
        self.prioridad_actual = self.prioridad_inicial
        self.rafaga_restante = self.rafaga_total
        self.cpu_ejecutado_total = 0
        self.siguiente_io_idx = 0
        self.estado = EstadoProceso.LISTO
        self.tiempo_ingreso_cola = self.arrival_time
        self.ha_ejecutado_primera_vez = False
        self.pasos_envejecimiento_aplicados = 0
        self.quantum_usado = 0
        self.tiempo_fin_io = None
        self.es_llegada_nueva = True
        self.tiempo_finalizacion = None

    def __repr__(self):
        return f"{self.nombre}(n{self.nivel},rest={self.rafaga_restante})"