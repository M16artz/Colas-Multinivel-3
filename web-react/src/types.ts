export const ALGORITHMS = ['Prioridad', 'SJF', 'RR'] as const;
export type Algorithm = (typeof ALGORITHMS)[number] | 'FIFO';
export type Level = 1 | 2 | 3;
export type ProcessState = 'Pendiente' | 'Listo' | 'Ejecución' | 'Bloqueado (E/S)' | 'Terminado';
export type Zone = 'CPU' | 'Cola N1' | 'Cola N2' | 'Cola N3' | 'E/S' | 'Terminado';

export interface ProcessDefinition {
  pid: number;
  nombre: string;
  arrivalTime: number;
  level: Level;
  initialPriority: number;
  totalBurst: number;
  ioPoints: number[];
  ioDurations: number[];
}

export interface RuntimeProcess extends ProcessDefinition {
  currentPriority: number;
  remainingBurst: number;
  totalCpuExecuted: number;
  nextIoIndex: number;
  state: ProcessState;
  queueEntryTime: number;
  hasRun: boolean;
  agingStepsApplied: number;
  quantumUsed: number;
  ioEndTime: number | null;
  isNewArrival: boolean;
  completionTime: number | null;
}

export interface Segment {
  type: Zone;
  start: number;
  end: number | null;
}

export interface SimulationConfig {
  quantum: number;
  agingInterval: number;
  agingEnabled: boolean;
  agingThreshold: number;
  agingCondition: 'mayor' | 'mayor_igual';
  algorithms: Record<Level, Algorithm>;
}

export interface Metrics {
  averageTurnaround: number;
  averageWaiting: number;
}

export interface SimulationSnapshot {
  time: number;
  all: RuntimeProcess[];
  ready: Record<Level, RuntimeProcess[]>;
  blocked: RuntimeProcess[];
  finished: RuntimeProcess[];
  cpu: RuntimeProcess | null;
  log: string[];
  history: Record<number, Segment[]>;
  isFinished: boolean;
  metrics: Metrics | null;
  config: SimulationConfig;
}
