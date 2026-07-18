# OrbitOS — migración web del simulador

Esta carpeta contiene una versión nueva e independiente en React + TypeScript. Los archivos Python originales del directorio padre no se modifican ni se sustituyen.

## Ejecutar

```bash
npm install
npm run dev
```

Para validar lógica y compilación:

```bash
npm test
npm run build
```

## Funciones migradas

- Motor discreto de 1 ms con jerarquía fija N1 > N2 > N3.
- Prioridad apropiativa, SJF, Round Robin y FIFO por cola.
- Cambio de configuración durante la simulación.
- Envejecimiento configurable hasta la primera ejecución.
- Llegadas, E/S, retornos, quantum y desempate de llegada nueva.
- Gestión visual de procesos antes de iniciar.
- Gantt por zonas con carriles, zoom y seguimiento automático.
- Estado de colas, inspector, registro, historial y métricas finales.

El test automatizado reproduce el escenario de ejemplo de Python y comprueba sus mismos resultados finales.
