from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Iterable, Optional, TypeVar
import os
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_DEFAULT_FILENAME = "config.ini"
_DEFAULT_ENV_PREFIX = "AUTONOTICE"


class ConfigError(RuntimeError):
    """当配置加载或查找失败时抛出的异常。"""


class ConfigManager:
    """集中化的项目配置加载和访问助手。"""

    def __init__(self, config_path: str | Path | None = None, env_prefix: str = _DEFAULT_ENV_PREFIX) -> None:
        self._config_path = self._resolve_path(config_path)
        self._env_prefix = env_prefix.upper()
        self._parser = ConfigParser()
        self._lock = RLock()
        self.reload()

    def reload(self) -> None:
        """从磁盘重新加载配置。"""
        with self._lock:
            # 使用 is_file()。如果宿主机不存在该文件，Docker 可能会创建一个同名的文件夹，导致 exists() 为 True 但无法作为配置文件读取。
            if not self._config_path.is_file():
                if self._config_path.exists():
                    logger.warning(f"{self._config_path} 是一个目录而不是文件，将跳过读取。")
                else:
                    logger.info(f"配置文件不存在: {self._config_path}，将仅依赖环境变量配置。")
                return
                
            read_files = self._parser.read(self._config_path, encoding="utf-8")
            if not read_files:
                # 只有当路径存在但读取失败（比如权限问题）时才抛出异常
                raise ConfigError(f"未能正确解析配置文件: {self._config_path}")

    def get(self, section: str, option: str, *, fallback: Optional[T] = None, cast: Optional[Callable[[str], T]] = None, required: bool = False) -> Optional[T | str]:
        """返回配置值，支持可选的类型转换和验证。"""
        raw_value = self._lookup_value(section, option)
        if raw_value is None:
            if required and fallback is None:
                raise ConfigError(f"缺少必要配置: [{section}] {option}")
            return fallback

        if cast is None:
            return raw_value

        try:
            return cast(raw_value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive path
            raise ConfigError(f"配置值无法转换: [{section}] {option} -> {raw_value}") from exc

    def get_int(self, section: str, option: str, **kwargs: Any) -> Optional[int]:
        return self.get(section, option, cast=int, **kwargs)

    def get_float(self, section: str, option: str, **kwargs: Any) -> Optional[float]:
        return self.get(section, option, cast=float, **kwargs)

    def get_bool(self, section: str, option: str, **kwargs: Any) -> Optional[bool]:
        return self.get(section, option, cast=self._to_bool, **kwargs)

    def as_dict(self, section: str, *, include_env: bool = True) -> Dict[str, str]:
        """以字典形式返回解析后的配置段副本。"""
        if not self._parser.has_section(section):
            raise ConfigError(f"找不到配置段: [{section}]")

        items = {key: value for key, value in self._parser.items(section)}
        if include_env:
            for key in list(items):
                env_value = self._lookup_env(section, key)
                if env_value is not None:
                    items[key] = env_value
        return items

    @staticmethod
    def _resolve_path(config_path: str | Path | None) -> Path:
        """解析配置文件路径，支持Docker环境"""
        if config_path:
            return Path(config_path)
        
        # 检查是否在Docker环境中
        if os.getenv('DOCKER_ENV') or os.path.exists('/.dockerenv'):
            # Docker环境下优先检查工作目录
            docker_config_path = Path('/app') / _DEFAULT_FILENAME
            if docker_config_path.exists():
                return docker_config_path
            
        # 检查环境变量指定的配置路径
        env_config_path = os.getenv('AUTONOTICE_CONFIG_PATH')
        if env_config_path:
            return Path(env_config_path)
        
        # 默认使用项目根目录
        return Path(__file__).resolve().parents[1] / _DEFAULT_FILENAME

    def _lookup_value(self, section: str, option: str) -> Optional[str]:
        env_value = self._lookup_env(section, option)
        if env_value is not None:
            return env_value
        if self._parser.has_option(section, option):
            return self._parser.get(section, option)
        return None

    def _lookup_env(self, section: str, option: str) -> Optional[str]:
        env_key = self._build_env_key(section, option)
        return os.getenv(env_key)

    def _build_env_key(self, section: str, option: str) -> str:
        sanitized_section = section.replace(".", "_").replace("-", "_")
        sanitized_option = option.replace(".", "_").replace("-", "_")
        return f"{self._env_prefix}__{sanitized_section}__{sanitized_option}".upper()

    @staticmethod
    def _to_bool(value: str) -> bool:
        """将字符串转换为布尔值。"""
        truthy = {"1", "true", "yes", "on"}
        falsy = {"0", "false", "no", "off"}
        lowered = value.strip().lower()
        if lowered in truthy:
            return True
        if lowered in falsy:
            return False
        raise ValueError(f"无法解析布尔值: {value}")


_default_manager: Optional[ConfigManager] = None
_manager_lock = RLock()


def get_manager() -> ConfigManager:
    """返回共享的ConfigManager实例。"""
    global _default_manager
    with _manager_lock:
        if _default_manager is None:
            _default_manager = ConfigManager()
        return _default_manager


def get_config(section: str, option: str, **kwargs: Any) -> Optional[Any]:
    """便捷代理函数，镜像ConfigManager.get方法。"""
    return get_manager().get(section, option, **kwargs)


def reload_config() -> None:
    get_manager().reload()
