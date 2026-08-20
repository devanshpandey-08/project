"""Input sanitization for XSS and injection prevention."""

import re
import html
from typing import Optional, List


class InputSanitizer:
    """
    Sanitize user inputs to prevent security vulnerabilities.
    
    Features:
    - XSS prevention (script tag removal)
    - HTML entity encoding
    - SQL injection pattern detection
    - Null byte removal
    - Length limiting
    - Special character escaping
    """
    
    # Dangerous patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<svg[^>]*onload',
        r'expression\s*\(',
        r'url\s*\(\s*["\']?javascript:',
    ]
    
    SQL_INJECTION_PATTERNS = [
        r"'\s*OR\s+'1'\s*=\s*'1",
        r';\s*DROP\s+TABLE',
        r'--\s*$',
        r';\s*DELETE\s+FROM',
        r';\s*UPDATE\s+.*\s+SET',
        r'UNION\s+SELECT',
    ]
    
    def __init__(
        self,
        max_length: int = 10000,
        allow_html: bool = False,
        strip_null_bytes: bool = True
    ):
        """
        Initialize sanitizer.
        
        Args:
            max_length: Maximum allowed input length
            allow_html: Whether to allow HTML tags (will be escaped if False)
            strip_null_bytes: Remove null bytes from input
        """
        self.max_length = max_length
        self.allow_html = allow_html
        self.strip_null_bytes = strip_null_bytes
        
        # Compile patterns
        self.xss_regexes = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.XSS_PATTERNS]
        self.sql_regexes = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        
    def sanitize(self, text: str) -> str:
        """
        Fully sanitize input text.
        
        Steps:
        1. Remove null bytes
        2. Truncate to max length
        3. Remove XSS patterns
        4. Escape HTML entities (if not allowing HTML)
        5. Trim whitespace
        
        Returns:
            Sanitized string
        """
        if not isinstance(text, str):
            text = str(text)
            
        # Remove null bytes
        if self.strip_null_bytes:
            text = text.replace('\x00', '')
            
        # Truncate
        if len(text) > self.max_length:
            text = text[:self.max_length]
            
        # Remove XSS patterns
        for regex in self.xss_regexes:
            text = regex.sub('', text)
            
        # Escape HTML if not allowed
        if not self.allow_html:
            text = html.escape(text)
            
        # Trim
        text = text.strip()
        
        return text
        
    def detect_xss(self, text: str) -> List[str]:
        """Detect potential XSS patterns in text."""
        detected = []
        
        for i, regex in enumerate(self.xss_regexes):
            if regex.search(text):
                detected.append(f"XSS_PATTERN_{i}")
                
        return detected
        
    def detect_sql_injection(self, text: str) -> List[str]:
        """Detect potential SQL injection patterns."""
        detected = []
        
        for i, regex in enumerate(self.sql_regexes):
            if regex.search(text):
                detected.append(f"SQL_INJECTION_PATTERN_{i}")
                
        return detected
        
    def is_safe(self, text: str) -> bool:
        """Check if input is safe (no dangerous patterns)."""
        return not (self.detect_xss(text) or self.detect_sql_injection(text))
        
    def sanitize_for_json(self, text: str) -> str:
        """Sanitize text for safe inclusion in JSON."""
        # Escape special JSON characters
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        
        # Remove control characters
        text = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
        
        return text
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for safe storage."""
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove null bytes and control chars
        filename = ''.join(c for c in filename if ord(c) >= 32)
        
        # Remove leading dots
        while filename.startswith('.'):
            filename = filename[1:]
            
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250-len(ext)] + '.' + ext if ext else filename[:255]
            
        return filename or "unnamed_file"
        
    def sanitize_url(self, url: str) -> Optional[str]:
        """Sanitize and validate a URL."""
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
        # Sanitize first
        url = url.strip()
        url = url.replace('\x00', '')
        
        # Validate
        if url_pattern.match(url):
            # Check for javascript: protocol
            if not url.lower().startswith('javascript:'):
                return url
                
        return None
