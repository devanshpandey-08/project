"""Observability: Tracing and metrics."""
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib


@dataclass
class Span:
    """Represents a single trace span."""
    id: str
    name: str
    trace_id: str
    parent_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
    
    def end(self) -> None:
        self.end_time = datetime.now(timezone.utc)
    
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "status": self.status,
            "error_message": self.error_message
        }


@dataclass
class Tracer:
    """Distributed tracing with span management."""
    
    service_name: str = "flomind"
    spans: List[Span] = field(default_factory=list)
    active_spans: Dict[str, Span] = field(default_factory=dict)
    
    def start_span(self, name: str, parent: Optional[Span] = None, attributes: Optional[Dict[str, Any]] = None) -> Span:
        span_id = hashlib.md5(f"{datetime.now(timezone.utc)}:{name}".encode()).hexdigest()[:12]
        trace_id = parent.trace_id if parent else hashlib.md5(f"{datetime.now(timezone.utc)}".encode()).hexdigest()[:12]
        
        span = Span(
            id=span_id,
            name=name,
            trace_id=trace_id,
            parent_id=parent.id if parent else None,
            attributes=attributes or {}
        )
        
        self.spans.append(span)
        self.active_spans[span_id] = span
        
        return span
    
    def end_span(self, span: Span, status: str = "OK", error_message: Optional[str] = None) -> None:
        span.status = status
        span.error_message = error_message
        span.end()
        
        if span.id in self.active_spans:
            del self.active_spans[span.id]
    
    def get_trace(self, trace_id: str) -> List[Span]:
        return [s for s in self.spans if s.trace_id == trace_id]
    
    def get_all_traces(self) -> List[Dict[str, Any]]:
        traces: Dict[str, List[Span]] = {}
        
        for span in self.spans:
            if span.trace_id not in traces:
                traces[span.trace_id] = []
            traces[span.trace_id].append(span)
        
        return {tid: [s.to_dict() for s in spans] for tid, spans in traces.items()}


@dataclass
class MetricsCollector:
    """Metrics collection and aggregation."""
    
    counters: Dict[str, float] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    histograms: Dict[str, List[float]] = field(default_factory=dict)
    
    def increment(self, name: str, value: float = 1.0, **tags) -> None:
        key = f"{name}:" + ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
        self.counters[key] = self.counters.get(key, 0) + value
    
    def gauge(self, name: str, value: float, **tags) -> None:
        key = f"{name}:" + ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
        self.gauges[key] = value
    
    def histogram(self, name: str, value: float, **tags) -> None:
        key = f"{name}:" + ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def get_counter(self, name: str, **tags) -> float:
        key = f"{name}:" + ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return self.counters.get(key, 0)
    
    def get_histogram_stats(self, name: str, **tags) -> Dict[str, float]:
        key = f"{name}:" + ":".join(f"{k}={v}" for k, v in sorted(tags.items()))
        values = self.histograms.get(key, [])
        
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }
    
    def reset(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
