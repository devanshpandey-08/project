"""Configuration management with environment variable support."""
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    encryption_enabled: bool = True
    audit_logging: bool = True
    rate_limit_requests_per_minute: int = 60
    api_keys: Dict[str, str] = field(default_factory=dict)
    pii_redaction_enabled: bool = True
    input_sanitization_enabled: bool = True


@dataclass
class ResilienceConfig:
    """Resilience and fault tolerance settings."""
    default_retry_count: int = 3
    default_timeout_seconds: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0
    rate_limit_enabled: bool = True


@dataclass
class ObservabilityConfig:
    """Observability and tracing settings."""
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    log_level: str = "INFO"
    trace_sample_rate: float = 1.0


@dataclass
class PersistenceConfig:
    """Checkpoint persistence settings."""
    checkpoint_enabled: bool = True
    storage_backend: str = "sqlite"  # memory, sqlite, postgres, redis
    sqlite_path: str = ":memory:"
    postgres_connection_string: Optional[str] = None
    redis_connection_string: Optional[str] = None


@dataclass
class FlowMindConfig:
    """Main configuration container."""
    
    security: SecurityConfig = field(default_factory=SecurityConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    
    @classmethod
    def from_env(cls, prefix: str = "FLOWMIND_") -> 'FlowMindConfig':
        """Load configuration from environment variables."""
        config = cls()
        
        # Security
        config.security.encryption_enabled = os.getenv(f"{prefix}ENCRYPTION_ENABLED", "true").lower() == "true"
        config.security.audit_logging = os.getenv(f"{prefix}AUDIT_LOGGING", "true").lower() == "true"
        config.security.rate_limit_requests_per_minute = int(os.getenv(f"{prefix}RATE_LIMIT", "60"))
        config.security.pii_redaction_enabled = os.getenv(f"{prefix}PII_REDACTION", "true").lower() == "true"
        config.security.input_sanitization_enabled = os.getenv(f"{prefix}INPUT_SANITIZATION", "true").lower() == "true"
        
        # Load API keys from env
        api_key_file = os.getenv(f"{prefix}API_KEY_FILE")
        if api_key_file and Path(api_key_file).exists():
            with open(api_key_file) as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config.security.api_keys[key] = value
        
        # Resilience
        config.resilience.default_retry_count = int(os.getenv(f"{prefix}RETRY_COUNT", "3"))
        config.resilience.default_timeout_seconds = float(os.getenv(f"{prefix}TIMEOUT", "30.0"))
        config.resilience.circuit_breaker_threshold = int(os.getenv(f"{prefix}CIRCUIT_BREAKER_THRESHOLD", "5"))
        config.resilience.circuit_breaker_recovery_seconds = float(os.getenv(f"{prefix}CIRCUIT_BREAKER_RECOVERY", "30.0"))
        config.resilience.rate_limit_enabled = os.getenv(f"{prefix}RATE_LIMIT_ENABLED", "true").lower() == "true"
        
        # Observability
        config.observability.tracing_enabled = os.getenv(f"{prefix}TRACING", "true").lower() == "true"
        config.observability.metrics_enabled = os.getenv(f"{prefix}METRICS", "true").lower() == "true"
        config.observability.log_level = os.getenv(f"{prefix}LOG_LEVEL", "INFO")
        config.observability.trace_sample_rate = float(os.getenv(f"{prefix}TRACE_SAMPLE_RATE", "1.0"))
        
        # Persistence
        config.persistence.checkpoint_enabled = os.getenv(f"{prefix}CHECKPOINTING", "true").lower() == "true"
        config.persistence.storage_backend = os.getenv(f"{prefix}STORAGE_BACKEND", "sqlite")
        config.persistence.sqlite_path = os.getenv(f"{prefix}SQLITE_PATH", ":memory:")
        config.persistence.postgres_connection_string = os.getenv(f"{prefix}POSTGRES_URL")
        config.persistence.redis_connection_string = os.getenv(f"{prefix}REDIS_URL")
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "security": {
                "encryption_enabled": self.security.encryption_enabled,
                "audit_logging": self.security.audit_logging,
                "rate_limit_requests_per_minute": self.security.rate_limit_requests_per_minute,
                "pii_redaction_enabled": self.security.pii_redaction_enabled,
                "input_sanitization_enabled": self.security.input_sanitization_enabled,
            },
            "resilience": {
                "default_retry_count": self.resilience.default_retry_count,
                "default_timeout_seconds": self.resilience.default_timeout_seconds,
                "circuit_breaker_threshold": self.resilience.circuit_breaker_threshold,
                "circuit_breaker_recovery_seconds": self.resilience.circuit_breaker_recovery_seconds,
                "rate_limit_enabled": self.resilience.rate_limit_enabled,
            },
            "observability": {
                "tracing_enabled": self.observability.tracing_enabled,
                "metrics_enabled": self.observability.metrics_enabled,
                "log_level": self.observability.log_level,
                "trace_sample_rate": self.observability.trace_sample_rate,
            },
            "persistence": {
                "checkpoint_enabled": self.persistence.checkpoint_enabled,
                "storage_backend": self.persistence.storage_backend,
                "sqlite_path": self.persistence.sqlite_path,
            }
        }
