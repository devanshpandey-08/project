"""
Observability system for FlowMind.

Provides tracing, metrics, and monitoring capabilities.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import time
import uuid


@dataclass
class Span:
    """A span in a trace."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    name: str = ""
    kind: str = "operation"  # operation, llm, tool, agent
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok, error
    error: Optional[str] = None
    parent_id: Optional[str] = None
    
    def end(self) -> None:
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'kind': self.kind,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms,
            'attributes': self.attributes,
            'status': self.status,
            'error': self.error,
            'parent_id': self.parent_id,
        }


@dataclass
class Trace:
    """A complete trace of an operation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_span(self, span: Span) -> None:
        self.spans.append(span)
    
    def end(self) -> None:
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    @property
    def total_tokens(self) -> int:
        return sum(s.attributes.get('tokens', 0) for s in self.spans)
    
    @property
    def total_cost(self) -> float:
        return sum(s.attributes.get('cost', 0.0) for s in self.spans)


class Tracer:
    """
    Distributed tracer for flow execution.
    
    Provides OpenTelemetry-compatible tracing.
    """
    
    def __init__(self, service_name: str = "flowmind"):
        self.service_name = service_name
        self._active_traces: Dict[str, Trace] = {}
        self._completed_traces: List[Trace] = []
        self._exporters: List[callable] = []
    
    def start_trace(self, name: str, **metadata) -> Trace:
        """Start a new trace."""
        trace = Trace(name=name, metadata=metadata)
        self._active_traces[trace.id] = trace
        return trace
    
    def end_trace(self, trace_id: str) -> Optional[Trace]:
        """End a trace."""
        if trace_id in self._active_traces:
            trace = self._active_traces.pop(trace_id)
            trace.end()
            self._completed_traces.append(trace)
            
            # Export
            for exporter in self._exporters:
                try:
                    exporter(trace)
                except Exception:
                    pass
            
            return trace
        return None
    
    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        kind: str = "operation"
    ) -> Span:
        """Start a new span."""
        span = Span(name=name, kind=kind, parent_id=parent_id)
        
        if trace_id and trace_id in self._active_traces:
            self._active_traces[trace_id].add_span(span)
        
        return span
    
    def add_exporter(self, exporter: callable) -> None:
        """Add a trace exporter."""
        self._exporters.append(exporter)
    
    def get_completed_traces(self) -> List[Trace]:
        """Get all completed traces."""
        return self._completed_traces.copy()
    
    def clear(self) -> None:
        """Clear all traces."""
        self._active_traces.clear()
        self._completed_traces.clear()


@dataclass
class Metrics:
    """Metrics collector for flows."""
    
    _counters: Dict[str, int] = field(default_factory=dict)
    _gauges: Dict[str, float] = field(default_factory=dict)
    _histograms: Dict[str, List[float]] = field(default_factory=dict)
    
    def inc(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def set(self, name: str, value: float) -> None:
        """Set a gauge."""
        self._gauges[name] = value
    
    def observe(self, name: str, value: float) -> None:
        """Record a histogram observation."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
    
    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)
    
    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)
    
    def get_histogram(self, name: str) -> Dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {'count': 0, 'sum': 0, 'avg': 0, 'min': 0, 'max': 0}
        
        return {
            'count': len(values),
            'sum': sum(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
        }
    
    def get_all(self) -> Dict[str, Any]:
        return {
            'counters': self._counters.copy(),
            'gauges': self._gauges.copy(),
            'histograms': {k: self.get_histogram(k) for k in self._histograms},
        }
    
    def clear(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


@dataclass
class ObservabilityConfig:
    """Configuration for observability."""
    enabled: bool = True
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    log_level: str = "info"
    export_interval_seconds: float = 60.0
    max_traces: int = 1000
