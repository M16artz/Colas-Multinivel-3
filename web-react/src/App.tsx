import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, BookOpen, ChevronDown, ChevronRight, CirclePause, CirclePlay, Clock3,
  Download, FileText, History, Layers3, Pencil, Plus, RefreshCw, RotateCcw,
  Settings2, Square, Trash2, X,
  Upload,
} from 'lucide-react';
import { DEFAULT_CONFIG, SAMPLE_PROCESSES, SimulationEngine } from './engine';
import { Gantt, processColor } from './components/Gantt';
import { ProcessModal } from './components/ProcessModal';
import { ALGORITHMS, type Level, type ProcessDefinition, type SimulationConfig, type SimulationSnapshot } from './types';

type Dialog = 'history' | 'log' | 'calculations' | null;

const cloneDefinitions = () => SAMPLE_PROCESSES.map((process) => ({ ...process, ioPoints: [...process.ioPoints], ioDurations: [...process.ioDurations] }));
const escapeXml = (value: string | number) => String(value).replace(/[<>&"']/g, (character) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[character]!);

function configurationXml(definitions: ProcessDefinition[], config: SimulationConfig, speed: number, zoom: number) {
  const processes = definitions.map((process) => {
    const operations = process.ioPoints.map((point, index) => `      <operacion-es punto-cpu="${point}" duracion="${process.ioDurations[index]}" />`).join('\n');
    return `    <proceso pid="${process.pid}" nombre="${escapeXml(process.nombre)}" llegada="${process.arrivalTime}" rafaga-cpu="${process.totalBurst}" nivel="${process.level}" prioridad-inicial="${process.initialPriority}">\n${operations}\n    </proceso>`;
  }).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>
<simulacion version="1" velocidad="${speed}" zoom="${zoom}">
  <procesos>
${processes}
  </procesos>
  <planificacion quantum="${config.quantum}" envejecimiento-activo="${config.agingEnabled}" intervalo-envejecimiento="${config.agingInterval}" condicion-envejecimiento="${config.agingCondition}" umbral-envejecimiento="${config.agingThreshold}">
    <algoritmo nivel="1" tipo="${config.algorithms[1]}" />
    <algoritmo nivel="2" tipo="${config.algorithms[2]}" />
    <algoritmo nivel="3" tipo="${config.algorithms[3]}" />
  </planificacion>
</simulacion>`;
}

function requiredInteger(element: Element, attribute: string, minimum?: number) {
  const raw = element.getAttribute(attribute);
  const value = raw == null || raw.trim() === '' ? Number.NaN : Number(raw);
  if (!Number.isInteger(value) || (minimum != null && value < minimum)) throw new Error(`El atributo “${attribute}” no es válido.`);
  return value;
}

function App() {
  const [definitions, setDefinitions] = useState<ProcessDefinition[]>(cloneDefinitions);
  const [config, setConfig] = useState<SimulationConfig>({ ...DEFAULT_CONFIG, algorithms: { ...DEFAULT_CONFIG.algorithms } });
  const [engine, setEngine] = useState<SimulationEngine | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(300);
  const [zoom, setZoom] = useState(30);
  const [follow, setFollow] = useState(true);
  const [editing, setEditing] = useState<ProcessDefinition | 'new' | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [logExpanded, setLogExpanded] = useState(false);
  const [xmlMessage, setXmlMessage] = useState('');
  const [selectedPid, setSelectedPid] = useState<number | null>(null);
  const logScroller = useRef<HTMLDivElement>(null);
  const xmlInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback((source: SimulationEngine) => setSnapshot(source.snapshot()), []);

  useEffect(() => {
    if (!running || !engine) return;
    if (snapshot?.isFinished) { setRunning(false); return; }
    const timer = window.setTimeout(() => { engine.step(); refresh(engine); }, speed);
    return () => window.clearTimeout(timer);
  }, [running, engine, snapshot?.time, snapshot?.isFinished, speed, refresh]);

  useEffect(() => {
    if (!logExpanded || !logScroller.current) return;
    logScroller.current.scrollTop = logScroller.current.scrollHeight;
  }, [snapshot?.log.length, logExpanded]);

  useEffect(() => {
    if (!engine) return;
    engine.updateConfig(config);
    refresh(engine);
  }, [config, engine, refresh]);

  const start = () => {
    if (!definitions.length) return;
    const next = new SimulationEngine(definitions, config);
    setEngine(next);
    setSnapshot(next.snapshot());
    setRunning(true);
    setFollow(true);
  };

  const reset = () => {
    setEngine(null);
    setSnapshot(null);
    setRunning(false);
    setFollow(true);
    setSelectedPid(null);
  };

  const stepOnce = () => {
    const source = engine ?? new SimulationEngine(definitions, config);
    if (!engine) setEngine(source);
    source.step();
    refresh(source);
  };

  const runToEnd = () => {
    const source = engine ?? new SimulationEngine(definitions, config);
    if (!engine) setEngine(source);
    setRunning(false);
    source.runToEnd();
    refresh(source);
    setFollow(true);
  };

  const saveProcess = (process: ProcessDefinition) => {
    setDefinitions((current) => current.some((item) => item.pid === process.pid) ? current.map((item) => item.pid === process.pid ? process : item) : [...current, process]);
    setEditing(null);
  };

  const exportXml = () => {
    const blob = new Blob([configurationXml(definitions, config, speed, zoom)], { type: 'application/xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'simulacion-orbitos.xml';
    link.click();
    URL.revokeObjectURL(url);
    setXmlMessage('Configuración exportada correctamente.');
  };

  const importXml = async (file: File) => {
    try {
      const documentXml = new DOMParser().parseFromString(await file.text(), 'application/xml');
      if (documentXml.querySelector('parsererror')) throw new Error('El archivo no contiene XML válido.');
      const root = documentXml.documentElement;
      const planning = root.querySelector(':scope > planificacion');
      if (root.tagName !== 'simulacion' || !planning) throw new Error('El archivo no corresponde a una configuración de OrbitOS.');

      const importedProcesses = [...root.querySelectorAll(':scope > procesos > proceso')].map((element) => {
        const operations = [...element.querySelectorAll(':scope > operacion-es')];
        return {
          pid: requiredInteger(element, 'pid', 1),
          nombre: element.getAttribute('nombre')?.trim() || `P${element.getAttribute('pid')}`,
          arrivalTime: requiredInteger(element, 'llegada', 0),
          totalBurst: requiredInteger(element, 'rafaga-cpu', 1),
          level: requiredInteger(element, 'nivel', 1) as Level,
          initialPriority: requiredInteger(element, 'prioridad-inicial'),
          ioPoints: operations.map((operation) => requiredInteger(operation, 'punto-cpu', 1)),
          ioDurations: operations.map((operation) => requiredInteger(operation, 'duracion', 0)),
        };
      });
      if (!importedProcesses.length) throw new Error('El archivo no contiene procesos.');
      if (importedProcesses.some((process) => process.level > 3)) throw new Error('Los niveles de cola deben estar entre 1 y 3.');
      if (new Set(importedProcesses.map((process) => process.pid)).size !== importedProcesses.length) throw new Error('Los PID deben ser únicos.');
      if (importedProcesses.some((process) => process.ioPoints.some((point, index) => point > process.totalBurst || (index > 0 && point < process.ioPoints[index - 1])))) throw new Error('Los puntos de E/S deben ser crecientes y no superar la ráfaga.');

      const algorithms = {} as SimulationConfig['algorithms'];
      for (const level of [1, 2, 3] as Level[]) {
        const algorithm = planning.querySelector(`algoritmo[nivel="${level}"]`)?.getAttribute('tipo') ?? '';
        if (!ALGORITHMS.some((candidate) => candidate === algorithm)) throw new Error(`El algoritmo del nivel ${level} no es válido.`);
        algorithms[level] = algorithm as SimulationConfig['algorithms'][Level];
      }
      const agingEnabled = planning.getAttribute('envejecimiento-activo');
      if (agingEnabled !== 'true' && agingEnabled !== 'false') throw new Error('El estado de envejecimiento no es válido.');
      const agingCondition = planning.getAttribute('condicion-envejecimiento');
      if (agingCondition !== 'mayor' && agingCondition !== 'mayor_igual') throw new Error('La condición de envejecimiento no es válida.');
      const importedConfig: SimulationConfig = {
        quantum: requiredInteger(planning, 'quantum', 1),
        agingEnabled: agingEnabled === 'true',
        agingInterval: requiredInteger(planning, 'intervalo-envejecimiento', 1),
        agingCondition,
        agingThreshold: requiredInteger(planning, 'umbral-envejecimiento'),
        algorithms,
      };

      const importedSpeed = Number(root.getAttribute('velocidad'));
      const importedZoom = Number(root.getAttribute('zoom'));
      setDefinitions(importedProcesses);
      setConfig(importedConfig);
      if (Number.isFinite(importedSpeed) && importedSpeed > 0) setSpeed(importedSpeed);
      if (Number.isFinite(importedZoom) && importedZoom >= 10 && importedZoom <= 120) setZoom(importedZoom);
      setEngine(null);
      setSnapshot(null);
      setRunning(false);
      setFollow(true);
      setSelectedPid(null);
      setXmlMessage(`Ejemplo “${file.name}” importado correctamente.`);
    } catch (error) {
      setXmlMessage(`Error: ${error instanceof Error ? error.message : 'No fue posible importar el archivo.'}`);
    }
  };

  const updateAlgorithm = (level: Level, value: string) => setConfig((current) => ({ ...current, algorithms: { ...current.algorithms, [level]: value } as SimulationConfig['algorithms'] }));
  const nextPid = Math.max(0, ...definitions.map((process) => process.pid)) + 1;
  const currentProcesses = snapshot?.all ?? definitions;
  const selected = snapshot?.all.find((process) => process.pid === selectedPid) ?? null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><Layers3 size={22} /></div><div><strong>Proceso<span>PaTi3</span></strong></div></div>
        <div className="top-status"><span className={`status-dot ${running ? 'live' : ''}`} />{snapshot?.isFinished ? 'Simulación completada' : running ? 'Motor en ejecución' : snapshot ? 'Simulación pausada' : 'Listo para simular'}</div>
        <div className="clock"><Clock3 size={17} /><div><small>Tiempo simulado</small><strong>{snapshot?.time ?? 0} ms</strong></div></div>
      </header>

      <main>
        <section className="hero-row">
          <div><span className="eyebrow">Colas multinivel · 1 &gt; 2 &gt; 3</span><h1>Proyecto de Sistemas Operativos<br /></h1><p>Miguel Armas, Soledad Buri, Richard Chamba, Emilio Flores, Odalis Rosillo.</p></div>
          <div className="hero-actions">
            {!running ? <button className="btn primary large" onClick={snapshot ? () => setRunning(true) : start} disabled={snapshot?.isFinished || !definitions.length}><CirclePlay size={19} />{snapshot ? 'Reanudar' : 'Iniciar simulación'}</button> : <button className="btn primary large" onClick={() => setRunning(false)}><CirclePause size={19} />Pausar</button>}
            <button className="btn ghost large" onClick={reset}><RotateCcw size={18} />Reiniciar</button>
          </div>
        </section>

        <div className="workspace-grid">
          <div className="main-column">
            <section className="panel process-panel">
              <div className="panel-head"><div><span className="eyebrow">Carga de trabajo</span><h2>Procesos</h2></div><button className="btn compact" disabled={Boolean(engine)} onClick={() => setEditing('new')}><Plus size={16} />Agregar</button></div>
              <div className="table-wrap">
                <table><thead><tr><th>Proceso</th><th>Llegada</th><th>CPU</th><th>Puntos E/S</th><th>Duración E/S</th><th>Nivel</th><th>Prioridad</th><th>Estado</th><th /></tr></thead>
                  <tbody>{currentProcesses.map((process) => {
                    const runtime = snapshot?.all.find((item) => item.pid === process.pid);
                    const totalIoDuration = process.ioDurations.reduce((sum, duration) => sum + duration, 0);
                    return <tr key={process.pid} className={selectedPid === process.pid ? 'selected' : ''} onClick={() => setSelectedPid(process.pid)}>
                      <td><div className="process-name"><i style={{ backgroundColor: processColor(process.pid) }} /><div><strong>{process.nombre}</strong><small>PID {process.pid}</small></div></div></td>
                      <td>{process.arrivalTime} ms</td><td>{runtime?.remainingBurst ?? process.totalBurst}<small className="muted"> / {process.totalBurst} ms</small></td><td>{process.ioPoints.length ? process.ioPoints.join(' · ') : '—'}</td><td>{process.ioDurations.length ? <><strong className="io-total">{totalIoDuration} ms</strong><small className="muted io-detail">{process.ioDurations.join(' · ')}</small></> : '—'}</td><td><span className={`level-badge level-${process.level}`}>N{process.level}</span></td><td>{runtime?.currentPriority ?? process.initialPriority}</td><td><StateBadge state={runtime?.state ?? 'Definido'} /></td>
                      <td><div className="row-actions"><button disabled={Boolean(engine)} aria-label={`Editar ${process.nombre}`} onClick={(event) => { event.stopPropagation(); setEditing(process); }}><Pencil size={15} /></button><button disabled={Boolean(engine)} aria-label={`Eliminar ${process.nombre}`} onClick={(event) => { event.stopPropagation(); setDefinitions((items) => items.filter((item) => item.pid !== process.pid)); }}><Trash2 size={15} /></button><ChevronRight size={16} /></div></td>
                    </tr>;
                  })}</tbody>
                </table>
              </div>
              {!definitions.length && <div className="empty-state"><Layers3 size={30} /><p>No hay procesos definidos.</p><button className="btn compact" onClick={() => setEditing('new')}>Crear el primero</button></div>}
            </section>

            <Gantt snapshot={snapshot} zoom={zoom} follow={follow} onZoom={setZoom} onFollow={setFollow} />

            <section className={`panel log-panel ${logExpanded ? 'expanded' : ''}`}>
              <div className="panel-head log-panel-head" role="button" tabIndex={0} aria-expanded={logExpanded} onClick={() => setLogExpanded((value) => !value)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setLogExpanded((value) => !value); } }}>
                <div><span className="eyebrow">Telemetría</span><h2>Registro de eventos</h2></div>
                <div className="log-head-actions">{logExpanded && <button className="text-button" onClick={(event) => { event.stopPropagation(); setDialog('log'); }}><FileText size={15} />Abrir registro completo</button>}<ChevronDown className="collapse-chevron" size={18} /></div>
              </div>
              {logExpanded && <div className="terminal" ref={logScroller}>{snapshot?.log.length ? snapshot.log.slice(-12).map((line, index) => <div key={`${index}-${line}`}><span>{line.slice(0, 12)}</span>{line.slice(12)}</div>) : <div className="terminal-idle"><Square size={12} /> El motor espera la orden de inicio…</div>}</div>}
            </section>
          </div>

          <aside className="side-column">
            <section className="panel config-panel">
              <div className="panel-head"><div><span className="eyebrow">Ajustes en vivo</span><h2>Planificación</h2></div><Settings2 size={19} className="panel-icon" /></div>
              <div className="config-section"><h3>Algoritmo por cola</h3>{([1, 2, 3] as Level[]).map((level) => <label className="algo-row" key={level}><span><i className={`queue-dot q${level}`} />Nivel {level}</span><select value={config.algorithms[level]} onChange={(e) => updateAlgorithm(level, e.target.value)}>{ALGORITHMS.map((algorithm) => <option key={algorithm}>{algorithm}</option>)}</select></label>)}</div>
              <div className="config-section two-fields"><label className="field"><span>Quantum RR</span><div className="input-unit"><input type="number" min="1" value={config.quantum} onChange={(e) => setConfig((c) => ({ ...c, quantum: Math.max(1, Number(e.target.value)) }))} /><b>ms</b></div></label><label className="field"><span>Velocidad</span><select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={1000}>0.5×</option><option value={500}>1×</option><option value={300}>2×</option><option value={100}>5×</option><option value={25}>Máxima</option></select></label></div>
              <div className="config-section aging"><div className="switch-row"><div><h3>Envejecimiento</h3><p>Mejora la prioridad mientras espera.</p></div><label className="switch"><input type="checkbox" checked={config.agingEnabled} onChange={(e) => setConfig((c) => ({ ...c, agingEnabled: e.target.checked }))} /><span /></label></div>
                <div className="two-fields"><label className="field"><span>Cada</span><div className="input-unit"><input type="number" min="1" value={config.agingInterval} onChange={(e) => setConfig((c) => ({ ...c, agingInterval: Math.max(1, Number(e.target.value)) }))} /><b>ms</b></div></label><label className="field"><span>Si prioridad</span><div className="condition-input"><select value={config.agingCondition} onChange={(e) => setConfig((c) => ({ ...c, agingCondition: e.target.value as SimulationConfig['agingCondition'] }))}><option value="mayor_igual">≥</option><option value="mayor">&gt;</option></select><input type="number" value={config.agingThreshold} onChange={(e) => setConfig((c) => ({ ...c, agingThreshold: Number(e.target.value) }))} /></div></label></div>
              </div>
              <div className="step-actions"><button className="btn compact" disabled={running || snapshot?.isFinished || !definitions.length} onClick={stepOnce}><ChevronRight size={16} />Paso +1 ms</button><button className="btn compact ghost" disabled={running || snapshot?.isFinished || !definitions.length} onClick={runToEnd}><RefreshCw size={15} />Hasta el final</button></div>
              <div className="xml-actions"><button className="btn compact" onClick={exportXml}><Download size={15} />Guardar XML</button><button className="btn compact ghost" onClick={() => xmlInput.current?.click()}><Upload size={15} />Importar ejemplo</button><input ref={xmlInput} type="file" accept=".xml,application/xml,text/xml" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importXml(file); event.target.value = ''; }} />{xmlMessage && <p className={xmlMessage.startsWith('Error:') ? 'xml-message error' : 'xml-message'}>{xmlMessage}</p>}</div>
            </section>

            <section className="panel queue-panel">
              <div className="panel-head"><div><span className="eyebrow">Estado instantáneo</span><h2>Colas</h2></div><Clock3 size={19} className="panel-icon" /></div>
              {([1, 2, 3] as Level[]).map((level) => <div className="queue-row" key={level}><div><span className={`queue-label q${level}`}>N{level}</span><small>{config.algorithms[level]}</small></div><div className="queue-items">{snapshot?.ready[level].length ? snapshot.ready[level].map((process) => <span key={process.pid} style={{ borderColor: processColor(process.pid) }}>{process.nombre}</span>) : <em>Vacía</em>}</div></div>)}
              <div className="io-row"><span><Activity size={15} />E / S</span><div>{snapshot?.blocked.length ? snapshot.blocked.map((process) => <b key={process.pid}>{process.nombre} <small>hasta {process.ioEndTime}ms</small></b>) : <em>Sin bloqueados</em>}</div></div>
            </section>

            <section className="panel final-metrics-panel">
              <div className="final-metric final-metric-execution"><span>Tiempo de ejecución medio</span><strong>{snapshot?.metrics ? `${snapshot.metrics.averageTurnaround.toFixed(2)} ms` : '—'}</strong><small>{snapshot?.metrics ? 'Resultado final' : 'Disponible al finalizar'}</small></div>
              <div className="final-metric final-metric-waiting"><span>Tiempo de espera promedio</span><strong>{snapshot?.metrics ? `${snapshot.metrics.averageWaiting.toFixed(2)} ms` : '—'}</strong><small>{snapshot?.metrics ? 'Resultado final' : 'Disponible al finalizar'}</small></div>
            </section>

            <section className="panel quick-panel"><button onClick={() => setDialog('history')}><History size={18} /><span><strong>Histórico detallado</strong><small>Todos los tramos por proceso</small></span><ChevronRight size={17} /></button><button onClick={() => setDialog('calculations')}><BookOpen size={18} /><span><strong>Cálculos completos</strong><small>Espera media y ejecución media</small></span><ChevronRight size={17} /></button></section>

            {selected && <section className="panel inspector"><div className="panel-head"><div><span className="eyebrow">Inspector</span><h2>{selected.nombre}</h2></div><button className="icon-btn" onClick={() => setSelectedPid(null)}><X size={16} /></button></div><dl><div><dt>Estado</dt><dd><StateBadge state={selected.state} /></dd></div><div><dt>CPU consumida</dt><dd>{selected.totalCpuExecuted} ms</dd></div><div><dt>Ráfaga restante</dt><dd>{selected.remainingBurst} ms</dd></div><div><dt>Prioridad actual</dt><dd>{selected.currentPriority}</dd></div><div><dt>Fin</dt><dd>{selected.completionTime == null ? '—' : `${selected.completionTime} ms`}</dd></div></dl></section>}
          </aside>
        </div>
      </main>

      {editing && <ProcessModal process={editing === 'new' ? null : editing} nextPid={nextPid} onSave={saveProcess} onClose={() => setEditing(null)} />}
      {dialog && <DetailDialog type={dialog} snapshot={snapshot} onClose={() => setDialog(null)} />}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const className = state === 'Ejecución' ? 'running' : state.startsWith('Bloqueado') ? 'blocked' : state === 'Terminado' ? 'done' : state === 'Listo' ? 'ready' : 'defined';
  return <span className={`state-badge ${className}`}><i />{state}</span>;
}

function DetailDialog({ type, snapshot, onClose }: { type: Exclude<Dialog, null>; snapshot: SimulationSnapshot | null; onClose: () => void }) {
  useEffect(() => { const listener = (event: KeyboardEvent) => event.key === 'Escape' && onClose(); window.addEventListener('keydown', listener); return () => window.removeEventListener('keydown', listener); }, [onClose]);
  const titles = type === 'history' ? ['Trazabilidad', 'Histórico por proceso'] : type === 'calculations' ? ['Métricas de la simulación', 'Cálculos completos'] : ['Auditoría del motor', 'Registro completo'];
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="modal detail-modal" role="dialog" aria-modal="true"><div className="modal-head"><div><span className="eyebrow">{titles[0]}</span><h2>{titles[1]}</h2></div><button className="icon-btn" onClick={onClose}><X size={19} /></button></div>
    {!snapshot ? <div className="dialog-empty">Inicia la simulación para generar información.</div> : type === 'log' ? <div className="full-log">{snapshot.log.map((line, index) => <div key={`${index}-${line}`}>{line}</div>)}</div> : type === 'calculations' ? <CalculationsView snapshot={snapshot} /> : <div className="history-list">{snapshot.all.map((process) => <article key={process.pid}><header><i style={{ background: processColor(process.pid) }} /><div><strong>{process.nombre}</strong><small>Llegada {process.arrivalTime} ms · Nivel {process.level} · CPU {process.totalBurst} ms</small></div></header><div className="segment-list">{(snapshot.history[process.pid] ?? []).filter((segment) => segment.type !== 'Terminado').map((segment, index) => { const end = segment.end ?? snapshot.time; return <div key={`${segment.start}-${index}`}><span>{segment.type}</span><b>{segment.start} → {end} ms</b><small>{end - segment.start} ms</small></div>; })}</div></article>)}</div>}
    <div className="modal-actions"><button className="btn primary" onClick={onClose}>Cerrar</button></div></section></div>;
}

function CalculationsView({ snapshot }: { snapshot: SimulationSnapshot }) {
  const calculations = useMemo(() => snapshot.all.map((process) => {
    const totalIo = process.ioDurations.reduce((sum, duration) => sum + duration, 0);
    const execution = process.completionTime == null ? null : process.completionTime - process.arrivalTime;
    const waiting = execution == null ? null : execution - process.totalBurst - totalIo;
    return { process, totalIo, execution, waiting };
  }), [snapshot.all]);

  return <div className="calculations-grid">
    <CalculationColumn kind="waiting" title="Tiempo de espera medio" subtitle="Ejecución − CPU − E/S" value={snapshot.metrics?.averageWaiting ?? null} calculations={calculations} />
    <CalculationColumn kind="execution" title="Tiempo de ejecución medio" subtitle="Finalización − llegada" value={snapshot.metrics?.averageTurnaround ?? null} calculations={calculations} />
  </div>;
}

function CalculationColumn({ kind, title, subtitle, value, calculations }: { kind: 'waiting' | 'execution'; title: string; subtitle: string; value: number | null; calculations: { process: SimulationSnapshot['all'][number]; totalIo: number; execution: number | null; waiting: number | null }[] }) {
  return <section className={`calculation-column calculation-${kind}`}><header><div><span>{title}</span><small>{subtitle}</small></div><strong>{value == null ? 'Pendiente' : `${value.toFixed(2)} ms`}</strong></header><div className="calculation-list">{calculations.map(({ process, totalIo, execution, waiting }) => {
    const result = kind === 'waiting' ? waiting : execution;
    return <article key={process.pid}><i style={{ background: processColor(process.pid) }} /><div><strong>{process.nombre}</strong><small>{kind === 'waiting' ? (execution == null ? 'Esperando finalización' : `${execution} − ${process.totalBurst} − ${totalIo}`) : (process.completionTime == null ? 'Esperando finalización' : `${process.completionTime} − ${process.arrivalTime}`)}</small></div><b>{result == null ? '—' : `${result} ms`}</b></article>;
  })}</div><footer><span>Σ valores / {calculations.length} procesos</span><b>{value == null ? 'Disponible al finalizar' : `${value.toFixed(2)} ms`}</b></footer></section>;
}

export default App;
