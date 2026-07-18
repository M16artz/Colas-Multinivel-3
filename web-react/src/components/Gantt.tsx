import { useEffect, useMemo, useRef } from 'react';
import { Crosshair, Minus, Plus } from 'lucide-react';
import type { RuntimeProcess, Segment, SimulationSnapshot, Zone } from '../types';

const COLORS = ['#ff6b4a', '#3b82f6', '#25c08a', '#f7b731', '#a56eff', '#20b9c4', '#ed7b32', '#64748b', '#ef476f', '#5e81f4'];
export const processColor = (pid: number) => COLORS[(pid - 1) % COLORS.length];
const translucentProcessColor = (pid: number) => `${processColor(pid)}cc`;
const ROWS: { zone: Zone; label: string; lanes: number }[] = [
  { zone: 'CPU', label: 'CPU', lanes: 1 },
  { zone: 'Cola N1', label: 'Listos N1', lanes: 3 },
  { zone: 'Cola N2', label: 'Listos N2', lanes: 3 },
  { zone: 'Cola N3', label: 'Listos N3', lanes: 3 },
  { zone: 'E/S', label: 'E / S', lanes: 2 },
];

interface Bar { process: RuntimeProcess; segment: Segment; end: number; lane: number }

function assignLanes(processes: RuntimeProcess[], history: Record<number, Segment[]>, zone: Zone, now: number, lanes: number): Bar[] {
  const bars = processes.flatMap((process) => (history[process.pid] ?? []).filter((segment) => segment.type === zone).map((segment) => ({ process, segment, end: segment.end ?? now })));
  bars.sort((a, b) => a.segment.start - b.segment.start);
  const laneEnds = Array(lanes).fill(-1);
  return bars.map((bar) => {
    let lane = laneEnds.findIndex((end) => end <= bar.segment.start);
    if (lane < 0) lane = lanes - 1;
    laneEnds[lane] = bar.end;
    return { ...bar, lane };
  });
}

interface Props {
  snapshot: SimulationSnapshot | null;
  zoom: number;
  follow: boolean;
  onZoom: (zoom: number) => void;
  onFollow: (follow: boolean) => void;
}

export function Gantt({ snapshot, zoom, follow, onZoom, onFollow }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const time = snapshot?.time ?? 0;
  const width = Math.max(900, (time + 5) * zoom);
  const marks = useMemo(() => Array.from({ length: Math.ceil(width / zoom) + 1 }, (_, index) => index), [width, zoom]);

  useEffect(() => {
    if (follow && scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth;
  }, [time, follow, zoom]);

  const goNow = () => {
    onFollow(true);
    requestAnimationFrame(() => { if (scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth; });
  };

  return (
    <section className="panel gantt-panel">
      <div className="panel-head gantt-head">
        <div><span className="eyebrow">Línea de tiempo</span><h2>Actividad por zona</h2></div>
        <div className="gantt-tools">
          <label className="follow-check"><input type="checkbox" checked={follow} onChange={(e) => onFollow(e.target.checked)} /> Seguir ahora</label>
          <div className="zoom-control"><button onClick={() => onZoom(Math.max(10, zoom - 5))} aria-label="Alejar"><Minus size={16} /></button><span>{zoom} px/ms</span><button onClick={() => onZoom(Math.min(120, zoom + 5))} aria-label="Acercar"><Plus size={16} /></button></div>
          <button className="btn compact" onClick={goNow}><Crosshair size={16} /> Ahora</button>
        </div>
      </div>
      <div className="timeline-shell">
        <div className="timeline-labels"><div className="ruler-label">t (ms)</div>{ROWS.map((row) => <div className="row-label" key={row.zone} style={{ height: row.lanes * 34 }}>{row.label}</div>)}</div>
        <div className="timeline-scroll" ref={scroller} onWheel={() => onFollow(false)} onPointerDown={() => onFollow(false)}>
          <div className="timeline" style={{ width }}>
            <div className="ruler">{marks.map((mark) => <div key={mark} className={`tick ${mark % 5 === 0 ? 'major' : ''}`} style={{ left: mark * zoom }}><span>{mark}</span></div>)}</div>
            {ROWS.map((row) => {
              const bars = snapshot ? assignLanes(snapshot.all, snapshot.history, row.zone, time, row.lanes) : [];
              return <div className="timeline-row" key={row.zone} style={{ height: row.lanes * 34 }}>
                {bars.map(({ process, segment, end, lane }, index) => {
                  const duration = Math.max(0.45, end - segment.start);
                  return <div key={`${process.pid}-${segment.start}-${index}`} className={`gantt-bar ${row.zone === 'CPU' ? 'cpu-bar' : ''}`} title={`${process.nombre} · ${row.label} · ${segment.start}–${end} ms`} style={{ left: segment.start * zoom, width: duration * zoom, top: lane * 34 + 5, backgroundColor: translucentProcessColor(process.pid) }}><span>{duration * zoom > 28 ? `P${process.pid}` : ''}</span></div>;
                })}
              </div>;
            })}
            <div className="time-cursor" style={{ left: time * zoom }}><span>t={time}</span></div>
          </div>
        </div>
      </div>
      <div className="process-legend">{(snapshot?.all ?? []).map((process) => <span key={process.pid} style={{ backgroundColor: translucentProcessColor(process.pid) }}><i />{process.nombre}</span>)}</div>
    </section>
  );
}
