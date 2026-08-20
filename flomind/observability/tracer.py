"""Observability - Tracing and Metrics."""

import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager
import threading


@dataclass
class Span:
    """Represents a span in distributed tracing."""
    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "OK"  # OK, ERROR
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent_span_id: Optional[str] = None
    
    def duration(self) -> Optional[float]:
        """Get span duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": (self.duration() or 0) * 1000,
            "status": self.status,
            "attributes": self.attributes
        }


class Tracer:
    """
    Distributed tracing for FlowMind.
    
    Features:
    - Hierarchical spans
    - Context propagation
    - Export compatibility (Jaeger, Zipkin)
    """
    
    def __init__(self, service_name: str = "flomind"):
        self.service_name = service_name
        self._spans: List[Span] = []
        self._active_spans: Dict[str, Span] = {}
        self._lock = threading.Lock()
        
    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        **attributes
    ) -> Span:
        """Start a new span."""
        with self._lock:
            span = Span(
                trace_id=trace_id or str(uuid.uuid4()),
                span_id=str(uuid.uuid4())[:16],
                name=name,
                start_time=time.time(),
                attributes=attributes,
                parent_span_id=parent_span_id
            )
            self._spans.append(span)
            self._active_spans[span.span_id] = span
            return span
            
    def end_span(self, span: Span, status: str = "OK") -> None:
        """End a span."""
        with self._lock:
            span.end_time = time.time()
            span.status = status
            if span.span_id in self._active_spans:
                del self._active_spans[span.span_id]
                
    @contextmanager
    def trace(self, name: str, **attributes):
        """Context manager for tracing."""
        span = self.start_span(name, **attributes)
        try:
            yield span
            self.end_span(span, "OK")
        except Exception as e:
            span.attributes["error"] = str(e)
            self.end_span(span, "ERROR")
            raise
            
    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        return [s for s in self._spans if s.trace_id == trace_id]
        
    def export(self) -> List[Dict[str, Any]]:
        """Export all completed spans."""
        return [s.to_dict() for s in self._spans if s.end_time is not None]
        
    def clear(self) -> None:
        """Clear all spans."""
        self._spans.clear()
        self._active_spans.clear()


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Metrics collection for FlowMind.
    
    Features:
    - Counter, Gauge, Histogram metrics
    - Tag-based filtering
    - Export to Prometheus format
    """
    
    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._points: List[MetricPoint] = []
        self._lock = threading.Lock()
        
    def increment(self, name: str, value: float = 1.0, **tags) -> None:
        """Increment a counter."""
        with self._lock:
            key = self._make_key(name, tags)
            self._counters[key] = self._counters.get(key, 0) + value
            self._points.append(MetricPoint(name, value, time.time(), tags))
            
    def gauge(self, name: str, value: float, **tags) -> None:
        """Set a gauge value."""
        with self._lock:
            key = self._make_key(name, tags)
            self._gauges[key] = value
            self._points.append(MetricPoint(name, value, time.time(), tags))
            
    def histogram(self, name: str, value: float, **tags) -> None:
        """Record a histogram value."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            self._points.append(MetricPoint(name, value, time.time(), tags))
            
    def _make_key(self, name: str, tags: Dict[str, str]) -> str:
        """Create unique key from name and tags."""
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}" if tag_str else name
        
    def get_counter(self, name: str, **tags) -> float:
        """Get counter value."""
        key = self._make_key(name, tags)
        return self._counters.get(key, 0.0)
        
    def get_gauge(self, name: str, **tags) -> Optional[float]:
        """Get gauge value."""
        key = self._make_key(name, tags)
        return self._gauges.get(key)
        
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics."""
        values = self._histograms.get(name, [])
        if not values:
            return {}
            
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }
        
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for key, value in self._counters.items():
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{key} {value}")
            
        for key, value in self._gauges.items():
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{key} {value}")
            
        return "\n".join(lines)
        
    def clear(self) -> None:
        """Clear all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._points.clear()
