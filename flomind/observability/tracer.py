"""
FlowMind Observability - The Real Differentiator

This is why developers choose FlowMind over LangChain/LangGraph:
1. When a 10-node flow fails at step 7, see exactly what happened at steps 1-6
2. Trace token usage and cost per node
3. Debug with full state replay
4. Understand latency breakdown (LLM vs network vs computation)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """
    A span represents a single operation within a trace.
    
    Unlike basic logging, spans give you:
    - Hierarchical structure (parent/child)
    - Timing information (start, end, duration)
    - Context (tags, metadata)
    - Error tracking
    """
    trace_id: str
    span_id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    parent_span_id: Optional[str] = None
    
    # Operation details
    kind: str = "node"  # node, llm, tool, memory, etc.
    status: str = "running"  # running, success, error
    error_message: Optional[str] = None
    
    # Metrics
    latency_ms: float = 0.0
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    
    # Context for debugging
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Input/Output for replay (optional, can be disabled for privacy)
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Any] = None
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """Mark the span as complete."""
        self.end_time = datetime.utcnow()
        self.status = "success" if success else "error"
        self.error_message = error
        if self.start_time and self.end_time:
            self.latency_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage/export."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "error_message": self.error_message,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    def debug_string(self) -> str:
        """Human-readable format for debugging."""
        status_icon = "✅" if self.status == "success" else "❌" if self.status == "error" else "⏳"
        lines = [
            f"{status_icon} {self.name} ({self.kind})",
            f"   Trace: {self.trace_id}",
            f"   Duration: {self.latency_ms:.2f}ms",
        ]
        
        if self.tokens_used:
            lines.append(f"   Tokens: {self.tokens_used}")
        if self.cost_usd:
            lines.append(f"   Cost: ${self.cost_usd:.4f}")
        if self.error_message:
            lines.append(f"   Error: {self.error_message}")
        
        return "\n".join(lines)


@dataclass
class Trace:
    """A complete trace containing all spans for a flow execution."""
    trace_id: str
    flow_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    spans: List[Span] = field(default_factory=list)
    status: str = "running"
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    
    def add_span(self, span: Span):
        """Add a span to the trace."""
        self.spans.append(span)
    
    def finish(self):
        """Mark the trace as complete."""
        self.end_time = datetime.utcnow()
        self.status = "success" if all(s.status == "success" for s in self.spans) else "error"
        self.total_tokens = sum(s.tokens_used or 0 for s in self.spans)
        self.total_cost_usd = sum(s.cost_usd or 0.0 for s in self.spans)
    
    def get_failed_spans(self) -> List[Span]:
        """Get all failed spans for debugging."""
        return [s for s in self.spans if s.status == "error"]
    
    def get_latency_breakdown(self) -> Dict[str, float]:
        """Break down latency by operation type."""
        breakdown = {}
        for span in self.spans:
            kind = span.kind
            breakdown[kind] = breakdown.get(kind, 0) + span.latency_ms
        return breakdown
    
    def debug_report(self) -> str:
        """Generate a comprehensive debug report."""
        lines = [
            "=" * 60,
            f"FLOW TRACE REPORT: {self.flow_name}",
            "=" * 60,
            f"Trace ID: {self.trace_id}",
            f"Status: {'✅ Success' if self.status == 'success' else '❌ Failed'}",
            f"Duration: {(self.end_time - self.start_time).total_seconds()*1000:.2f}ms" if self.end_time else "Running...",
            f"Total Nodes: {len(self.spans)}",
            f"Total Tokens: {self.total_tokens}",
            f"Total Cost: ${self.total_cost_usd:.4f}",
            "",
        ]
        
        # Latency breakdown
        breakdown = self.get_latency_breakdown()
        if breakdown:
            lines.append("LATENCY BREAKDOWN:")
            for kind, latency in sorted(breakdown.items(), key=lambda x: -x[1]):
                pct = (latency / sum(breakdown.values()) * 100) if breakdown else 0
                lines.append(f"  {kind}: {latency:.2f}ms ({pct:.1f}%)")
            lines.append("")
        
        # Node-by-node details
        lines.append("EXECUTION DETAILS:")
        for i, span in enumerate(self.spans, 1):
            status_icon = "✅" if span.status == "success" else "❌"
            lines.append(f"  {i}. {status_icon} {span.name}")
            lines.append(f"      Type: {span.kind}, Duration: {span.latency_ms:.2f}ms")
            if span.tokens_used:
                lines.append(f"      Tokens: {span.tokens_used}")
            if span.error_message:
                lines.append(f"      ERROR: {span.error_message}")
        
        # Failed nodes section
        failed = self.get_failed_spans()
        if failed:
            lines.append("")
            lines.append("❌ FAILED NODES (for debugging):")
            for span in failed:
                lines.append(f"  - {span.name}: {span.error_message}")
                if span.input_data:
                    lines.append(f"    Input: {json.dumps(span.input_data, default=str)[:200]}...")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class FlowTracer:
    """
    Manages traces and spans for flow execution.
    
    Key Features:
    - Automatic trace context propagation
    - Hierarchical span structure
    - Real-time span collection
    - Export capabilities (JSON, console, external systems)
    """
    
    def __init__(self, export_callback=None):
        self.traces: Dict[str, Trace] = {}
        self.export_callback = export_callback  # Called when trace completes
        self._active_spans: Dict[str, Span] = {}
    
    def start_trace(self, flow_name: str, trace_id: Optional[str] = None) -> Trace:
        """Start a new trace for a flow execution."""
        trace_id = trace_id or str(uuid.uuid4())
        trace = Trace(
            trace_id=trace_id,
            flow_name=flow_name,
            start_time=datetime.utcnow()
        )
        self.traces[trace_id] = trace
        logger.info(f"Started trace {trace_id} for flow {flow_name}")
        return trace
    
    def start_span(self, trace_id: str, name: str, 
                   kind: str = "node",
                   parent_span_id: Optional[str] = None,
                   input_data: Optional[Dict[str, Any]] = None,
                   tags: Optional[Dict[str, str]] = None) -> Span:
        """Start a new span within a trace."""
        if trace_id not in self.traces:
            raise ValueError(f"Trace {trace_id} not found")
        
        span = Span(
            trace_id=trace_id,
            span_id=str(uuid.uuid4()),
            name=name,
            start_time=datetime.utcnow(),
            parent_span_id=parent_span_id,
            kind=kind,
            input_data=input_data,
            tags=tags or {}
        )
        
        self.traces[trace_id].add_span(span)
        self._active_spans[span.span_id] = span
        
        return span
    
    def finish_span(self, span_id: str, success: bool = True,
                    error: Optional[str] = None,
                    output_data: Optional[Any] = None,
                    tokens_used: Optional[int] = None,
                    cost_usd: Optional[float] = None):
        """Finish a span with results."""
        if span_id not in self._active_spans:
            raise ValueError(f"Span {span_id} not found")
        
        span = self._active_spans[span_id]
        span.finish(success=success, error=error)
        span.output_data = output_data
        span.tokens_used = tokens_used
        span.cost_usd = cost_usd
        
        del self._active_spans[span_id]
        
        logger.debug(f"Finished span {span.name}: {'success' if success else 'error'}")
    
    def finish_trace(self, trace_id: str):
        """Finish a trace and optionally export it."""
        if trace_id not in self.traces:
            raise ValueError(f"Trace {trace_id} not found")
        
        trace = self.traces[trace_id]
        trace.finish()
        
        logger.info(f"Finished trace {trace_id}: {trace.status}")
        
        # Export if callback provided
        if self.export_callback:
            self.export_callback(trace)
        
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        return self.traces.get(trace_id)
    
    def get_all_traces(self) -> List[Trace]:
        """Get all traces."""
        return list(self.traces.values())
    
    def export_trace_json(self, trace_id: str) -> str:
        """Export a trace as JSON for external tools."""
        trace = self.get_trace(trace_id)
        if not trace:
            raise ValueError(f"Trace {trace_id} not found")
        
        return json.dumps({
            "trace_id": trace.trace_id,
            "flow_name": trace.flow_name,
            "start_time": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "status": trace.status,
            "total_tokens": trace.total_tokens,
            "total_cost_usd": trace.total_cost_usd,
            "spans": [s.to_dict() for s in trace.spans]
        }, indent=2)


class MetricsCollector:
    """
    Collects aggregate metrics across all flows.
    
    Unlike per-trace data, this gives you:
    - Average latency trends
    - Error rates over time
    - Token usage patterns
    - Cost analysis
    """
    
    def __init__(self):
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.latency_histogram: Dict[str, List[float]] = {}  # node_type -> latencies
        self.error_counts: Dict[str, int] = {}  # error_type -> count
    
    def record_execution(self, trace: Trace):
        """Record metrics from a completed trace."""
        self.execution_count += 1
        
        if trace.status == "success":
            self.success_count += 1
        else:
            self.error_count += 1
        
        if trace.end_time:
            duration = (trace.end_time - trace.start_time).total_seconds() * 1000
            self.total_latency_ms += duration
        
        self.total_tokens += trace.total_tokens
        self.total_cost_usd += trace.total_cost_usd
        
        # Per-node-type metrics
        for span in trace.spans:
            if span.kind not in self.latency_histogram:
                self.latency_histogram[span.kind] = []
            self.latency_histogram[span.kind].append(span.latency_ms)
            
            if span.status == "error" and span.error_message:
                error_type = type(span.error_message).__name__
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get aggregate metrics summary."""
        avg_latency = self.total_latency_ms / self.execution_count if self.execution_count > 0 else 0
        success_rate = self.success_count / self.execution_count if self.execution_count > 0 else 0
        
        return {
            "total_executions": self.execution_count,
            "success_rate": f"{success_rate*100:.2f}%",
            "avg_latency_ms": f"{avg_latency:.2f}",
            "total_tokens": self.total_tokens,
            "total_cost_usd": f"${self.total_cost_usd:.4f}",
            "error_breakdown": self.error_counts,
        }
