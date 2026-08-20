"""Input sanitization for security."""

import re
import html
from typing import Optional, List


class InputSanitizer:
    """
    Sanitize user inputs to prevent security vulnerabilities.
    
    Features:
    - XSS prevention (HTML escaping)
    - SQL injection prevention (basic)
    - Null byte removal
    - Length limiting
    - Special character escaping
    
    Usage:
        sanitizer = InputSanitizer()
        clean = sanitizer.sanitize("<script>alert('xss')</script>")
        # Returns: &lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;
    """
    
    def __init__(
        self,
        max_length: int = 10000,
        allow_html: bool = False,
        allowed_tags: Optional[List[str]] = None,
    ):
        self.max_length = max_length
        self.allow_html = allow_html
        self.allowed_tags = allowed_tags or []
        
        # Dangerous patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
            r"(--)|(;)|(\|)",
            r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
        ]
    
    def sanitize(self, text: str) -> str:
        """Apply all sanitization rules."""
        if not text:
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Length limit
        if len(text) > self.max_length:
            text = text[:self.max_length]
        
        # Remove dangerous characters
        text = self._remove_dangerous_chars(text)
        
        # Escape HTML if not allowed
        if not self.allow_html:
            text = html.escape(text, quote=True)
        else:
            text = self._sanitize_html(text)
        
        return text
    
    def _remove_dangerous_chars(self, text: str) -> str:
        """Remove potentially dangerous characters."""
        # Remove control characters except newline and tab
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text
    
    def _sanitize_html(self, text: str) -> str:
        """Sanitize HTML allowing only safe tags."""
        if not self.allowed_tags:
            return html.escape(text, quote=True)
        
        # For now, just escape everything
        # A full implementation would use a library like bleach
        return html.escape(text, quote=True)
    
    def sanitize_for_sql(self, text: str) -> str:
        """Basic SQL injection prevention."""
        for pattern in self.sql_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text
    
    def sanitize_for_xss(self, text: str) -> str:
        """XSS prevention."""
        for pattern in self.xss_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return html.escape(text, quote=True)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename."""
        # Remove path separators
        filename = filename.replace('/', '').replace('\\', '')
        
        # Remove null bytes
        filename = filename.replace('\x00', '')
        
        # Only allow safe characters
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = f"{name[:250-len(ext)]}.{ext}" if ext else filename[:255]
        
        # Prevent hidden files
        if filename.startswith('.'):
            filename = '_' + filename[1:]
        
        return filename or "unnamed_file"
    
    def sanitize_url(self, url: str) -> Optional[str]:
        """Validate and sanitize a URL."""
        if not url:
            return None
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if url_pattern.match(url):
            # Remove javascript: URLs
            if url.lower().startswith('javascript:'):
                return None
            return url
        
        return None
    
    def sanitize_email(self, email: str) -> Optional[str]:
        """Validate and sanitize an email address."""
        if not email:
            return None
        
        email = email.strip().lower()
        
        # Basic email validation
        pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        if pattern.match(email):
            return email
        
        return None
    
    def is_safe(self, text: str) -> bool:
        """Check if text appears safe without modifying it."""
        # Check for obvious attack patterns
        for pattern in self.sql_patterns + self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # Check for null bytes
        if '\x00' in text:
            return False
        
        # Check for excessive length
        if len(text) > self.max_length * 2:
            return False
        
        return True
