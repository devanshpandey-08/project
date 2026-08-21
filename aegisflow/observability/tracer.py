import time
from typing import Dict, List
class TraceSpan:
    def __init__(self, name: str, trace_id: str):
        self.name, self.trace_id = name, trace_id
        self.start_time = time.time()
        self.end_time = None
        self.attributes = {}
    def set_attribute(self, key: str, value: any): self.attributes[key] = value
    def end(self): self.end_time = time.time()
class Tracer:
    def __init__(self): self.spans: List[TraceSpan] = []
    def start_span(self, name: str, trace_id: str) -> TraceSpan:
        span = TraceSpan(name, trace_id)
        self.spans.append(span)
        return span
