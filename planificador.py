# -*- coding: utf-8 -*-
"""
Capa de PLANIFICACIÓN (lógica de negocio)
==========================================
Implementa el motor de simulación de colas multinivel. La jerarquía de
niveles es fija (1 siempre desaloja a 2 y 3; 2 siempre desaloja a 3), pero
el ALGORITMO INTERNO de cada cola es configurable dinámicamente entre:

  - "Prioridad" : selección por menor valor de prioridad_actual, con
                  apropiación dentro del mismo nivel y envejecimiento
                  (umbral y condición configurables) mientras el proceso
                  no haya ejecutado nunca.
  - "SJF"       : selección por menor ráfaga restante, no apropiativo
                  dentro del mismo nivel.
  - "RR"        : Round Robin con quantum fijo (compartido por todas las
                  colas que usen este algoritmo). No apropiativo dentro
                  del mismo nivel (solo cede por fin de quantum).
  - "FIFO"      : estrictamente por orden de llegada a la cola, no
                  apropiativo.

El motor avanza en pasos discretos de 1 ms. No conoce nada de Tkinter ni
de dibujo: solo produce un log textual y expone el estado (colas, CPU,
bloqueados) y el histórico de tramos para que la capa de interfaz lo pinte.
"""

from typing import Dict, List, Optional
from modelo import Proceso, EstadoProceso

ALGORITMOS_VALIDOS = ("Prioridad", "SJF", "RR", "FIFO")


class MotorSimulacion:
    def __init__(self, procesos: List[Proceso], quantum: int, tt_envejecimiento: int,
                 envejecimiento_habilitado: bool = True,
                 algoritmos: Optional[Dict[int, str]] = None,
                 umbral_envejecimiento: int = 1,
                 condicion_envejecimiento: str = "mayor_igual"):
        self.quantum = quantum
        self.tt = max(1, tt_envejecimiento)
        self.envejecimiento_habilitado = envejecimiento_habilitado
        self.umbral_envejecimiento = umbral_envejecimiento
        # "mayor"       -> aplica envejecimiento solo si prioridad_actual >  umbral
        # "mayor_igual" -> aplica envejecimiento solo si prioridad_actual >= umbral
        self.condicion_envejecimiento = condicion_envejecimiento

        self.algoritmos: Dict[int, str] = {1: "Prioridad", 2: "SJF", 3: "RR"}
        if algoritmos:
            for nivel, alg in algoritmos.items():
                if alg in ALGORITMOS_VALIDOS:
                    self.algoritmos[nivel] = alg

        self.tiempo = 0
        self.procesos_todos = procesos
        self.pendientes_llegada = sorted(procesos, key=lambda p: (p.arrival_time, p.pid))
        self.listos = {1: [], 2: [], 3: []}   # type: dict[int, list[Proceso]]
        self.bloqueados: List[Proceso] = []
        self.terminados: List[Proceso] = []
        self.en_cpu: Optional[Proceso] = None
        self.log: List[str] = []
        self.finalizada = False

        # Historial por proceso: lista de tramos {tipo, inicio, fin}
        # tipo in {"Cola N1","Cola N2","Cola N3","CPU","E/S","Terminado"}
        # 'fin' es None mientras el tramo sigue abierto (en curso).
        self.historial = {p.pid: [] for p in procesos}

    # ------------------------------------------------------------------ #
    # Reconfiguración en caliente (cambios dinámicos desde la interfaz)
    # ------------------------------------------------------------------ #
    def actualizar_configuracion(self, quantum=None, tt_envejecimiento=None,
                                  envejecimiento_habilitado=None, algoritmos=None,
                                  umbral_envejecimiento=None, condicion_envejecimiento=None):
        if quantum is not None:
            self.quantum = quantum
        if tt_envejecimiento is not None:
            self.tt = max(1, tt_envejecimiento)
        if envejecimiento_habilitado is not None:
            self.envejecimiento_habilitado = envejecimiento_habilitado
        if umbral_envejecimiento is not None:
            self.umbral_envejecimiento = umbral_envejecimiento
        if condicion_envejecimiento is not None:
            self.condicion_envejecimiento = condicion_envejecimiento
        if algoritmos:
            for nivel, alg in algoritmos.items():
                if alg in ALGORITMOS_VALIDOS:
                    self.algoritmos[nivel] = alg

    # ------------------------------------------------------------------ #
    # Utilidades de registro
    # ------------------------------------------------------------------ #
    def _registrar(self, msg: str):
        self.log.append(f"[t={self.tiempo:>5} ms] {msg}")

    def _cambiar_zona(self, p: Proceso, tipo: str, t: Optional[int] = None):
        """Cierra el tramo abierto del proceso (si lo hay) e inicia uno nuevo,
        dejando constancia del tiempo exacto en que comienza cada tramo
        (cola de nivel N, CPU o E/S). Esto forma el histórico permanente."""
        if t is None:
            t = self.tiempo
        tramos = self.historial.setdefault(p.pid, [])
        if tramos and tramos[-1]["fin"] is None:
            tramos[-1]["fin"] = t
        tramos.append({"tipo": tipo, "inicio": t, "fin": None})

    # ------------------------------------------------------------------ #
    # Inserción en colas de listos
    # ------------------------------------------------------------------ #
    def _insertar_listo(self, p: Proceso, es_nueva: bool):
        p.estado = EstadoProceso.LISTO
        p.es_llegada_nueva = es_nueva
        p.quantum_usado = 0
        self.listos[p.nivel].append(p)

    # ------------------------------------------------------------------ #
    # Selección según el algoritmo configurado para ese nivel, con regla
    # de desempate 9 (llegada nueva gana el empate frente a retorno de E/S)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clave_desempate(p: Proceso):
        return 0 if p.es_llegada_nueva else 1

    def _mejor_proceso(self, nivel: int) -> Optional[Proceso]:
        cola = self.listos[nivel]
        if not cola:
            return None
        algo = self.algoritmos.get(nivel, "FIFO")
        if algo == "Prioridad":
            return min(cola, key=lambda p: (p.prioridad_actual, p.tiempo_ingreso_cola, self._clave_desempate(p)))
        if algo == "SJF":
            return min(cola, key=lambda p: (p.rafaga_restante, p.tiempo_ingreso_cola, self._clave_desempate(p)))
        # "RR" y "FIFO" seleccionan siempre la cabeza de la cola (orden de llegada/reinserción)
        return cola[0]

    # ------------------------------------------------------------------ #
    # Despacho / apropiación
    # ------------------------------------------------------------------ #
    def _iniciar_ejecucion(self, p: Proceso, nivel: int):
        self.listos[nivel].remove(p)
        p.estado = EstadoProceso.EJECUCION
        self.en_cpu = p
        if not p.ha_ejecutado_primera_vez:
            p.ha_ejecutado_primera_vez = True  # el envejecimiento cesa aquí para siempre
        if self.algoritmos.get(nivel) == "RR":
            p.quantum_usado = 0
        self._cambiar_zona(p, "CPU")
        self._registrar(f"P{p.pid} (nivel {nivel}, alg={self.algoritmos.get(nivel)}) TOMA la CPU "
                         f"(ráfaga restante={p.rafaga_restante}ms"
                         + (f", prioridad={p.prioridad_actual}" if self.algoritmos.get(nivel) == "Prioridad" else "") + ")")

    def _desalojar(self, actual: Proceso, nuevo: Proceso, nivel_nuevo: int):
        # El proceso desalojado regresa a su cola; su tiempo de ingreso NO se reinicia (regla 4)
        actual.estado = EstadoProceso.LISTO
        actual.es_llegada_nueva = False
        if self.algoritmos.get(actual.nivel) == "RR":
            # Fresca "ejecución independiente" la próxima vez (regla 8); se reinserta al frente
            # porque no agotó su quantum, solo fue apropiado por un nivel superior.
            self.listos[actual.nivel].insert(0, actual)
        else:
            self.listos[actual.nivel].append(actual)
        self._cambiar_zona(actual, f"Cola N{actual.nivel}")
        self._registrar(f"P{nuevo.pid} (nivel {nivel_nuevo}) DESALOJA a "
                         f"P{actual.pid} (nivel {actual.nivel}) de la CPU")
        self._iniciar_ejecucion(nuevo, nivel_nuevo)

    def _planificar(self):
        """Decide quién debe estar en CPU en este instante; aplica apropiación."""
        actual = self.en_cpu

        if actual is None:
            for nivel in (1, 2, 3):
                candidato = self._mejor_proceso(nivel)
                if candidato:
                    self._iniciar_ejecucion(candidato, nivel)
                    return
            return

        # Apropiación ENTRE niveles: cualquier nivel estrictamente superior (número
        # menor) al del proceso en CPU siempre lo desaloja, sin importar el
        # algoritmo interno de ese nivel (regla fija de jerarquía 1 > 2 > 3).
        for nivel in range(1, actual.nivel):
            candidato = self._mejor_proceso(nivel)
            if candidato is not None:
                self._desalojar(actual, candidato, nivel)
                return

        # Apropiación DENTRO del mismo nivel: solo ocurre si ese nivel usa el
        # algoritmo "Prioridad" (SJF/RR/FIFO no se auto-apropian; RR solo cede
        # por fin de quantum, ya gestionado en paso()).
        if self.algoritmos.get(actual.nivel) == "Prioridad":
            candidato = self._mejor_proceso(actual.nivel)
            if candidato is not None and candidato is not actual and candidato.prioridad_actual < actual.prioridad_actual:
                self._desalojar(actual, candidato, actual.nivel)

    # ------------------------------------------------------------------ #
    # Envejecimiento (umbral y condición configurables)
    # ------------------------------------------------------------------ #
    def _cumple_condicion_envejecimiento(self, prioridad_actual: int) -> bool:
        if self.condicion_envejecimiento == "mayor":
            return prioridad_actual > self.umbral_envejecimiento
        return prioridad_actual >= self.umbral_envejecimiento  # "mayor_igual"

    def _aplicar_envejecimiento(self, t: int):
        if not self.envejecimiento_habilitado:
            return
        for nivel in (1, 2, 3):
            if self.algoritmos.get(nivel) != "Prioridad":
                continue
            for p in self.listos[nivel]:
                if p.ha_ejecutado_primera_vez:
                    continue
                if not self._cumple_condicion_envejecimiento(p.prioridad_actual):
                    continue
                espera = t - p.tiempo_ingreso_cola
                pasos_esperados = espera // self.tt
                if pasos_esperados > p.pasos_envejecimiento_aplicados:
                    delta = pasos_esperados - p.pasos_envejecimiento_aplicados
                    p.prioridad_actual -= delta
                    p.pasos_envejecimiento_aplicados = pasos_esperados
                    self._registrar(f"P{p.pid} ENVEJECE -> nueva prioridad={p.prioridad_actual}")

    # ------------------------------------------------------------------ #
    # Paso principal de la simulación (1 ms)
    # ------------------------------------------------------------------ #
    def paso(self):
        t = self.tiempo

        # 1) Llegadas nuevas al sistema
        while self.pendientes_llegada and self.pendientes_llegada[0].arrival_time == t:
            p = self.pendientes_llegada.pop(0)
            p.tiempo_ingreso_cola = t
            self._insertar_listo(p, es_nueva=True)
            self._cambiar_zona(p, f"Cola N{p.nivel}")
            self._registrar(f"P{p.pid} LLEGA al sistema -> ingresa a cola Nivel {p.nivel} "
                             f"(t_ingreso={t}ms" + (f", prioridad={p.prioridad_actual}" if p.nivel == 1 else "") + ")")

        # 2) Retornos desde E/S (se procesan después de las llegadas: regla de desempate 9)
        aun_bloqueados = []
        for p in self.bloqueados:
            if p.tiempo_fin_io == t:
                p.tiempo_ingreso_cola = t
                self._insertar_listo(p, es_nueva=False)
                self._cambiar_zona(p, f"Cola N{p.nivel}")
                self._registrar(f"P{p.pid} TERMINA E/S -> reingresa a cola Nivel {p.nivel} (t_ingreso={t}ms)")
            else:
                aun_bloqueados.append(p)
        self.bloqueados = aun_bloqueados

        # 3) Envejecimiento (solo colas con algoritmo "Prioridad", solo antes de
        #    la primera ejecución, y solo si la prioridad actual cumple la
        #    condición configurada respecto al umbral)
        self._aplicar_envejecimiento(t)

        # 4) Decisión de planificación / apropiación
        self._planificar()

        # 5) Ejecutar 1 ms al proceso en CPU (si hay)
        if self.en_cpu is not None:
            p = self.en_cpu
            p.rafaga_restante -= 1
            p.cpu_ejecutado_total += 1
            if self.algoritmos.get(p.nivel) == "RR":
                p.quantum_usado += 1

            t_next = t + 1
            termino = p.rafaga_restante <= 0
            pide_io = (not termino and p.siguiente_io_idx < len(p.puntos_io)
                       and p.cpu_ejecutado_total >= p.puntos_io[p.siguiente_io_idx])
            quantum_agotado = (not termino and not pide_io and self.algoritmos.get(p.nivel) == "RR"
                               and p.quantum_usado >= self.quantum)

            if termino:
                p.estado = EstadoProceso.TERMINADO
                p.tiempo_finalizacion = t_next
                self.terminados.append(p)
                self.en_cpu = None
                self._cambiar_zona(p, "Terminado", t_next)
                self._registrar(f"P{p.pid} FINALIZA su ejecución -> Terminado (t={t_next}ms)")
            elif pide_io:
                dur = p.duraciones_io[p.siguiente_io_idx]
                p.siguiente_io_idx += 1
                p.tiempo_fin_io = t_next + dur
                p.estado = EstadoProceso.BLOQUEADO
                self.bloqueados.append(p)
                self.en_cpu = None
                self._cambiar_zona(p, "E/S", t_next)
                self._registrar(f"P{p.pid} SOLICITA E/S por {dur}ms (retorna en t={p.tiempo_fin_io}ms)")
            elif quantum_agotado:
                p.quantum_usado = 0
                p.estado = EstadoProceso.LISTO
                p.es_llegada_nueva = False
                self.listos[p.nivel].append(p)
                self.en_cpu = None
                self._cambiar_zona(p, f"Cola N{p.nivel}", t_next)
                self._registrar(f"P{p.pid} AGOTA su quantum -> regresa al final de la cola Nivel {p.nivel}")

        self.tiempo += 1

        self.finalizada = (
            not self.pendientes_llegada and not self.bloqueados and self.en_cpu is None
            and all(len(q) == 0 for q in self.listos.values())
        )

    # ------------------------------------------------------------------ #
    # Utilidad: correr hasta el final (modo "sin interfaz", para pruebas)
    # ------------------------------------------------------------------ #
    def correr_hasta_el_final(self, limite_ms: int = 100000):
        while not self.finalizada and self.tiempo < limite_ms:
            self.paso()
        return self.log
