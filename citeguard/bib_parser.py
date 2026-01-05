"""
BIB文件解析模块
解析bibtex格式的参考文献文件
"""
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class BibEntry:
    """表示一个BIB条目"""
    entry_type: str  # inproceedings, article, book, etc.
    cite_key: str    # 引用键，如 qian2022game
    title: str = ""
    author: str = ""
    year: str = ""
    
    # 期刊论文字段
    journal: str = ""
    volume: str = ""
    number: str = ""
    pages: str = ""
    publisher: str = ""
    
    # 会议论文字段
    booktitle: str = ""
    organization: str = ""
    
    # 其他字段
    doi: str = ""
    url: str = ""
    abstract: str = ""
    keywords: str = ""
    
    # 原始文本
    raw_text: str = ""
    
    # 额外字段（存储未预定义的字段）
    extra_fields: Dict[str, str] = field(default_factory=dict)
    
    def to_bibtex(self) -> str:
        """将条目转换回bibtex格式"""
        lines = [f"@{self.entry_type}{{{self.cite_key},"]
        
        # 定义字段顺序
        field_order = [
            ("title", self.title),
            ("author", self.author),
            ("booktitle", self.booktitle),
            ("journal", self.journal),
            ("volume", self.volume),
            ("number", self.number),
            ("pages", self.pages),
            ("year", self.year),
            ("organization", self.organization),
            ("publisher", self.publisher),
            ("doi", self.doi),
            ("url", self.url),
            ("abstract", self.abstract),
            ("keywords", self.keywords),
        ]
        
        for field_name, field_value in field_order:
            if field_value:
                lines.append(f"  {field_name}={{{field_value}}},")
        
        # 添加额外字段
        for field_name, field_value in self.extra_fields.items():
            if field_value:
                lines.append(f"  {field_name}={{{field_value}}},")
        
        lines.append("}")
        return "\n".join(lines)
    
    def get_search_query(self) -> str:
        """获取用于搜索的查询字符串"""
        # 优先使用DOI
        if self.doi:
            return self.doi
        # 否则使用标题
        return self.title
    
    def get_author_list(self) -> List[str]:
        """解析作者列表"""
        if not self.author:
            return []
        # 按 "and" 分割作者
        authors = re.split(r'\s+and\s+', self.author)
        return [a.strip() for a in authors]


class BibParser:
    """BIB文件解析器"""
    
    def __init__(self):
        self.entries: List[BibEntry] = []
    
    def parse_file(self, filepath: str) -> List[BibEntry]:
        """解析bib文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse_string(content)
    
    def parse_string(self, content: str) -> List[BibEntry]:
        """解析bib字符串"""
        self.entries = []
        
        # 匹配所有条目 @type{key, ...}
        # 使用更鲁棒的匹配方式
        entry_pattern = r'@(\w+)\s*\{\s*([^,]+)\s*,([^@]*?)(?=\n\s*@|\n*$)'
        matches = re.finditer(entry_pattern, content, re.DOTALL)
        
        for match in matches:
            entry_type = match.group(1).lower()
            cite_key = match.group(2).strip()
            fields_text = match.group(3)
            
            entry = BibEntry(
                entry_type=entry_type,
                cite_key=cite_key,
                raw_text=match.group(0)
            )
            
            # 解析字段
            self._parse_fields(entry, fields_text)
            self.entries.append(entry)
        
        return self.entries
    
    def _parse_fields(self, entry: BibEntry, fields_text: str):
        """解析条目中的字段"""
        # 匹配字段：fieldname = {value} 或 fieldname = "value" 或 fieldname = value
        # 需要处理嵌套大括号的情况
        
        # 先处理 field = {value} 形式（最常见）
        brace_pattern = r'(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
        for match in re.finditer(brace_pattern, fields_text):
            field_name = match.group(1).lower()
            field_value = match.group(2).strip()
            self._set_field(entry, field_name, field_value)
        
        # 处理 field = "value" 形式
        quote_pattern = r'(\w+)\s*=\s*"([^"]*)"'
        for match in re.finditer(quote_pattern, fields_text):
            field_name = match.group(1).lower()
            field_value = match.group(2).strip()
            self._set_field(entry, field_name, field_value)
        
        # 处理 field = number 形式（主要是year）
        number_pattern = r'(\w+)\s*=\s*(\d+)'
        for match in re.finditer(number_pattern, fields_text):
            field_name = match.group(1).lower()
            field_value = match.group(2).strip()
            # 只有当该字段还未设置时才设置
            if not getattr(entry, field_name, None) and field_name not in entry.extra_fields:
                self._set_field(entry, field_name, field_value)
    
    def _set_field(self, entry: BibEntry, field_name: str, field_value: str):
        """设置字段值"""
        known_fields = [
            'title', 'author', 'year', 'journal', 'volume', 'number',
            'pages', 'publisher', 'booktitle', 'organization', 'doi',
            'url', 'abstract', 'keywords'
        ]
        
        if field_name in known_fields:
            setattr(entry, field_name, field_value)
        else:
            entry.extra_fields[field_name] = field_value
    
    def get_entry_by_key(self, cite_key: str) -> Optional[BibEntry]:
        """根据引用键获取条目"""
        for entry in self.entries:
            if entry.cite_key == cite_key:
                return entry
        return None
    
    def export_to_file(self, filepath: str, entries: List[BibEntry] = None):
        """导出为bib文件"""
        if entries is None:
            entries = self.entries
        
        content = "\n\n".join(entry.to_bibtex() for entry in entries)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)


# 测试代码
if __name__ == "__main__":
    test_bib = """
@inproceedings{qian2022game,
  title={Game theory based D2D collaborative offloading for workflow applications in mobile edge computing},
  author={Qian, Cheng and Zhao, Gansen and Luo, Haoyu},
  booktitle={2022 IEEE International Conference on Web Services (ICWS)},
  pages={276--285},
  year={2022},
  organization={IEEE}
}

@article{he2017integrated,
  title={Integrated networking, caching, and computing for connected vehicles: A deep reinforcement learning approach},
  author={He, Ying and Zhao, Nan and Yin, Hongxi},
  journal={IEEE transactions on vehicular technology},
  volume={67},
  number={1},
  pages={44--55},
  year={2017},
  publisher={IEEE}
}
"""
    
    parser = BibParser()
    entries = parser.parse_string(test_bib)
    
    print(f"解析到 {len(entries)} 个条目:\n")
    for entry in entries:
        print(f"Key: {entry.cite_key}")
        print(f"Type: {entry.entry_type}")
        print(f"Title: {entry.title}")
        print(f"Author: {entry.author}")
        print(f"Year: {entry.year}")
        print(f"Authors list: {entry.get_author_list()}")
        print("-" * 50)
    
    print("\n导出测试:")
    for entry in entries:
        print(entry.to_bibtex())
        print()
