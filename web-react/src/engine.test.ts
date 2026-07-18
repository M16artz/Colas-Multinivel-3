import { describe, expect, it } from 'vitest';
import { DEFAULT_CONFIG, SAMPLE_PROCESSES, SimulationEngine } from './engine';

describe('SimulationEngine', () => {
  it('reproduce los resultados del ejemplo original en Python', () => {
    const result = new SimulationEngine(SAMPLE_PROCESSES, DEFAULT_CONFIG).runToEnd();
    expect(result.time).toBe(33);
    expect(result.metrics?.averageTurnaround).toBe(20.2);
    expect(result.metrics?.averageWaiting).toBe(11.6);
    expect(result.all.map((process) => process.completionTime)).toEqual([16, 7, 20, 33, 32]);
  });

  it('aplica envejecimiento según la prioridad inicial hasta la primera ejecución', () => {
    const processes = [
      { pid: 1, nombre: 'P1', arrivalTime: 0, totalBurst: 10, level: 1 as const, initialPriority: 0, ioPoints: [], ioDurations: [] },
      { pid: 2, nombre: 'P2', arrivalTime: 0, totalBurst: 1, level: 1 as const, initialPriority: 3, ioPoints: [], ioDurations: [] },
    ];
    const config = {
      ...DEFAULT_CONFIG,
      agingInterval: 1,
      agingThreshold: 2,
      agingCondition: 'mayor_igual' as const,
      algorithms: { ...DEFAULT_CONFIG.algorithms },
    };

    const result = new SimulationEngine(processes, config).runToEnd();
    const agingEvents = result.log.filter((line) => line.includes('P2 ENVEJECE'));

    expect(agingEvents).toHaveLength(4);
    expect(agingEvents.map((line) => line.match(/prioridad=(-?\d+)/)?.[1])).toEqual(['2', '1', '0', '-1']);
    expect(result.all.find((process) => process.pid === 2)?.completionTime).toBe(5);
  });
});
