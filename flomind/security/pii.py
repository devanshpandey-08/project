"""PII detection and redaction for compliance."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RedactionLevel(Enum):
    """Level of PII redaction."""
    FULL = "full"  # Replace entire value
    PARTIAL = "partial"  # Show last 4 chars
    MASKED = "masked"  # Replace with [REDACTED]
    HASHED = "hashed"  # Replace with hash


@dataclass
class PIIMatch:
    """A detected PII match."""
    type: str
    value: str
    start: int
    end: int
    confidence: float


class PIIDetector:
    """
    Detect and redact Personally Identifiable Information (PII).
    
    Supports detection of:
    - Email addresses
    - Phone numbers (various formats)
    - Social Security Numbers (SSN)
    - Credit card numbers
    - IP addresses
    - URLs with query parameters
    
    Usage:
        detector = PIIDetector()
        result = detector.detect("Contact john@example.com or call 555-123-4567")
        redacted = detector.redact(result.text, level=RedactionLevel.PARTIAL)
    """
    
    def __init__(self):
        self.patterns: Dict[str, Tuple[re.Pattern, float]] = {
            "email": (
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                0.95
            ),
            "phone_us": (
                re.compile(r'\b(?:\+?1[-.\s]?)?\(?(?:[0-9]{3})\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
                0.90
            ),
            "ssn": (
                re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
                0.98
            ),
            "credit_card": (
                re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
                0.92
            ),
            "ip_address": (
                re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
                0.85
            ),
            "url_with_params": (
                re.compile(r'https?://[^\s]+\?[^\s]+'),
                0.80
            ),
        }
        
        # Additional patterns for international support can be added
    
    def detect(self, text: str) -> List[PIIMatch]:
        """Detect all PII in text."""
        matches: List[PIIMatch] = []
        
        for pii_type, (pattern, confidence) in self.patterns.items():
            for match in pattern.finditer(text):
                matches.append(PIIMatch(
                    type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                ))
        
        # Sort by position
        matches.sort(key=lambda m: m.start)
        
        return matches
    
    def redact(
        self,
        text: str,
        level: RedactionLevel = RedactionLevel.FULL,
        types: Optional[List[str]] = None,
        min_confidence: float = 0.8,
    ) -> str:
        """
        Redact PII from text.
        
        Args:
            text: Input text
            level: Redaction level
            types: Specific PII types to redact (None = all)
            min_confidence: Minimum confidence threshold
        
        Returns:
            Redacted text
        """
        matches = self.detect(text)
        
        if not matches:
            return text
        
        # Filter matches
        filtered = [
            m for m in matches
            if m.confidence >= min_confidence
            and (types is None or m.type in types)
        ]
        
        if not filtered:
            return text
        
        # Build redacted string
        result = []
        last_end = 0
        
        for match in filtered:
            # Add text before this match
            result.append(text[last_end:match.start])
            
            # Add redacted version
            redacted = self._redact_value(match.value, level, match.type)
            result.append(redacted)
            
            last_end = match.end
        
        # Add remaining text
        result.append(text[last_end:])
        
        return ''.join(result)
    
    def _redact_value(self, value: str, level: RedactionLevel, pii_type: str) -> str:
        """Redact a single value based on level."""
        if level == RedactionLevel.MASKED:
            return "[REDACTED]"
        
        elif level == RedactionLevel.HASHED:
            import hashlib
            return f"[HASH:{hashlib.sha256(value.encode()).hexdigest()[:16]}]"
        
        elif level == RedactionLevel.PARTIAL:
            if len(value) <= 4:
                return "[REDACTED]"
            return "*" * (len(value) - 4) + value[-4:]
        
        else:  # FULL
            return f"[{pii_type.upper()}]"
    
    def get_stats(self, text: str) -> Dict[str, Any]:
        """Get statistics about PII in text."""
        matches = self.detect(text)
        
        stats = {
            "total_matches": len(matches),
            "by_type": {},
            "high_confidence": 0,
        }
        
        for match in matches:
            stats["by_type"][match.type] = stats["by_type"].get(match.type, 0) + 1
            if match.confidence >= 0.9:
                stats["high_confidence"] += 1
        
        return stats
    
    def add_pattern(
        self,
        name: str,
        pattern: str,
        confidence: float = 0.8,
    ) -> "PIIDetector":
        """Add a custom PII pattern."""
        self.patterns[name] = (re.compile(pattern), confidence)
        return self
