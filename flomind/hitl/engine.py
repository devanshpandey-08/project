"""Human-in-the-Loop engine for approvals and interruptions."""
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
import hashlib

from flomind.core.state import FlowState


class ApprovalStatus(Enum):
    PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()
    EXPIRED = auto()


class ApprovalPattern(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    MAJORITY = "majority"
    UNANIMOUS = "unanimous"


@dataclass
class HumanInterrupt:
    """Represents a human interruption point."""
    
    id: str
    flow_id: str
    node_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: Optional[datetime] = None
    approver_id: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[float] = None
    pattern: ApprovalPattern = ApprovalPattern.REQUIRED
    
    def is_expired(self) -> bool:
        if self.timeout_seconds is None:
            return False
        
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.timeout_seconds
    
    def approve(self, approver_id: str, response_data: Optional[Dict[str, Any]] = None) -> bool:
        if self.status != ApprovalStatus.PENDING:
            return False
        
        if self.is_expired():
            self.status = ApprovalStatus.EXPIRED
            return False
        
        self.status = ApprovalStatus.APPROVED
        self.approver_id = approver_id
        self.responded_at = datetime.now(timezone.utc)
        self.response_data = response_data or {}
        return True
    
    def reject(self, approver_id: str, reason: str = "") -> bool:
        if self.status != ApprovalStatus.PENDING:
            return False
        
        if self.is_expired():
            self.status = ApprovalStatus.EXPIRED
            return False
        
        self.status = ApprovalStatus.REJECTED
        self.approver_id = approver_id
        self.responded_at = datetime.now(timezone.utc)
        self.response_data = {"reason": reason}
        return True


@dataclass
class HITLEngine:
    """Human-in-the-Loop engine for managing interruptions."""
    
    interrupts: Dict[str, HumanInterrupt] = field(default_factory=dict)
    wait_handles: Dict[str, asyncio.Event] = field(default_factory=dict)
    
    def create_interrupt(
        self,
        flow_id: str,
        node_id: str,
        timeout_seconds: Optional[float] = None,
        pattern: ApprovalPattern = ApprovalPattern.REQUIRED
    ) -> HumanInterrupt:
        interrupt_id = hashlib.md5(f"{flow_id}:{node_id}:{datetime.now(timezone.utc)}".encode()).hexdigest()[:12]
        
        interrupt = HumanInterrupt(
            id=interrupt_id,
            flow_id=flow_id,
            node_id=node_id,
            timeout_seconds=timeout_seconds,
            pattern=pattern
        )
        
        self.interrupts[interrupt_id] = interrupt
        self.wait_handles[interrupt_id] = asyncio.Event()
        
        return interrupt
    
    async def wait_for_approval(self, interrupt_id: str, timeout: Optional[float] = None) -> bool:
        if interrupt_id not in self.wait_handles:
            raise ValueError(f"Interrupt {interrupt_id} not found")
        
        event = self.wait_handles[interrupt_id]
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        
        interrupt = self.interrupts.get(interrupt_id)
        return interrupt and interrupt.status == ApprovalStatus.APPROVED
    
    def approve(self, interrupt_id: str, approver_id: str, response_data: Optional[Dict[str, Any]] = None) -> bool:
        if interrupt_id not in self.interrupts:
            return False
        
        interrupt = self.interrupts[interrupt_id]
        success = interrupt.approve(approver_id, response_data)
        
        if success and interrupt_id in self.wait_handles:
            self.wait_handles[interrupt_id].set()
        
        return success
    
    def reject(self, interrupt_id: str, approver_id: str, reason: str = "") -> bool:
        if interrupt_id not in self.interrupts:
            return False
        
        interrupt = self.interrupts[interrupt_id]
        success = interrupt.reject(approver_id, reason)
        
        if success and interrupt_id in self.wait_handles:
            self.wait_handles[interrupt_id].set()
        
        return success
    
    def get_interrupt(self, interrupt_id: str) -> Optional[HumanInterrupt]:
        return self.interrupts.get(interrupt_id)
    
    def get_pending_interrupts(self, flow_id: Optional[str] = None) -> List[HumanInterrupt]:
        interrupts = [
            interrupt for interrupt in self.interrupts.values()
            if interrupt.status == ApprovalStatus.PENDING
        ]
        
        if flow_id:
            interrupts = [i for i in interrupts if i.flow_id == flow_id]
        
        return interrupts
    
    def cleanup_expired(self) -> int:
        expired_ids = [
            interrupt_id for interrupt_id, interrupt in self.interrupts.items()
            if interrupt.is_expired() and interrupt.status == ApprovalStatus.PENDING
        ]
        
        for interrupt_id in expired_ids:
            interrupt = self.interrupts[interrupt_id]
            interrupt.status = ApprovalStatus.EXPIRED
            
            if interrupt_id in self.wait_handles:
                self.wait_handles[interrupt_id].set()
        
        return len(expired_ids)
