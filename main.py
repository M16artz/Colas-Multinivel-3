# -*- coding: utf-8 -*-
"""
Punto de entrada.
Ejecutar con:  python3 main.py
Dependencias: solo la biblioteca estándar de Python (tkinter).
"""
import tkinter as tk
from interfaz import AplicacionSimulador


def _fijar_dpi_awareness():
    """En Windows, si el proceso no está marcado como "DPI aware", Tk puede
    mostrar mal los popups sin bordes (overrideredirect) -por ejemplo, el
    desplegable de un ttk.Combobox- como una ventana normal con título "tk".
    Se corrige marcando el proceso como DPI aware ANTES de crear el root."""
    import sys
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    _fijar_dpi_awareness()
    root = tk.Tk()
    app = AplicacionSimulador(root)
    root.mainloop()


if __name__ == "__main__":
    main()