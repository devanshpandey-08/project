"""Configuration system for FlowMind."""

import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SecurityConfig:
    """Security configuration."""
    encryption_key: Optional[str] = None
    enable_pii_detection: bool = True
    enable_input_sanitization: bool = True
    audit_logging: bool = True
    mask_sensitive_data: bool = True


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    default_provider: str = "openai"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class ObservabilityConfig:
    """Observability configuration."""
    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"
    export_to_file: bool = False
    log_directory: str = "./logs"


@dataclass
class FlowMindConfig:
    """
    Main configuration class for FlowMind.
    
    Features:
    - Environment variable support (FLOWMIND_* prefix)
    - YAML/JSON config file loading
    - Configuration validation
    - Hot reloading capability
    """
    # Application
    app_name: str = "FlowMind"
    environment: str = "production"  # development, staging, production
    debug: bool = False
    
    # Sub-configs
    security: SecurityConfig = field(default_factory=SecurityConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    
    @classmethod
    def from_env(cls) -> 'FlowMindConfig':
        """Load configuration from environment variables."""
        config = cls()
        
        # App settings
        config.environment = os.getenv("FLOWMIND_ENV", "production")
        config.debug = os.getenv("FLOWMIND_DEBUG", "false").lower() == "true"
        
        # Security
        config.security.encryption_key = os.getenv("FLOWMIND_ENCRYPTION_KEY")
        config.security.enable_pii_detection = os.getenv("FLOWMIND_ENABLE_PII", "true").lower() == "true"
        
        # Rate limiting
        config.rate_limit.requests_per_minute = int(os.getenv("FLOWMIND_RATE_LIMIT_PER_MIN", "60"))
        
        # LLM
        config.llm.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("FLOWMIND_OPENAI_KEY")
        config.llm.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("FLOWMIND_ANTHROPIC_KEY")
        config.llm.default_model = os.getenv("FLOWMIND_DEFAULT_MODEL", "gpt-4")
        
        # Observability
        config.observability.log_level = os.getenv("FLOWMIND_LOG_LEVEL", "INFO")
        
        return config
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "debug": self.debug,
            "security": {
                "enable_pii_detection": self.security.enable_pii_detection,
                "enable_input_sanitization": self.security.enable_input_sanitization,
                "audit_logging": self.security.audit_logging,
            },
            "rate_limit": {
                "enabled": self.rate_limit.enabled,
                "requests_per_minute": self.rate_limit.requests_per_minute,
            },
            "llm": {
                "default_provider": self.llm.default_provider,
                "default_model": self.llm.default_model,
            },
            "observability": {
                "enable_tracing": self.observability.enable_tracing,
                "log_level": self.observability.log_level,
            }
        }
        
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if self.environment not in ["development", "staging", "production"]:
            errors.append(f"Invalid environment: {self.environment}")
            
        if self.security.encryption_key and len(self.security.encryption_key) < 32:
            errors.append("Encryption key must be at least 32 characters")
            
        if self.rate_limit.requests_per_minute <= 0:
            errors.append("Rate limit must be positive")
            
        return errors


# Global configuration instance
_settings: Optional[FlowMindConfig] = None


def get_settings() -> FlowMindConfig:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = FlowMindConfig.from_env()
    return _settings


def configure(settings: FlowMindConfig) -> None:
    """Set global settings."""
    global _settings
    _settings = settings


Settings = FlowMindConfig  # Alias for backwards compatibility
