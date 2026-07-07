# -*- coding: utf-8 -*-
"""
Punto de entrada.
Ejecutar con:  python3 main.py
Dependencias: solo la biblioteca estándar de Python (tkinter).
"""
import tkinter as tk
from interfaz import AplicacionSimulador


def main():
    root = tk.Tk()
    app = AplicacionSimulador(root)
    root.mainloop()


if __name__ == "__main__":
    main()