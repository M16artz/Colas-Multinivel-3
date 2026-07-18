import { useEffect, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import type { Level, ProcessDefinition } from '../types';

interface Props {
  process: ProcessDefinition | null;
  nextPid: number;
  onSave: (process: ProcessDefinition) => void;
  onClose: () => void;
}

const parseList = (value: string) => value.trim() ? value.split(/[,-]/).map((part) => Number(part.trim())) : [];

export function ProcessModal({ process, nextPid, onSave, onClose }: Props) {
  const [name, setName] = useState(process?.nombre ?? '');
  const [arrival, setArrival] = useState(String(process?.arrivalTime ?? 0));
  const [burst, setBurst] = useState(String(process?.totalBurst ?? 5));
  const [level, setLevel] = useState<Level>(process?.level ?? 1);
  const [priority, setPriority] = useState(String(process?.initialPriority ?? 1));
  const [ioPoints, setIoPoints] = useState(process?.ioPoints.join('-') ?? '');
  const [ioDurations, setIoDurations] = useState(process?.ioDurations.join('-') ?? '');
  const [error, setError] = useState('');

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const points = parseList(ioPoints);
    const durations = parseList(ioDurations);
    const arrivalNumber = Number(arrival);
    const burstNumber = Number(burst);
    const priorityNumber = Number(priority || 0);
    if (![arrivalNumber, burstNumber, priorityNumber, ...points, ...durations].every(Number.isInteger)) return setError('Todos los tiempos y prioridades deben ser enteros.');
    if (arrivalNumber < 0) return setError('La llegada no puede ser negativa.');
    if (burstNumber <= 0) return setError('La ráfaga debe ser mayor que cero.');
    if (points.length !== durations.length) return setError('Cada punto de E/S necesita una duración.');
    if (points.some((point, index) => point <= 0 || point > burstNumber || (index > 0 && point < points[index - 1]))) return setError('Los puntos de E/S deben ser crecientes y no superar la ráfaga.');
    if (durations.some((duration) => duration < 0)) return setError('Las duraciones de E/S no pueden ser negativas.');
    const pid = process?.pid ?? nextPid;
    onSave({ pid, nombre: name.trim() || `P${pid}`, arrivalTime: arrivalNumber, totalBurst: burstNumber, level, initialPriority: priorityNumber, ioPoints: points, ioDurations: durations });
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="modal" onSubmit={submit} aria-labelledby="process-title">
        <div className="modal-head">
          <div><span className="eyebrow">Definición del proceso</span><h2 id="process-title">{process ? `Editar ${process.nombre}` : 'Nuevo proceso'}</h2></div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Cerrar"><X size={19} /></button>
        </div>
        <div className="form-grid">
          <label className="field field-wide"><span>Nombre</span><input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder={`P${process?.pid ?? nextPid}`} /></label>
          <label className="field"><span>Llegada (ms)</span><input inputMode="numeric" value={arrival} onChange={(e) => setArrival(e.target.value)} /></label>
          <label className="field"><span>Ráfaga CPU (ms)</span><input inputMode="numeric" value={burst} onChange={(e) => setBurst(e.target.value)} /></label>
          <label className="field"><span>Nivel de cola</span><select value={level} onChange={(e) => setLevel(Number(e.target.value) as Level)}><option value={1}>Nivel 1</option><option value={2}>Nivel 2</option><option value={3}>Nivel 3</option></select></label>
          <label className="field"><span>Prioridad inicial</span><input inputMode="numeric" value={priority} onChange={(e) => setPriority(e.target.value)} /></label>
          <label className="field"><span>Puntos E/S</span><input className="io-example" value={ioPoints} onChange={(e) => setIoPoints(e.target.value)} placeholder="3-7" /><small>CPU acumulada</small></label>
          <label className="field"><span>Duraciones E/S</span><input className="io-example" value={ioDurations} onChange={(e) => setIoDurations(e.target.value)} placeholder="2-4" /><small>Una por cada punto</small></label>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="modal-actions"><button type="button" className="btn ghost" onClick={onClose}>Cancelar</button><button className="btn primary" type="submit">Guardar proceso</button></div>
      </form>
    </div>
  );
}
