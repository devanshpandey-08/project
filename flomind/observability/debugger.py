"""
FlowMind Observability - Flow Debugger

Debug flows with state replay, step-through execution, and detailed inspection.
This is the key differentiator for developer experience.
"""

from typing import Any, Dict, List, Optional
import json


class FlowDebugger:
    """
    Debug flows with powerful inspection capabilities.
    
    Key Features:
    - State replay at any point in execution
    - Node-by-node inspection
    - Latency analysis
    - Error root cause analysis
    """
    
    def __init__(self):
        self.traces = {}
    
    def attach_trace(self, trace):
        """Attach a trace for debugging."""
        self.traces[trace.trace_id] = trace
    
    def get_state_at_node(self, trace_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Get the state at a specific node execution."""
        trace = self.traces.get(trace_id)
        if not trace:
            return None
        
        # Find the span for this node
        for span in trace.spans:
            if span.name == node_id:
                return {
                    "input": span.input_data,
                    "output": span.output_data,
                    "latency_ms": span.latency_ms,
                    "success": span.status == "success"
                }
        
        return None
    
    def get_execution_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get timeline of all node executions."""
        trace = self.traces.get(trace_id)
        if not trace:
            return []
        
        timeline = []
        for span in sorted(trace.spans, key=lambda s: s.start_time):
            timeline.append({
                "node": span.name,
                "type": span.kind,
                "start": span.start_time.isoformat(),
                "duration_ms": span.latency_ms,
                "status": span.status,
                "error": span.error_message
            })
        
        return timeline
    
    def find_bottleneck(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Find the slowest node in a trace."""
        trace = self.traces.get(trace_id)
        if not trace or not trace.spans:
            return None
        
        slowest = max(trace.spans, key=lambda s: s.latency_ms)
        return {
            "node": slowest.name,
            "latency_ms": slowest.latency_ms,
            "percentage": (slowest.latency_ms / sum(s.latency_ms for s in trace.spans)) * 100
        }
    
    def get_error_chain(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get the chain of errors leading to failure."""
        trace = self.traces.get(trace_id)
        if not trace:
            return []
        
        errors = []
        for span in trace.spans:
            if span.status == "error":
                errors.append({
                    "node": span.name,
                    "error": span.error_message,
                    "input_sample": json.dumps(span.input_data, default=str)[:200] if span.input_data else None
                })
        
        return errors
    
    def generate_debug_report(self, trace_id: str) -> str:
        """Generate a comprehensive debug report."""
        trace = self.traces.get(trace_id)
        if not trace:
            return f"Trace {trace_id} not found"
        
        return trace.debug_report()
