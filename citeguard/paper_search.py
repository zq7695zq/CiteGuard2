"""
论文搜索模块
使用CrossRef和Semantic Scholar API搜索论文信息
"""
import requests
import time
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CROSSREF_API_URL, CROSSREF_EMAIL,
    SEMANTIC_SCHOLAR_API_URL, SEMANTIC_SCHOLAR_API_KEY,
    REQUEST_TIMEOUT, REQUEST_RETRY, REQUEST_DELAY
)


@dataclass
class PaperInfo:
    """论文信息数据类"""
    title: str = ""
    authors: List[str] = None
    year: str = ""
    abstract: str = ""
    doi: str = ""
    venue: str = ""  # 期刊或会议名
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    url: str = ""
    citation_count: int = 0
    
    # 验证信息
    is_verified: bool = False
    source: str = ""  # 数据来源: crossref, semantic_scholar, etc.
    similarity_score: float = 0.0  # 与查询的相似度
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []


class PaperSearcher:
    """论文搜索器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'CiteGuard/1.0 (mailto:{CROSSREF_EMAIL})'
        })
    
    def search_by_title(self, title: str, author: str = None, year: str = None) -> Optional[PaperInfo]:
        """
        通过论文标题搜索
        优先使用CrossRef，如果失败则使用Semantic Scholar
        """
        # 尝试CrossRef
        result = self._search_crossref(title, author, year)
        if result and result.is_verified:
            return result
        
        # 尝试Semantic Scholar
        result_ss = self._search_semantic_scholar(title)
        if result_ss and result_ss.is_verified:
            return result_ss
        
        # 返回最好的结果（即使未验证）
        return result or result_ss
    
    def search_by_doi(self, doi: str) -> Optional[PaperInfo]:
        """通过DOI搜索"""
        return self._search_crossref_by_doi(doi)
    
    def _search_crossref(self, title: str, author: str = None, year: str = None) -> Optional[PaperInfo]:
        """使用CrossRef API搜索"""
        try:
            # 构建查询参数
            params = {
                'query.title': title,
                'rows': 5,
                'select': 'DOI,title,author,published-print,published-online,container-title,volume,issue,page,publisher,abstract,is-referenced-by-count'
            }
            
            if author:
                # 取第一个作者的姓
                first_author = author.split(' and ')[0] if ' and ' in author else author
                last_name = first_author.split(',')[0].strip() if ',' in first_author else first_author.split()[-1]
                params['query.author'] = last_name
            
            response = self.session.get(
                CROSSREF_API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                print(f"CrossRef API error: {response.status_code}")
                return None
            
            data = response.json()
            items = data.get('message', {}).get('items', [])
            
            if not items:
                return None
            
            # 找到最匹配的结果
            best_match = None
            best_score = 0
            
            for item in items:
                score = self._calculate_similarity(title, item.get('title', [''])[0])
                
                # 如果指定了年份，检查年份是否匹配
                if year:
                    item_year = self._extract_year_from_crossref(item)
                    if item_year and item_year == year:
                        score += 0.2  # 年份匹配加分
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if best_match and best_score > 0.7:  # 相似度阈值
                paper_info = self._parse_crossref_result(best_match)
                paper_info.similarity_score = best_score
                paper_info.is_verified = best_score > 0.85
                return paper_info
            
            return None
            
        except Exception as e:
            print(f"CrossRef search error: {e}")
            return None
        finally:
            time.sleep(REQUEST_DELAY)
    
    def _search_crossref_by_doi(self, doi: str) -> Optional[PaperInfo]:
        """通过DOI在CrossRef搜索"""
        try:
            url = f"{CROSSREF_API_URL}/{doi}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            item = data.get('message', {})
            
            if item:
                paper_info = self._parse_crossref_result(item)
                paper_info.is_verified = True
                paper_info.similarity_score = 1.0
                return paper_info
            
            return None
            
        except Exception as e:
            print(f"CrossRef DOI search error: {e}")
            return None
        finally:
            time.sleep(REQUEST_DELAY)
    
    def _search_semantic_scholar(self, title: str) -> Optional[PaperInfo]:
        """使用Semantic Scholar API搜索"""
        try:
            # 使用搜索端点
            search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            
            headers = {}
            if SEMANTIC_SCHOLAR_API_KEY:
                headers['x-api-key'] = SEMANTIC_SCHOLAR_API_KEY
            
            params = {
                'query': title,
                'limit': 5,
                'fields': 'title,authors,year,abstract,venue,citationCount,externalIds,publicationVenue'
            }
            
            response = self.session.get(
                search_url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                print(f"Semantic Scholar API error: {response.status_code}")
                return None
            
            data = response.json()
            papers = data.get('data', [])
            
            if not papers:
                return None
            
            # 找到最匹配的结果
            best_match = None
            best_score = 0
            
            for paper in papers:
                paper_title = paper.get('title', '')
                score = self._calculate_similarity(title, paper_title)
                
                if score > best_score:
                    best_score = score
                    best_match = paper
            
            if best_match and best_score > 0.7:
                paper_info = self._parse_semantic_scholar_result(best_match)
                paper_info.similarity_score = best_score
                paper_info.is_verified = best_score > 0.85
                return paper_info
            
            return None
            
        except Exception as e:
            print(f"Semantic Scholar search error: {e}")
            return None
        finally:
            time.sleep(REQUEST_DELAY)
    
    def _parse_crossref_result(self, item: Dict) -> PaperInfo:
        """解析CrossRef返回结果"""
        # 提取作者
        authors = []
        for author in item.get('author', []):
            name = f"{author.get('family', '')}, {author.get('given', '')}"
            authors.append(name.strip(', '))
        
        # 提取年份
        year = self._extract_year_from_crossref(item)
        
        # 提取页码
        pages = item.get('page', '')
        
        return PaperInfo(
            title=item.get('title', [''])[0] if item.get('title') else '',
            authors=authors,
            year=year,
            abstract=item.get('abstract', ''),
            doi=item.get('DOI', ''),
            venue=item.get('container-title', [''])[0] if item.get('container-title') else '',
            volume=str(item.get('volume', '')),
            issue=str(item.get('issue', '')),
            pages=pages,
            publisher=item.get('publisher', ''),
            citation_count=item.get('is-referenced-by-count', 0),
            source='crossref'
        )
    
    def _parse_semantic_scholar_result(self, paper: Dict) -> PaperInfo:
        """解析Semantic Scholar返回结果"""
        # 提取作者
        authors = [a.get('name', '') for a in paper.get('authors', [])]
        
        # 提取DOI
        external_ids = paper.get('externalIds', {})
        doi = external_ids.get('DOI', '')
        
        return PaperInfo(
            title=paper.get('title', ''),
            authors=authors,
            year=str(paper.get('year', '')),
            abstract=paper.get('abstract', '') or '',
            doi=doi,
            venue=paper.get('venue', ''),
            citation_count=paper.get('citationCount', 0),
            source='semantic_scholar'
        )
    
    def _extract_year_from_crossref(self, item: Dict) -> str:
        """从CrossRef结果中提取年份"""
        # 尝试从published-print获取
        published = item.get('published-print') or item.get('published-online') or item.get('created')
        if published and 'date-parts' in published:
            date_parts = published['date-parts']
            if date_parts and date_parts[0]:
                return str(date_parts[0][0])
        return ''
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度"""
        if not str1 or not str2:
            return 0.0
        
        # 标准化字符串
        s1 = self._normalize_string(str1)
        s2 = self._normalize_string(str2)
        
        if s1 == s2:
            return 1.0
        
        # 使用词集合的Jaccard相似度
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _normalize_string(self, s: str) -> str:
        """标准化字符串用于比较"""
        # 转小写
        s = s.lower()
        # 移除标点符号
        s = re.sub(r'[^\w\s]', '', s)
        # 移除多余空格
        s = ' '.join(s.split())
        return s
    
    def verify_paper(self, title: str, author: str = None, year: str = None) -> Tuple[bool, Optional[PaperInfo], str]:
        """
        验证论文是否真实存在
        返回: (是否验证通过, 论文信息, 验证说明)
        """
        paper_info = self.search_by_title(title, author, year)
        
        if paper_info is None:
            return False, None, "未找到匹配的论文，可能不存在或信息有误"
        
        if paper_info.is_verified:
            return True, paper_info, f"论文验证通过（相似度: {paper_info.similarity_score:.2%}，来源: {paper_info.source}）"
        else:
            return False, paper_info, f"找到相似论文但相似度较低（{paper_info.similarity_score:.2%}），需要人工确认"


# 测试代码
if __name__ == "__main__":
    searcher = PaperSearcher()
    
    print("=" * 60)
    print("测试1: 搜索会议论文")
    print("=" * 60)
    
    title1 = "Game theory based D2D collaborative offloading for workflow applications in mobile edge computing"
    verified1, info1, msg1 = searcher.verify_paper(
        title=title1,
        author="Qian, Cheng",
        year="2022"
    )
    
    print(f"标题: {title1[:50]}...")
    print(f"验证结果: {verified1}")
    print(f"说明: {msg1}")
    if info1:
        print(f"找到DOI: {info1.doi}")
        print(f"找到标题: {info1.title}")
        print(f"摘要: {info1.abstract[:200] if info1.abstract else '无摘要'}...")
    
    print("\n" + "=" * 60)
    print("测试2: 搜索期刊论文")
    print("=" * 60)
    
    title2 = "Integrated networking, caching, and computing for connected vehicles: A deep reinforcement learning approach"
    verified2, info2, msg2 = searcher.verify_paper(
        title=title2,
        author="He, Ying",
        year="2017"
    )
    
    print(f"标题: {title2[:50]}...")
    print(f"验证结果: {verified2}")
    print(f"说明: {msg2}")
    if info2:
        print(f"找到DOI: {info2.doi}")
        print(f"找到标题: {info2.title}")
        print(f"摘要: {info2.abstract[:200] if info2.abstract else '无摘要'}...")
    
    print("\n" + "=" * 60)
    print("测试3: 搜索一个可能不存在的论文")
    print("=" * 60)
    
    title3 = "A completely fake paper title that does not exist anywhere in the world 12345"
    verified3, info3, msg3 = searcher.verify_paper(title=title3)
    
    print(f"标题: {title3[:50]}...")
    print(f"验证结果: {verified3}")
    print(f"说明: {msg3}")
