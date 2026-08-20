"""
FlowMind Configuration System

Production-ready configuration management with:
- Environment variable support
- YAML/JSON config files
- Secret management
- Validation
- Hot reloading
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import os
import json
import asyncio


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout_seconds: float = 60.0
    retry_count: int = 3


@dataclass
class VectorStoreConfig:
    """Vector store configuration."""
    provider: str = "inmemory"  # inmemory, pinecone, weaviate, chroma, milvus
    dimensions: int = 1536
    index_name: str = "flomind_index"
    connection_string: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class MemoryConfig:
    """Memory system configuration."""
    short_term_max_messages: int = 100
    long_term_storage_path: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class ObservabilityConfig:
    """Observability configuration."""
    enabled: bool = True
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    log_level: str = "INFO"
    export_endpoint: Optional[str] = None  # OTLP endpoint
    service_name: str = "flomind"
    sampling_rate: float = 1.0
    max_spans_per_trace: int = 1000


@dataclass
class ResilienceConfig:
    """Resilience policies configuration."""
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    timeout_default_seconds: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0


@dataclass
class StreamingConfig:
    """Streaming configuration."""
    enabled: bool = True
    buffer_size: int = 100
    chunk_size: int = 1000
    timeout_seconds: float = 30.0


@dataclass
class SecurityConfig:
    """Security configuration."""
    api_keys: List[str] = field(default_factory=list)
    allowed_origins: List[str] = field(default_factory=list)
    rate_limit_requests_per_minute: int = 60
    encryption_enabled: bool = True
    audit_logging: bool = True


@dataclass
class FlowMindConfig:
    """
    Main configuration class for FlowMind.
    
    Provides centralized configuration management for all components.
    """
    # Component configurations
    llm: LLMConfig = field(default_factory=LLMConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Global settings
    environment: str = "development"  # development, staging, production
    debug: bool = False
    max_concurrent_flows: int = 100
    default_timeout_seconds: float = 120.0
    
    @classmethod
    def from_env(cls, prefix: str = "FLOWMIND_") -> 'FlowMindConfig':
        """
        Load configuration from environment variables.
        
        Args:
            prefix: Environment variable prefix
            
        Returns:
            FlowMindConfig instance
        """
        config = cls()
        
        # LLM config
        if provider := os.getenv(f"{prefix}LLM_PROVIDER"):
            config.llm.provider = provider
        if model := os.getenv(f"{prefix}LLM_MODEL"):
            config.llm.model = model
        if api_key := os.getenv(f"{prefix}LLM_API_KEY"):
            config.llm.api_key = api_key
        if base_url := os.getenv(f"{prefix}LLM_BASE_URL"):
            config.llm.base_url = base_url
        
        # Vector store config
        if provider := os.getenv(f"{prefix}VECTOR_PROVIDER"):
            config.vector_store.provider = provider
        if conn_str := os.getenv(f"{prefix}VECTOR_CONNECTION_STRING"):
            config.vector_store.connection_string = conn_str
        
        # Observability config
        if enabled := os.getenv(f"{prefix}OBSERVABILITY_ENABLED"):
            config.observability.enabled = enabled.lower() == "true"
        if endpoint := os.getenv(f"{prefix}OBSERVABILITY_ENDPOINT"):
            config.observability.export_endpoint = endpoint
        if log_level := os.getenv(f"{prefix}LOG_LEVEL"):
            config.observability.log_level = log_level.upper()
        
        # Environment
        if env := os.getenv(f"{prefix}ENVIRONMENT"):
            config.environment = env
        if debug := os.getenv(f"{prefix}DEBUG"):
            config.debug = debug.lower() == "true"
        
        return config
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'FlowMindConfig':
        """
        Load configuration from a JSON or YAML file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            FlowMindConfig instance
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, 'r') as f:
            if path.suffix in ('.yaml', '.yml'):
                try:
                    import yaml
                    data = yaml.safe_load(f)
                except ImportError:
                    raise ImportError("Install PyYAML: pip install pyyaml")
            else:
                data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FlowMindConfig':
        """Load configuration from a dictionary."""
        config = cls()
        
        if 'llm' in data:
            config.llm = LLMConfig(**data['llm'])
        if 'vector_store' in data:
            config.vector_store = VectorStoreConfig(**data['vector_store'])
        if 'memory' in data:
            config.memory = MemoryConfig(**data['memory'])
        if 'observability' in data:
            config.observability = ObservabilityConfig(**data['observability'])
        if 'resilience' in data:
            config.resilience = ResilienceConfig(**data['resilience'])
        if 'streaming' in data:
            config.streaming = StreamingConfig(**data['streaming'])
        if 'security' in data:
            config.security = SecurityConfig(**data['security'])
        
        # Global settings
        if 'environment' in data:
            config.environment = data['environment']
        if 'debug' in data:
            config.debug = data['debug']
        if 'max_concurrent_flows' in data:
            config.max_concurrent_flows = data['max_concurrent_flows']
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'environment': self.environment,
            'debug': self.debug,
            'llm': {
                'provider': self.llm.provider,
                'model': self.llm.model,
                'temperature': self.llm.temperature,
                'timeout_seconds': self.llm.timeout_seconds,
            },
            'observability': {
                'enabled': self.observability.enabled,
                'log_level': self.observability.log_level,
            },
            'resilience': {
                'retry_max_attempts': self.resilience.retry_max_attempts,
                'timeout_default_seconds': self.resilience.timeout_default_seconds,
            },
        }
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Validate LLM config
        if self.llm.provider not in ('openai', 'anthropic', 'google', 'azure', 'ollama', 'mock'):
            errors.append(f"Invalid LLM provider: {self.llm.provider}")
        
        if self.llm.temperature < 0 or self.llm.temperature > 2:
            errors.append("LLM temperature must be between 0 and 2")
        
        # Validate observability
        if self.observability.sampling_rate < 0 or self.observability.sampling_rate > 1:
            errors.append("Observability sampling rate must be between 0 and 1")
        
        # Validate resilience
        if self.resilience.retry_max_attempts < 0:
            errors.append("Retry max attempts must be non-negative")
        
        # Validate security in production
        if self.environment == "production":
            if not self.security.api_keys:
                errors.append("API keys required in production")
            if not self.security.audit_logging:
                errors.append("Audit logging required in production")
        
        return errors
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


class ConfigManager:
    """
    Centralized configuration manager with hot reloading.
    
    Usage:
        manager = ConfigManager()
        config = manager.get_config()
        
        # Or load from file
        manager.load_from_file("config.yaml")
        
        # Or from environment
        manager.load_from_env()
    """
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[FlowMindConfig] = None
    _watch_task: Optional[asyncio.Task] = None
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = FlowMindConfig()
    
    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """Get singleton instance."""
        return cls()
    
    def get_config(self) -> FlowMindConfig:
        """Get current configuration."""
        return self._config
    
    def load_from_file(self, path: Union[str, Path]) -> FlowMindConfig:
        """Load configuration from file."""
        self._config = FlowMindConfig.from_file(path)
        return self._config
    
    def load_from_env(self, prefix: str = "FLOWMIND_") -> FlowMindConfig:
        """Load configuration from environment variables."""
        self._config = FlowMindConfig.from_env(prefix)
        return self._config
    
    def load_from_dict(self, data: Dict[str, Any]) -> FlowMindConfig:
        """Load configuration from dictionary."""
        self._config = FlowMindConfig.from_dict(data)
        return self._config
    
    async def watch_file(self, path: Union[str, Path], callback: callable = None) -> None:
        """
        Watch configuration file for changes and reload automatically.
        
        Args:
            path: Path to configuration file
            callback: Optional callback function to call on reload
        """
        path = Path(path)
        last_modified = path.stat().st_mtime if path.exists() else 0
        
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            if path.exists():
                current_modified = path.stat().st_mtime
                if current_modified != last_modified:
                    try:
                        self.load_from_file(path)
                        if callback:
                            callback(self._config)
                        last_modified = current_modified
                    except Exception as e:
                        # Log error but continue watching
                        pass
    
    def stop_watching(self) -> None:
        """Stop watching for configuration changes."""
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None


# Global configuration accessor
def get_config() -> FlowMindConfig:
    """Get global configuration."""
    return ConfigManager.get_instance().get_config()


def load_config(path: Union[str, Path]) -> FlowMindConfig:
    """Load configuration from file."""
    return ConfigManager.get_instance().load_from_file(path)


def load_config_from_env(prefix: str = "FLOWMIND_") -> FlowMindConfig:
    """Load configuration from environment."""
    return ConfigManager.get_instance().load_from_env(prefix)
