from strategy.rss_parse import RssStrategy
from utils.config_manager import get_config
from utils.logger import get_logger

logger = get_logger(__name__)

_instance = None

def get_strategy():
    """工厂函数：根据配置获取策略实例（单例）"""
    global _instance
    if _instance is not None:
        return _instance

    strategy_type = get_config("base", "type", fallback="rss")

    if strategy_type == "rss":
        _instance = RssStrategy()
    else:
        # 如果有其他策略（如直接API），在这里扩展
        # 目前默认回退到 RSS 或抛出错误
        logger.warning(f"Unknown strategy type: {strategy_type}, falling back to RSS.")
        _instance = RssStrategy()

    return _instance
