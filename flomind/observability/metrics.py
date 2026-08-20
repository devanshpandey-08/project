"""
FlowMind Observability - Metrics Collector

Aggregate metrics collection for monitoring and alerting.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from datetime import datetime


@dataclass
class MetricsCollector:
    """
    Collects aggregate metrics across all flow executions.
    
    Unlike per-trace data, this gives you:
    - Average latency trends
    - Error rates over time
    - Token usage patterns
    - Cost analysis
    """
    
    execution_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    latency_histogram: Dict[str, List[float]] = field(default_factory=dict)
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    def record_execution(self, trace):
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
            kind = span.kind
            if kind not in self.latency_histogram:
                self.latency_histogram[kind] = []
            self.latency_histogram[kind].append(span.latency_ms)
            
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
