# Análisis y correspondencia de la migración

## Proyecto original

El proyecto usa una arquitectura en tres capas:

- `modelo.py`: entidad `Proceso`, estados y reinicio del estado dinámico.
- `planificador.py`: motor de simulación independiente de la interfaz.
- `interfaz.py`: aplicación Tkinter, formularios, controles, Gantt, log e histórico.
- `main.py`: configuración DPI y arranque de la ventana.
- `ProcesosMultinivel3.spec`, `build/` y `dist/`: empaquetado y artefactos de PyInstaller.

## Correspondencia web

| Origen | Nueva implementación |
| --- | --- |
| `modelo.py` | `src/types.ts` |
| `planificador.py` | `src/engine.ts` |
| `interfaz.py` | `src/App.tsx` y `src/components/` |
| `main.py` | `src/main.tsx` |
| validación manual | `src/engine.test.ts` |

## Reglas preservadas

1. Las llegadas se procesan antes que los retornos de E/S.
2. N1 desaloja a N2/N3 y N2 desaloja a N3.
3. Solo Prioridad se apropia dentro de su propio nivel.
4. SJF es no apropiativo; RR cede al agotar quantum; FIFO conserva el orden.
5. Un RR desalojado por un nivel superior vuelve al frente de su cola.
6. El envejecimiento solo actúa en colas con Prioridad y antes de la primera ejecución.
7. Los puntos de E/S se interpretan como CPU acumulada.
8. Las métricas descuentan ráfaga total y duraciones de E/S del tiempo de retorno.

## Verificación de paridad

Con los cinco procesos de ejemplo, ambas versiones producen:

- tiempo final: 33 ms;
- finalización por PID: 16, 7, 20, 33 y 32 ms;
- tiempo de ejecución medio: 20,2 ms;
- tiempo de espera medio: 11,6 ms.
