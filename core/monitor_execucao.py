from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any


@dataclass
class ExecutionMonitor:
    max_events: int = 250
    _events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=250))
    _completed_at: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    _lock: RLock = field(default_factory=RLock)
    started_at: float | None = None
    total: int = 0
    completed: int = 0
    errors: int = 0
    current: str = "Aguardando"
    stage: str = "Sistema pronto"
    method: str = "-"
    status: str = "Aguardando"

    def reset(self, total: int = 0) -> None:
        with self._lock:
            self._events = deque(maxlen=self.max_events)
            self._completed_at = deque(maxlen=20)
            self.started_at = time.monotonic()
            self.total = max(int(total), 0)
            self.completed = 0
            self.errors = 0
            self.current = "Preparando..."
            self.stage = "Inicialização"
            self.method = "-"
            self.status = "Em andamento"
        self.event("INFO", "Execução iniciada")

    def event(self, level: str, message: str, **details: Any) -> None:
        with self._lock:
            self._events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": str(level).upper(),
                "message": str(message),
                "details": details,
            })

    def update(self, *, current: str | None = None, stage: str | None = None,
               method: str | None = None, status: str | None = None) -> None:
        with self._lock:
            if current is not None:
                self.current = str(current)
            if stage is not None:
                self.stage = str(stage)
            if method is not None:
                self.method = str(method)
            if status is not None:
                self.status = str(status)

    def complete(self, label: str, error: bool = False) -> None:
        with self._lock:
            now = time.monotonic()
            self.completed += 1
            if error:
                self.errors += 1
            self._completed_at.append(now)
            self.current = str(label)
        self.event("ERROR" if error else "OK", f"{label}: {'erro' if error else 'concluído'}")

    @property
    def progress(self) -> float:
        return min(self.completed / self.total, 1.0) if self.total else 0.0

    @property
    def speed_current(self) -> float:
        with self._lock:
            points = list(self._completed_at)
        if len(points) < 2:
            return 0.0
        elapsed = points[-1] - points[0]
        return ((len(points) - 1) / elapsed) * 60.0 if elapsed > 0 else 0.0

    @property
    def speed_average(self) -> float:
        if not self.started_at or self.completed <= 0:
            return 0.0
        elapsed = time.monotonic() - self.started_at
        return (self.completed / elapsed) * 60.0 if elapsed > 0 else 0.0

    @property
    def eta_seconds(self) -> float | None:
        speed = self.speed_average
        remaining = max(self.total - self.completed, 0)
        return (remaining / speed) * 60.0 if speed > 0 else None

    def recent_text(self, limit: int = 18) -> str:
        with self._lock:
            rows = list(self._events)[-limit:]
        return "\n".join(
            f"[{row['time']}] {row['level']:<7} {row['message']}"
            for row in rows
        ) or "Sistema pronto para iniciar."


def _format_eta(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "calculando"
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}min"
    if minutes:
        return f"{minutes}min {secs:02d}s"
    return f"{secs}s"


def render_gauge_html(monitor: ExecutionMonitor) -> str:
    speed = max(monitor.speed_current, 0.0)
    scale_max = max(6.0, float(math.ceil(max(speed, monitor.speed_average, 1.0) * 1.5)))
    ratio = min(speed / scale_max, 1.0)
    angle = -120.0 + 240.0 * ratio
    radians = math.radians(angle)
    center_x, center_y, radius = 150.0, 145.0, 92.0
    needle_x = center_x + radius * 0.78 * math.cos(radians)
    needle_y = center_y + radius * 0.78 * math.sin(radians)
    middle = scale_max / 2.0
    return f"""
<div class="live-gauge-wrap">
  <div class="live-gauge-title">VELOCIDADE AO VIVO</div>
  <svg viewBox="0 0 300 235" class="live-gauge" role="img" aria-label="Velocidade {speed:.2f} municípios por minuto">
    <path d="M 55 155 A 100 100 0 1 1 245 155" fill="none" stroke="#e5e7eb" stroke-width="20" stroke-linecap="round"/>
    <path d="M 55 155 A 100 100 0 0 1 102 70" fill="none" stroke="#ef4444" stroke-width="20" stroke-linecap="round"/>
    <path d="M 102 70 A 100 100 0 0 1 198 70" fill="none" stroke="#f59e0b" stroke-width="20"/>
    <path d="M 198 70 A 100 100 0 0 1 245 155" fill="none" stroke="#22c55e" stroke-width="20" stroke-linecap="round"/>
    <text x="45" y="185" class="gauge-mark">0</text>
    <text x="142" y="35" class="gauge-mark">{middle:.0f}</text>
    <text x="244" y="185" class="gauge-mark">{scale_max:.0f}</text>
    <line x1="{center_x}" y1="{center_y}" x2="{needle_x:.1f}" y2="{needle_y:.1f}" stroke="#111827" stroke-width="7" stroke-linecap="round"/>
    <circle cx="{center_x}" cy="{center_y}" r="13" fill="#111827"/>
    <circle cx="{center_x}" cy="{center_y}" r="5" fill="#ffffff"/>
    <text x="150" y="205" text-anchor="middle" class="gauge-value">{speed:.2f}</text>
    <text x="150" y="225" text-anchor="middle" class="gauge-unit">municípios/min</text>
  </svg>
  <div class="gauge-stats">
    <span>Média: <b>{monitor.speed_average:.2f}/min</b></span>
    <span>ETA: <b>{_format_eta(monitor.eta_seconds)}</b></span>
  </div>
</div>
"""
