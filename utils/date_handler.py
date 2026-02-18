"""日期处理工具模块"""
from datetime import datetime
from typing import Optional, Union

class DateHandler:
    """日期处理类"""
    
    # 常用日期格式
    FORMATS = {
        'rfc2822': '%a, %d %b %Y %H:%M:%S %Z',
        'iso_basic': '%Y-%m-%dT%H:%M:%S',
        'iso_zulu': '%Y-%m-%dT%H:%M:%SZ',
        'standard': '%Y-%m-%d %H:%M:%S',
        'date_only': '%Y-%m-%d'
    }
    
    @staticmethod
    def parse_rfc2822(date_str: str) -> Optional[datetime]:
        """解析RFC 2822格式日期"""
        if not date_str:
            return None
            
        try:
            # 尝试标准格式
            return datetime.strptime(date_str.strip(), DateHandler.FORMATS['rfc2822'])
        except ValueError:
            # 尝试其他变体
            variants = [
                '%a, %d %b %Y %H:%M:%S GMT',
                '%a, %d %b %Y %H:%M:%S UTC',
                '%a, %d %b %Y %H:%M:%S',
            ]
            for fmt in variants:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            return None
    
    @staticmethod
    def format_standard(dt: Union[datetime, str]) -> str:
        """格式化为标准格式"""
        if isinstance(dt, str):
            parsed_dt = DateHandler.parse_rfc2822(dt)
            if parsed_dt is None:
                return dt  # 返回原字符串
            dt = parsed_dt
        
        return dt.strftime(DateHandler.FORMATS['standard'])

    @staticmethod
    def format_notify(dt: Union[datetime, str]) -> str:
        """格式化为通知格式 yyyy-mm-dd HH:MM"""
        if isinstance(dt, str):
            parsed_dt = DateHandler.parse_rfc2822(dt)
            if parsed_dt is None:
                return dt  # 返回原字符串
            dt = parsed_dt

        return dt.strftime('%Y-%m-%d %H:%M')

    @staticmethod
    def to_timestamp(dt: Union[datetime, str]) -> Optional[float]:
        """转换为时间戳"""
        if isinstance(dt, str):
            parsed_dt = DateHandler.parse_rfc2822(dt)
            if parsed_dt is None:
                return None
            dt = parsed_dt
        
        return dt.timestamp() if isinstance(dt, datetime) else None
    
    @staticmethod
    def is_newer(new_date: str, old_date: str) -> bool:
        """比较两个日期，判断new_date是否比old_date更新"""
        new_dt = DateHandler.parse_rfc2822(new_date)
        old_dt = DateHandler.parse_rfc2822(old_date)
        
        if new_dt is None or old_dt is None:
            return False
            
        return new_dt > old_dt

# 便捷函数
def parse_date(date_str: str) -> Optional[datetime]:
    """便捷的日期解析函数"""
    return DateHandler.parse_rfc2822(date_str)

def format_date(dt: Union[datetime, str]) -> str:
    """便捷的日期格式化函数"""
    return DateHandler.format_standard(dt)

# 测试代码
if __name__ == "__main__":
    # 测试RFC 2822格式解析
    test_date = "Thu, 12 Feb 2026 15:21:06 GMT"
    parsed = parse_date(test_date)
    formatted = format_date(parsed)
    
    print(f"原始: {test_date}")
    print(f"解析: {parsed}")
    print(f"格式化: {formatted}")
    print(f"时间戳: {DateHandler.to_timestamp(test_date)}")