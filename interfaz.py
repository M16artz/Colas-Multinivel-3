# -*- coding: utf-8 -*-
"""
Capa de INTERFAZ / VISUALIZACIÓN
=================================
Construida con Tkinter. Contiene:

  - Tabla editable de procesos (Treeview + diálogos de alta/edición).
  - Panel de configuración global (quantum, tt/umbral/condición de
    envejecimiento, algoritmo por cola, on/off) con aplicación en vivo.
  - Controles de simulación (iniciar / pausar-reanudar / reiniciar).
  - Diagrama de Gantt "por zona" (no por proceso): una única fila
    horizontal para la CPU y una única fila horizontal por cada cola de
    listos (Nivel 1/2/3) y para E/S. Cada franja se etiqueta con el PID
    del proceso y se colorea de forma consistente por proceso. Cuando un
    proceso sale de una cola (según las reglas del algoritmo vigente en
    ella) su franja se marca con un tachado en el instante exacto de
    salida. Si en un mismo instante hay varios procesos esperando en la
    misma cola, se apilan en "carriles" dentro de esa misma fila en vez
    de crear filas nuevas.
  - La geometría vertical del diagrama es FIJA desde el arranque (no
    depende del tiempo transcurrido ni del scroll), lo que evita el error
    de que las etiquetas se desplacen y queden tapando el dibujo.
  - Botón "Ver histórico" con el detalle textual de cada tramo.
  - Panel de log cronológico en tiempo real.

Esta capa NO contiene lógica de planificación: solo llama a
`planificador.MotorSimulacion` y dibuja el estado/histórico que este expone.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from modelo import Proceso, EstadoProceso
from planificador import MotorSimulacion, ALGORITMOS_VALIDOS


# ---------------------------------------------------------------------- #
# Utilidades de parseo
# ---------------------------------------------------------------------- #
def parsear_lista_enteros(texto: str):
    texto = (texto or "").strip()
    if texto == "":
        return []
    sep = "-" if "-" in texto else ","
    return [int(x.strip()) for x in texto.split(sep) if x.strip() != ""]


# Paleta de colores estable por PID (independiente de la zona/cola).
PALETA_PID = [
    "#e74c3c", "#3498db", "#27ae60", "#f39c12", "#9b59b6",
    "#16a085", "#e67e22", "#2c3e50", "#c0392b", "#2980b9",
    "#8e44ad", "#d35400", "#1abc9c", "#7f8c8d", "#f1c40f",
]


def color_de_pid(pid: int) -> str:
    return PALETA_PID[(pid - 1) % len(PALETA_PID)]


# Filas fijas del diagrama y cuántos "carriles" (procesos concurrentes)
# soporta cada una antes de empezar a superponer (caso muy poco común).
FILAS = ["CPU", "Cola N1", "Cola N2", "Cola N3", "E/S"]
CARRILES_POR_FILA = {"CPU": 1, "Cola N1": 3, "Cola N2": 3, "Cola N3": 3, "E/S": 2}
NOMBRE_FILA = {
    "CPU": "CPU",
    "Cola N1": "Listos N1",
    "Cola N2": "Listos N2",
    "Cola N3": "Listos N3",
    "E/S": "E / S",
}


class DialogoProceso(tk.Toplevel):
    """Diálogo modal para agregar/editar una fila de la tabla de procesos."""

    def __init__(self, master, valores_iniciales=None):
        super().__init__(master)
        self.title("Proceso")
        self.resizable(False, False)
        self.resultado = None
        self.grab_set()

        etiquetas = ["Nombre del proceso", "Tiempo de llegada", "Ráfaga CPU total", "Puntos E/S (ej. 2-5-6)",
                     "Duraciones E/S (ej. 3-2)", "Nivel de cola (1/2/3)", "Prioridad inicial"]
        claves = ["nombre", "llegada", "rafaga", "puntos_io", "duraciones_io", "nivel", "prioridad"]
        self.vars = {}

        valores_iniciales = valores_iniciales or {
            "nombre": "", "llegada": "0", "rafaga": "5", "puntos_io": "", "duraciones_io": "",
            "nivel": "1", "prioridad": "1",
        }

        for i, (etq, clave) in enumerate(zip(etiquetas, claves)):
            tk.Label(self, text=etq).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            var = tk.StringVar(value=str(valores_iniciales.get(clave, "")))
            self.vars[clave] = var
            if clave == "nivel":
                combo = ttk.Combobox(self, textvariable=var, values=["1", "2", "3"], width=17, state="readonly")
                combo.grid(row=i, column=1, padx=8, pady=4)
            else:
                tk.Entry(self, textvariable=var, width=20).grid(row=i, column=1, padx=8, pady=4)

        tk.Label(self, text="(si se deja vacío, se usa \"Pn\" según el PID asignado)",
                 font=("Arial", 7), fg="#666").grid(row=0, column=2, sticky="w", padx=(4, 8))

        botones = tk.Frame(self)
        botones.grid(row=len(etiquetas), column=0, columnspan=2, pady=10)
        tk.Button(botones, text="Guardar", command=self._guardar, width=12).pack(side="left", padx=5)
        tk.Button(botones, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=5)

    def _guardar(self):
        try:
            llegada = int(self.vars["llegada"].get())
            rafaga = int(self.vars["rafaga"].get())
            nivel = int(self.vars["nivel"].get())
            prioridad = int(self.vars["prioridad"].get() or 0)
            puntos_io = parsear_lista_enteros(self.vars["puntos_io"].get())
            duraciones_io = parsear_lista_enteros(self.vars["duraciones_io"].get())
            if nivel not in (1, 2, 3):
                raise ValueError("El nivel debe ser 1, 2 o 3")
            if len(puntos_io) != len(duraciones_io):
                raise ValueError("Puntos de E/S y duraciones de E/S deben tener la misma cantidad de elementos")
            if rafaga <= 0:
                raise ValueError("La ráfaga total debe ser mayor que 0")
            if puntos_io != sorted(puntos_io):
                raise ValueError("Los puntos de E/S deben ser crecientes (acumulados)")
            if puntos_io and puntos_io[-1] > rafaga:
                raise ValueError("Los puntos de E/S no pueden superar la ráfaga total")
        except ValueError as e:
            messagebox.showerror("Datos inválidos", str(e))
            return

        self.resultado = {
            "nombre": self.vars["nombre"].get().strip(),
            "llegada": llegada, "rafaga": rafaga, "nivel": nivel, "prioridad": prioridad,
            "puntos_io": self.vars["puntos_io"].get().strip(),
            "duraciones_io": self.vars["duraciones_io"].get().strip(),
        }
        self.destroy()


class AplicacionSimulador:
    LANE_H = 42
    GAP_FILA = 4
    RULER_H = 28
    TOP_PAD = 6
    ANCHO_ETIQUETAS = 96

    ZOOM_MIN = 10
    ZOOM_MAX = 120
    ZOOM_PASO = 5
    ZOOM_DEFECTO = 30

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Simulador de Gestión de Procesos - Colas Multinivel")
        self.root.geometry("1420x860")

        self.motor: MotorSimulacion | None = None
        self.reproduciendo = False
        self.pid_autoincrement = 1
        self.definiciones = []          # filas de la tabla (dicts)
        self.log_mostrado = 0           # cuántas líneas del log ya se imprimieron
        self.CELDA_PX = 40

        # Geometría vertical FIJA (no depende del tiempo ni del scroll horizontal).
        self.fila_geo = {}
        y = self.RULER_H + self.TOP_PAD
        for fila in FILAS:
            carriles = CARRILES_POR_FILA[fila]
            alto = carriles * self.LANE_H
            self.fila_geo[fila] = {"y0": y, "carriles": carriles, "alto": alto}
            y += alto + self.GAP_FILA
        self.alto_total_fijo = y + 6

        self._construir_layout()
        self._cargar_ejemplo_por_defecto()
        self._dibujar_etiquetas_filas()   # estático: se dibuja una sola vez
        ZOOM_DEFECTO = 40

    # ------------------------------------------------------------------ #
    # Construcción de la interfaz
    # ------------------------------------------------------------------ #
    def _construir_layout(self):
        raiz = self.root

        panel_izq = tk.Frame(raiz)
        panel_izq.pack(side="left", fill="y", padx=6, pady=6)

        panel_der = tk.Frame(raiz)
        panel_der.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        # ---------------- Panel izquierdo: tabla + configuración -------- #
        tk.Label(panel_izq, text="Procesos", font=("Arial", 12, "bold")).pack(anchor="w")

        columnas = ("nombre", "llegada", "rafaga", "puntos_io", "duraciones_io", "nivel", "prioridad")
        self.tabla = ttk.Treeview(panel_izq, columns=columnas, show="headings", height=8)
        titulos = {"nombre": "Nombre", "llegada": "Llegada", "rafaga": "Ráfaga", "puntos_io": "Pts E/S",
                   "duraciones_io": "Dur E/S", "nivel": "Nivel", "prioridad": "Prior."}
        anchos = {"nombre": 70}
        for c in columnas:
            self.tabla.heading(c, text=titulos[c])
            self.tabla.column(c, width=anchos.get(c, 56), anchor="center")
        self.tabla.pack(fill="x")

        fila_botones = tk.Frame(panel_izq)
        fila_botones.pack(fill="x", pady=4)
        tk.Button(fila_botones, text="Agregar", command=self._agregar_proceso).pack(side="left", padx=2)
        tk.Button(fila_botones, text="Editar", command=self._editar_proceso).pack(side="left", padx=2)
        tk.Button(fila_botones, text="Eliminar", command=self._eliminar_proceso).pack(side="left", padx=2)

        ttk.Separator(panel_izq, orient="horizontal").pack(fill="x", pady=8)

        tk.Label(panel_izq, text="Configuración global", font=("Arial", 12, "bold")).pack(anchor="w")

        marco_cfg = tk.Frame(panel_izq)
        marco_cfg.pack(fill="x", pady=4)

        tk.Label(marco_cfg, text="Quantum Round Robin (ms):").grid(row=0, column=0, sticky="w")
        self.var_quantum = tk.StringVar(value="4")
        tk.Entry(marco_cfg, textvariable=self.var_quantum, width=8).grid(row=0, column=1, padx=4)

        tk.Label(marco_cfg, text="Envejecer cada tt (ms):").grid(row=1, column=0, sticky="w")
        self.var_tt = tk.StringVar(value="5")
        tk.Entry(marco_cfg, textvariable=self.var_tt, width=8).grid(row=1, column=1, padx=4)

        self.var_envejecimiento = tk.BooleanVar(value=True)
        tk.Checkbutton(marco_cfg, text="Habilitar envejecimiento", variable=self.var_envejecimiento
                        ).grid(row=2, column=0, columnspan=2, sticky="w")

        # --- Umbral y condición de envejecimiento (configurable manualmente) ---
        tk.Label(marco_cfg, text="Envejecer solo si prioridad:").grid(row=3, column=0, sticky="w", pady=(6, 0))
        marco_umbral = tk.Frame(marco_cfg)
        marco_umbral.grid(row=4, column=0, columnspan=2, sticky="w")
        self.var_cond_env = tk.StringVar(value="mayor_igual")
        self.combo_cond_env = ttk.Combobox(marco_umbral, textvariable=self.var_cond_env, state="readonly",
                                            width=9, values=["mayor_igual", "mayor"])
        self.combo_cond_env.grid(row=0, column=0, padx=(0, 4))
        self._map_cond_texto = {"mayor_igual": ">= umbral", "mayor": "> umbral"}
        self.combo_cond_env.configure(values=["mayor_igual", "mayor"])
        tk.Label(marco_umbral, text="que:").grid(row=0, column=1)
        self.var_umbral_env = tk.StringVar(value="1")
        tk.Entry(marco_umbral, textvariable=self.var_umbral_env, width=5).grid(row=0, column=2, padx=4)

        ttk.Separator(panel_izq, orient="horizontal").pack(fill="x", pady=8)

        # --- Selector de algoritmo de planificación por cola/nivel --- #
        tk.Label(panel_izq, text="Algoritmo por cola", font=("Arial", 12, "bold")).pack(anchor="w")
        marco_alg = tk.Frame(panel_izq)
        marco_alg.pack(fill="x", pady=4)
        self.vars_algoritmo = {}
        defaults_alg = {1: "Prioridad", 2: "SJF", 3: "RR"}

        # Filtramos la tupla para excluir "FIFO"
        opciones_combobox = [alg for alg in ALGORITMOS_VALIDOS if alg != "FIFO"]

        for i, nivel in enumerate((1, 2, 3)):
            tk.Label(marco_alg, text=f"Nivel {nivel}:").grid(row=i, column=0, sticky="w")
            var = tk.StringVar(value=defaults_alg[nivel])
            self.vars_algoritmo[nivel] = var
            
            # Asignamos la lista filtrada a 'values'
            combo = ttk.Combobox(marco_alg, textvariable=var, state="readonly", width=11,
                                values=opciones_combobox)
            combo.grid(row=i, column=1, padx=4, pady=2)
            combo.bind("<<ComboboxSelected>>", self._aplicar_config_en_vivo)
        tk.Label(panel_izq, text="(el cambio de algoritmo se aplica al instante,\naun con la simulación corriendo)",
                 font=("Arial", 7), fg="#555", justify="left").pack(anchor="w")

        ttk.Separator(panel_izq, orient="horizontal").pack(fill="x", pady=8)

        tk.Label(panel_izq, text="Controles de simulación", font=("Arial", 12, "bold")).pack(anchor="w")

        marco_ctrl = tk.Frame(panel_izq)
        marco_ctrl.pack(fill="x", pady=4)
        self.btn_iniciar = tk.Button(marco_ctrl, text="▶ Iniciar", width=10, command=self._iniciar)
        self.btn_iniciar.grid(row=0, column=0, padx=2, pady=2)
        self.btn_pausar = tk.Button(marco_ctrl, text="⏸ Pausar", width=10, command=self._pausar_reanudar,
                                     state="disabled")
        self.btn_pausar.grid(row=0, column=1, padx=2, pady=2)
        self.btn_reiniciar = tk.Button(marco_ctrl, text="⟲ Reiniciar", width=10, command=self._reiniciar)
        self.btn_reiniciar.grid(row=1, column=0, columnspan=2, pady=2)
        self.btn_historial = tk.Button(marco_ctrl, text="📜 Ver histórico", width=22,
                                        command=self._ver_historial)
        self.btn_historial.grid(row=2, column=0, columnspan=2, pady=(6, 2))

        tk.Label(panel_izq, text="Segundos reales por paso (1 ms simulado):").pack(anchor="w", pady=(8, 0))
        self.var_segundos_paso = tk.DoubleVar(value=0.30)
        tk.Scale(panel_izq, from_=0.05, to=2.0, resolution=0.05, orient="horizontal",
                 variable=self.var_segundos_paso, length=220).pack(anchor="w")
        tk.Label(panel_izq, text="(más alto = simulación más lenta y fácil de seguir)",
                 font=("Arial", 8), fg="#555").pack(anchor="w")

        self.lbl_reloj = tk.Label(panel_izq, text="t = 0 ms", font=("Consolas", 16, "bold"), fg="#1a1a1a")
        self.lbl_reloj.pack(anchor="w", pady=10)

        ttk.Separator(panel_izq, orient="horizontal").pack(fill="x", pady=4)

        # --- Zoom del diagrama en vivo --- #
        tk.Label(panel_izq, text="Zoom del diagrama:", font=("Arial", 10, "bold")).pack(anchor="w")
        marco_zoom = tk.Frame(panel_izq)
        marco_zoom.pack(anchor="w", pady=(2, 4))
        tk.Button(marco_zoom, text="－ Zoom", width=8, command=self._zoom_out).grid(row=0, column=0, padx=2)
        self.lbl_zoom = tk.Label(marco_zoom, text=f"{self.CELDA_PX} px/ms", width=10, anchor="center")
        self.lbl_zoom.grid(row=0, column=1)
        tk.Button(marco_zoom, text="＋ Zoom", width=8, command=self._zoom_in).grid(row=0, column=2, padx=2)
        tk.Button(panel_izq, text="Restablecer zoom", command=self._zoom_reset).pack(anchor="w", pady=(0, 4))

        # --- Seguimiento automático del scroll --- #
        self.var_seguir = tk.BooleanVar(value=True)
        tk.Checkbutton(panel_izq, text="Seguir el instante actual (auto-scroll)",
                        variable=self.var_seguir).pack(anchor="w")
        tk.Button(panel_izq, text="⏩ Ir al instante actual",
                  command=self._ir_al_instante_actual).pack(anchor="w", pady=(2, 0))
        tk.Label(panel_izq, text="(si desplazas el diagrama manualmente, el auto-scroll\n"
                                  "se desactiva solo; usa el botón o la casilla para volver)",
                 font=("Arial", 7), fg="#555", justify="left").pack(anchor="w", pady=(2, 0))

        ttk.Separator(panel_izq, orient="horizontal").pack(fill="x", pady=4)

        # Leyenda: filas del diagrama y significado del tachado
        tk.Label(panel_izq, text="Leyenda del diagrama:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(panel_izq, text="• Cada fila = una zona (CPU / cola / E-S).\n"
                                  "• Cada bloque de color = un proceso distinto\n"
                                  "  (mismo color siempre = mismo PID).\n"
                                  "• Rayado diagonal en CPU = ráfaga consumida.\n"
                                  "• Marca 'X' roja = instante exacto en que el\n"
                                  "  proceso sale de esa cola.",
                 font=("Arial", 8), justify="left", fg="#333").pack(anchor="w")
        self.marco_leyenda_pids = tk.Frame(panel_izq)
        self.marco_leyenda_pids.pack(anchor="w", pady=(4, 0), fill="x")

        # ---------------- Panel derecho: Gantt + log -------------------- #
        tk.Label(panel_der, text="Diagrama en vivo (una fila por zona; se rellena con el tiempo)",
                 font=("Arial", 11, "bold")).pack(anchor="w")
        marco_gantt = tk.Frame(panel_der)
        marco_gantt.pack(fill="both", expand=True)

        alto_canvas = self.alto_total_fijo + 10

        # Canvas IZQUIERDO fijo (nombres de fila): nunca se desplaza horizontalmente,
        # así los nombres nunca terminan tapando el dibujo del lado derecho.
        self.canvas_etiquetas = tk.Canvas(marco_gantt, width=self.ANCHO_ETIQUETAS, height=alto_canvas,
                                           bg="#f2f2f2", highlightthickness=1, highlightbackground="#bbbbbb")
        self.canvas_etiquetas.pack(side="left", fill="y")

        marco_contenido = tk.Frame(marco_gantt)
        marco_contenido.pack(side="left", fill="both", expand=True)

        self.canvas_gantt = tk.Canvas(marco_contenido, bg="#ffffff", height=alto_canvas,
                                       highlightthickness=1, highlightbackground="#bbbbbb")

        def _scroll_manual(*args):
            # Cualquier interacción manual con el scrollbar desactiva el auto-scroll,
            # así el usuario puede navegar libremente por el histórico sin que la
            # vista "salte" de vuelta al instante actual en el siguiente paso.
            self.var_seguir.set(False)
            self.canvas_gantt.xview(*args)

        barra_h = tk.Scrollbar(marco_contenido, orient="horizontal", command=_scroll_manual)
        self.canvas_gantt.configure(xscrollcommand=barra_h.set, scrollregion=(0, 0, 1000, alto_canvas))
        self.canvas_gantt.pack(side="top", fill="both", expand=True)
        self.canvas_gantt.update_idletasks()
        barra_h.pack(side="top", fill="x")

        def _rueda_manual(_evento):
            self.var_seguir.set(False)
            direccion = -1 if _evento.delta > 0 else 1
            self.canvas_gantt.xview_scroll(direccion * 3, "units")

        def _rueda_manual_linux(direccion):
            def _cb(_evento):
                self.var_seguir.set(False)
                self.canvas_gantt.xview_scroll(direccion * 3, "units")
            return _cb

        self.canvas_gantt.bind("<MouseWheel>", _rueda_manual)               # Windows / macOS
        self.canvas_gantt.bind("<Shift-MouseWheel>", _rueda_manual)
        self.canvas_gantt.bind("<Button-4>", _rueda_manual_linux(-1))       # Linux (scroll arriba)
        self.canvas_gantt.bind("<Button-5>", _rueda_manual_linux(1))        # Linux (scroll abajo)

        tk.Label(panel_der, text="Registro de eventos", font=("Arial", 11, "bold")).pack(anchor="w", pady=(6, 0))
        marco_log = tk.Frame(panel_der)
        marco_log.pack(fill="both", expand=False)
        self.txt_log = tk.Text(marco_log, height=11, font=("Menlo", 9), bg="#111", fg="#0f0")
        barra = tk.Scrollbar(marco_log, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=barra.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

    def _cargar_ejemplo_por_defecto(self):
        ejemplo = [
            {"nombre": "", "llegada": 0, "rafaga": 8, "nivel": 1, "prioridad": 3, "puntos_io": "3", "duraciones_io": "3"},
            {"nombre": "", "llegada": 2, "rafaga": 5, "nivel": 1, "prioridad": 1, "puntos_io": "", "duraciones_io": ""},
            {"nombre": "", "llegada": 0, "rafaga": 6, "nivel": 2, "prioridad": 0, "puntos_io": "2", "duraciones_io": "4"},
            {"nombre": "", "llegada": 0, "rafaga": 9, "nivel": 3, "prioridad": 0, "puntos_io": "4", "duraciones_io": "3"},
            {"nombre": "", "llegada": 5, "rafaga": 5, "nivel": 3, "prioridad": 0, "puntos_io": "", "duraciones_io": ""},
        ]
        for d in ejemplo:
            self._insertar_definicion(d)

    # ------------------------------------------------------------------ #
    # Manejo de la tabla de procesos
    # ------------------------------------------------------------------ #
    def _insertar_definicion(self, d):
        d = dict(d)
        d["pid"] = self.pid_autoincrement
        self.pid_autoincrement += 1
        if not str(d.get("nombre", "")).strip():
            d["nombre"] = f"P{d['pid']}"
        self.definiciones.append(d)
        self.tabla.insert("", "end", iid=str(d["pid"]),
                           values=(d["nombre"], d["llegada"], d["rafaga"], d["puntos_io"], d["duraciones_io"],
                                   d["nivel"], d["prioridad"]))

    def _agregar_proceso(self):
        dlg = DialogoProceso(self.root)
        self.root.wait_window(dlg)
        if dlg.resultado:
            self._insertar_definicion(dlg.resultado)

    def _editar_proceso(self):
        sel = self.tabla.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecciona una fila de la tabla primero.")
            return
        pid = int(sel[0])
        d = next(x for x in self.definiciones if x["pid"] == pid)
        dlg = DialogoProceso(self.root, valores_iniciales=d)
        self.root.wait_window(dlg)
        if dlg.resultado:
            nuevo = dict(dlg.resultado)
            nuevo["pid"] = pid
            if not str(nuevo.get("nombre", "")).strip():
                nuevo["nombre"] = f"P{pid}"
            idx = self.definiciones.index(d)
            self.definiciones[idx] = nuevo
            self.tabla.item(str(pid), values=(nuevo["nombre"], nuevo["llegada"], nuevo["rafaga"],
                                               nuevo["puntos_io"], nuevo["duraciones_io"],
                                               nuevo["nivel"], nuevo["prioridad"]))

    def _eliminar_proceso(self):
        sel = self.tabla.selection()
        if not sel:
            messagebox.showinfo("Eliminar", "Selecciona una fila de la tabla primero.")
            return
        pid = int(sel[0])
        self.definiciones = [x for x in self.definiciones if x["pid"] != pid]
        self.tabla.delete(sel[0])

    # ------------------------------------------------------------------ #
    # Control de simulación
    # ------------------------------------------------------------------ #
    def _construir_procesos_desde_tabla(self):
        procesos = []
        for d in self.definiciones:
            p = Proceso(
                pid=d["pid"], arrival_time=int(d["llegada"]), nivel=int(d["nivel"]),
                prioridad_inicial=int(d["prioridad"]), rafaga_total=int(d["rafaga"]),
                puntos_io=parsear_lista_enteros(d["puntos_io"]),
                duraciones_io=parsear_lista_enteros(d["duraciones_io"]),
                nombre=str(d.get("nombre", "")).strip(),
            )
            procesos.append(p)
        return procesos

    def _leer_config_formulario(self):
        """Lee y valida los campos de configuración. Devuelve un dict o None si hay error."""
        try:
            quantum = int(self.var_quantum.get())
            tt = int(self.var_tt.get())
            umbral = int(self.var_umbral_env.get())
            if quantum <= 0 or tt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Configuración inválida",
                                  "Quantum, tt y umbral de envejecimiento deben ser enteros "
                                  "(quantum y tt además positivos).")
            return None
        algoritmos = {nivel: var.get() for nivel, var in self.vars_algoritmo.items()}
        return {
            "quantum": quantum,
            "tt": tt,
            "umbral": umbral,
            "condicion": self.var_cond_env.get(),
            "envejecimiento": self.var_envejecimiento.get(),
            "algoritmos": algoritmos,
        }

    def _iniciar(self):
        if not self.definiciones:
            messagebox.showwarning("Sin procesos", "Agrega al menos un proceso a la tabla.")
            return
        cfg = self._leer_config_formulario()
        if cfg is None:
            return

        procesos = self._construir_procesos_desde_tabla()
        self.motor = MotorSimulacion(
            procesos, quantum=cfg["quantum"], tt_envejecimiento=cfg["tt"],
            envejecimiento_habilitado=cfg["envejecimiento"], algoritmos=cfg["algoritmos"],
            umbral_envejecimiento=cfg["umbral"], condicion_envejecimiento=cfg["condicion"],
        )
        self.log_mostrado = 0
        self.txt_log.delete("1.0", "end")
        self.canvas_gantt.delete("barra")
        self.reproduciendo = True
        self.var_seguir.set(True)
        self.btn_pausar.config(state="normal", text="⏸ Pausar")
        self.btn_iniciar.config(state="disabled")
        self._actualizar_leyenda_pids()
        self._loop()

    def _pausar_reanudar(self):
        if not self.motor:
            return
        self.reproduciendo = not self.reproduciendo
        self.btn_pausar.config(text="⏸ Pausar" if self.reproduciendo else "▶ Reanudar")

    def _reiniciar(self):
        self.motor = None
        self.reproduciendo = False
        self.var_seguir.set(True)
        self.log_mostrado = 0
        self.CELDA_PX = self.ZOOM_DEFECTO
        self.txt_log.delete("1.0", "end")
        self.canvas_gantt.delete("barra")
        self.lbl_reloj.config(text="t = 0 ms")
        self.btn_pausar.config(state="disabled", text="⏸ Pausar")
        self.btn_iniciar.config(state="normal")

    def _aplicar_config_en_vivo(self, _evento=None):
        """Aplica quantum / envejecimiento / algoritmo por cola AL INSTANTE si
        hay una simulación en curso (permite cambiar de algoritmo en caliente,
        según lo pedido: 'de forma dinámica')."""
        cfg = self._leer_config_formulario()
        if cfg is None:
            return
        if self.motor is not None:
            self.motor.actualizar_configuracion(
                quantum=cfg["quantum"], tt_envejecimiento=cfg["tt"],
                envejecimiento_habilitado=cfg["envejecimiento"],
                algoritmos=cfg["algoritmos"], umbral_envejecimiento=cfg["umbral"],
                condicion_envejecimiento=cfg["condicion"],
            )

    # ------------------------------------------------------------------ #
    # Zoom del diagrama (mantiene visible, al cambiar de escala, el mismo
    # instante que estaba en el borde izquierdo de la ventana visible).
    # ------------------------------------------------------------------ #
    def _instante_en_borde_izquierdo(self):
        if self.CELDA_PX <= 0:
            return 0.0
        return self.canvas_gantt.canvasx(0) / self.CELDA_PX

    def _restaurar_borde_izquierdo(self, t_borde):
        if self.motor is None:
            return
        ancho_total = max(self.motor.tiempo * self.CELDA_PX + 300, 900)
        x_objetivo = t_borde * self.CELDA_PX
        fraccion = max(0.0, min(1.0, x_objetivo / ancho_total))
        self.canvas_gantt.xview_moveto(fraccion)

    def _cambiar_zoom(self, nuevo_valor):
        nuevo_valor = max(self.ZOOM_MIN, min(self.ZOOM_MAX, nuevo_valor))
        if nuevo_valor == self.CELDA_PX:
            return
        t_borde = self._instante_en_borde_izquierdo() if self.motor is not None else None
        self.CELDA_PX = nuevo_valor
        self.lbl_zoom.config(text=f"{self.CELDA_PX} px/ms")
        if self.motor is not None:
            self._redibujar_gantt()
            if not (self.reproduciendo and self.var_seguir.get()):
                self._restaurar_borde_izquierdo(t_borde)

    def _zoom_in(self):
        self._cambiar_zoom(self.CELDA_PX + self.ZOOM_PASO)

    def _zoom_out(self):
        self._cambiar_zoom(self.CELDA_PX - self.ZOOM_PASO)

    def _zoom_reset(self):
        self._cambiar_zoom(self.ZOOM_DEFECTO)

    def _ir_al_instante_actual(self):
        """Reactiva el auto-scroll y salta de inmediato al instante actual,
        sin esperar al siguiente paso de la simulación."""
        self.var_seguir.set(True)
        if self.motor is not None:
            self.canvas_gantt.xview_moveto(1.0)

    # ------------------------------------------------------------------ #
    # Bucle principal: 1 paso (1 ms simulado) por llamada, con espera
    # real en SEGUNDOS controlada por el usuario.
    # ------------------------------------------------------------------ #
    def _loop(self):
        if self.motor is None:
            return

        if self.reproduciendo and not self.motor.finalizada:
            self.motor.paso()
            self._actualizar_log()
            self.lbl_reloj.config(text=f"t = {self.motor.tiempo} ms")
            self._redibujar_gantt()

            if self.motor.finalizada:
                self.btn_pausar.config(state="disabled")
                self.txt_log.insert("end", "==== SIMULACIÓN FINALIZADA: todos los procesos terminaron ====\n")
                self.txt_log.see("end")
                return

            espera_ms = max(10, int(float(self.var_segundos_paso.get()) * 1000))
            self.root.after(espera_ms, self._loop)
        else:
            # En pausa (o antes de iniciar de nuevo): seguimos refrescando el
            # dibujo por si el usuario reanuda, revisando cada 150 ms reales.
            self._redibujar_gantt()
            if self.motor.finalizada:
                return
            self.root.after(150, self._loop)

    def _actualizar_log(self):
        nuevas = self.motor.log[self.log_mostrado:]
        for linea in nuevas:
            self.txt_log.insert("end", linea + "\n")
        self.log_mostrado = len(self.motor.log)
        if nuevas:
            self.txt_log.see("end")

    def _actualizar_leyenda_pids(self):
        for w in self.marco_leyenda_pids.winfo_children():
            w.destroy()
        if self.motor is None:
            return
        tk.Label(self.marco_leyenda_pids, text="Color por proceso:", font=("Arial", 8, "bold")).pack(anchor="w")
        for p in self.motor.procesos_todos:
            fila = tk.Frame(self.marco_leyenda_pids)
            fila.pack(anchor="w")
            tk.Canvas(fila, width=14, height=10, bg=color_de_pid(p.pid), highlightthickness=1,
                      highlightbackground="#333333").pack(side="left", padx=3, pady=1)
            tk.Label(fila, text=f"P{p.pid}", font=("Arial", 8)).pack(side="left")

    # ------------------------------------------------------------------ #
    # Etiquetas de fila (estáticas: se dibujan UNA sola vez, geometría fija)
    # ------------------------------------------------------------------ #
    def _dibujar_etiquetas_filas(self):
        c = self.canvas_etiquetas
        c.delete("all")
        ancho = self.ANCHO_ETIQUETAS
        c.create_text(ancho / 2, self.RULER_H / 2, text="t (ms)", font=("Arial", 8, "italic"),
                      fill="#777777")
        for fila in FILAS:
            geo = self.fila_geo[fila]
            y0, y1 = geo["y0"], geo["y0"] + geo["alto"]
            c.create_rectangle(0, y0, ancho, y1, fill="#e9e9e9", outline="#bbbbbb")
            c.create_text(ancho / 2, (y0 + y1) / 2, text=NOMBRE_FILA[fila],
                          font=("Arial", 9, "bold"), fill="#222222", width=ancho - 6)

    # ------------------------------------------------------------------ #
    # Diagrama de Gantt en vivo (una fila fija por zona, carriles internos)
    # ------------------------------------------------------------------ #
    def _redibujar_gantt(self):
        c = self.canvas_gantt
        if self.motor is None:
            return
        c.delete("barra")

        cell = self.CELDA_PX
        procesos = self.motor.procesos_todos
        t_actual = self.motor.tiempo

        ancho_total = max(t_actual * cell + 300, 900)
        alto_total = self.alto_total_fijo
        c.configure(scrollregion=(0, 0, ancho_total, alto_total))

        # --- Regla de tiempo (líneas guía + números cada 5 ms) --- #
        paso_regla = 1
        marca = 0
        while marca * cell <= ancho_total:
            x = marca * cell
            c.create_line(x, self.RULER_H, x, alto_total, fill="#f0f0f0", tags="barra")
            c.create_text(
                    x + cell/2,
                    12,
                    text=str(marca),
                    anchor="center",
                    font=("Arial", 8, "bold"),
                    fill="#666666",
                    tags="barra"
)
            marca += paso_regla

        # --- Separadores horizontales entre filas --- #
        for fila in FILAS:
            geo = self.fila_geo[fila]
            c.create_line(0, geo["y0"] - self.GAP_FILA / 2, ancho_total, geo["y0"] - self.GAP_FILA / 2,
                          fill="#dddddd", tags="barra")

        # --- Bloques por fila, con empaquetado en carriles --- #
        for fila in FILAS:
            geo = self.fila_geo[fila]
            tramos_fila = []
            for p in procesos:
                for tr in self.motor.historial.get(p.pid, []):
                    if tr["tipo"] != fila:
                        continue
                    ini = tr["inicio"]
                    cerrado = tr["fin"] is not None
                    fin = tr["fin"] if cerrado else t_actual
                    if fin <= ini:
                        fin = ini + 0.5
                    tramos_fila.append((ini, fin, p, cerrado))
            tramos_fila.sort(key=lambda x: x[0])

            n_carriles = geo["carriles"]
            fin_carril = [-1] * n_carriles
            for ini, fin, p, cerrado in tramos_fila:
                carril = None
                for i in range(n_carriles):
                    if fin_carril[i] <= ini:
                        carril = i
                        break
                if carril is None:
                    carril = n_carriles - 1  # caso extremo: más concurrencia que carriles reservados
                fin_carril[carril] = fin

                y0 = geo["y0"] + carril * self.LANE_H
                y1 = y0 + self.LANE_H - 4
                x0, x1 = ini * cell, fin * cell
                color = color_de_pid(p.pid)
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline="#222222", width=1, tags="barra")

                if x1 - x0 > 16:
                    c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=f"P{p.pid}",
                                  font=("Arial", 7, "bold"), fill="#ffffff", tags="barra")

                if fila == "CPU":
                    # Rayado diagonal = ráfaga de CPU efectivamente consumida (igual que antes).
                    xx = x0
                    while xx < x1:
                        c.create_line(xx, y1, xx + (y1 - y0), y0, fill="#000000", width=1, tags="barra")
                        xx += 5
                elif cerrado:
                    pass

                                        # =====================================================
        # CURSOR DEL TIEMPO
        # =====================================================

        xt = (t_actual + 0.5) * cell

        c.create_line(
            xt,
            self.RULER_H + 26,
            xt,
            alto_total,
            fill="#ff3b30",
            width=3,
            tags="barra"
        )

        ANCHO = cell

        c.create_rectangle(
            xt - ANCHO / 2,
            2,
            xt + ANCHO / 2,
            26,
            fill="#f44336",
            outline="#f44336",
            tags="barra"
        )

        c.create_text(
            xt,
            14,
            text=f"t={t_actual}",
            fill="white",
            font=("Arial", 8, "bold"),
            anchor="center",
            tags="barra"
        )

    # ------------------------------------------------------------------ #
    # Ventana de histórico detallado (tiempos iniciales de cada tramo)
    # ------------------------------------------------------------------ #
    def _ver_historial(self):
        if self.motor is None:
            messagebox.showinfo("Histórico", "Primero inicia una simulación.")
            return

        top = tk.Toplevel(self.root)
        top.title("Histórico detallado por proceso")
        top.geometry("680x520")

        marco = tk.Frame(top)
        marco.pack(fill="both", expand=True)
        txt = tk.Text(marco, font=("Consolas", 10))
        barra = tk.Scrollbar(marco, command=txt.yview)
        txt.configure(yscrollcommand=barra.set)
        txt.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        for p in self.motor.procesos_todos:
            txt.insert("end", f"=== P{p.pid} · {p.nombre}  (llegada={p.arrival_time}ms, nivel origen={p.nivel}, "
                               f"ráfaga total={p.rafaga_total}ms) ===\n")
            tramos = self.motor.historial.get(p.pid, [])
            if not tramos:
                txt.insert("end", "   (aún no ingresa al sistema)\n\n")
                continue
            for tr in tramos:
                if tr["tipo"] == "Terminado":
                    continue
                fin_val = tr["fin"] if tr["fin"] is not None else self.motor.tiempo
                fin_txt = f"{fin_val}ms" + (" (en curso)" if tr["fin"] is None else "")
                dur = fin_val - tr["inicio"]
                txt.insert("end", f"   {tr['tipo']:<10} | inicio={tr['inicio']:>5}ms | "
                                   f"fin={fin_txt:<14} | duración={dur:>4}ms\n")
            txt.insert("end", "\n")

        txt.config(state="disabled")
        tk.Button(top, text="Cerrar", command=top.destroy).pack(pady=6)