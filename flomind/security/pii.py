"""PII Detection and Redaction for compliance."""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"  # Social Security Number
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BANK_ACCOUNT = "bank_account"
    CUSTOM = "custom"


@dataclass
class PIIMatch:
    """Represents a detected PII instance."""
    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float = 1.0
    
    def redact(self, replacement: str = "[REDACTED]") -> str:
        """Get the redacted version."""
        return replacement


class PIIDetector:
    """
    Detect and redact Personally Identifiable Information (PII).
    
    Features:
    - Multiple PII type detection
    - Position tracking
    - Confidence scoring
    - Custom pattern support
    - GDPR/HIPAA compliance helpers
    """
    
    # Predefined regex patterns for common PII types
    PATTERNS = {
        PIIType.EMAIL: (
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            0.95
        ),
        PIIType.PHONE: (
            r'\b(?:\+?1[-.\s]?)?\(?(?:[0-9]{3})\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            0.90
        ),
        PIIType.SSN: (
            r'\b\d{3}-\d{2}-\d{4}\b',
            0.98
        ),
        PIIType.CREDIT_CARD: (
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            0.92
        ),
        PIIType.IP_ADDRESS: (
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            0.85
        ),
        PIIType.DATE_OF_BIRTH: (
            r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b',
            0.80
        ),
    }
    
    def __init__(self, custom_patterns: Optional[Dict[str, Tuple[str, float]]] = None):
        """
        Initialize PII detector.
        
        Args:
            custom_patterns: Dict of {name: (regex_pattern, confidence)}
        """
        self.patterns = dict(self.PATTERNS)
        self.compiled_patterns: Dict[PIIType, re.Pattern] = {}
        
        # Compile built-in patterns
        for pii_type, (pattern, confidence) in self.patterns.items():
            self.compiled_patterns[pii_type] = re.compile(pattern, re.IGNORECASE)
            
        # Add custom patterns
        if custom_patterns:
            for name, (pattern, confidence) in custom_patterns.items():
                enum_name = PIIType.CUSTOM
                self.patterns[enum_name] = (pattern, confidence)
                self.compiled_patterns[enum_name] = re.compile(pattern, re.IGNORECASE)
                
    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect all PII in text.
        
        Returns:
            List of PIIMatch objects with positions and types
        """
        matches = []
        
        for pii_type, pattern in self.compiled_patterns.items():
            for match in pattern.finditer(text):
                piimatch = PIIMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=self.patterns.get(pii_type, ("", 1.0))[1]
                )
                matches.append(piimatch)
                
        # Sort by position
        matches.sort(key=lambda m: m.start)
        
        return matches
        
    def redact(
        self,
        text: str,
        pii_types: Optional[List[PIIType]] = None,
        replacement: str = "[REDACTED]"
    ) -> str:
        """
        Redact PII from text.
        
        Args:
            text: Input text
            pii_types: Specific PII types to redact (None = all)
            replacement: Replacement string
            
        Returns:
            Text with PII redacted
        """
        matches = self.detect(text)
        
        if pii_types:
            matches = [m for m in matches if m.pii_type in pii_types]
            
        if not matches:
            return text
            
        # Redact from end to start to preserve positions
        result = text
        for match in reversed(matches):
            result = result[:match.start] + replacement + result[match.end:]
            
        return result
        
    def get_pii_summary(self, text: str) -> Dict[str, int]:
        """Get count of each PII type found."""
        matches = self.detect(text)
        summary = {}
        
        for match in matches:
            type_name = match.pii_type.value
            summary[type_name] = summary.get(type_name, 0) + 1
            
        return summary
        
    def contains_pii(self, text: str, pii_types: Optional[List[PIIType]] = None) -> bool:
        """Check if text contains any PII."""
        matches = self.detect(text)
        
        if pii_types:
            return any(m.pii_type in pii_types for m in matches)
            
        return len(matches) > 0
        
    def mask_partial(
        self,
        text: str,
        show_chars: int = 2,
        pii_types: Optional[List[PIIType]] = None
    ) -> str:
        """
        Mask PII partially (show first/last few chars).
        
        Example: john.doe@example.com -> jo***@example.com
        """
        matches = self.detect(text)
        
        if pii_types:
            matches = [m for m in matches if m.pii_type in pii_types]
            
        if not matches:
            return text
            
        result = text
        for match in reversed(matches):
            value = match.value
            if len(value) <= show_chars * 2:
                masked = "*" * len(value)
            else:
                masked = value[:show_chars] + "*" * (len(value) - show_chars * 2) + value[-show_chars:]
            result = result[:match.start] + masked + result[match.end:]
            
        return result
