from typing import Callable,List
from dataclasses import dataclass

@dataclass
class TwitterContent:
    """
    转换成内容的标准值
    """
    author:str
    content:str
    link:str
    publish_date: str
    title:str
    media_list: List[str]

class ParseTwitterContext:
    """
    策略上下文
    """
    def __init__(self,source_type:str, strategy: Callable[[str],list[TwitterContent]]):
        self.source_type = source_type
        self.strategy = strategy

    def parse(self,user_id):
        return self.strategy(user_id)