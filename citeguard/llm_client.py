"""
LLM交互模块
封装硅基流动API调用
"""
import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, SILICONFLOW_MODEL, REQUEST_TIMEOUT


@dataclass
class ContextMatchResult:
    """上下文匹配结果"""
    is_match: bool          # 是否匹配
    confidence: float       # 置信度 0-1
    explanation: str        # 解释
    suggestion: str = ""    # 改进建议


@dataclass
class BibCorrectionResult:
    """BIB修正结果"""
    corrected_bib: str      # 修正后的BIB
    changes: List[str]      # 修改列表
    explanation: str        # 解释


class LLMClient:
    """LLM客户端 - 使用硅基流动API"""
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or SILICONFLOW_API_KEY
        self.model = model or SILICONFLOW_MODEL
        self.base_url = SILICONFLOW_BASE_URL
        
    def _call_api(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> Optional[str]:
        """调用API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                print(f"API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            return data['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"API call failed: {e}")
            return None
    
    def check_context_match(
        self, 
        paper_abstract: str, 
        citation_context: str,
        paper_title: str = ""
    ) -> ContextMatchResult:
        """
        检查论文摘要是否与引用上下文匹配
        
        Args:
            paper_abstract: 论文摘要
            citation_context: 引用上下文
            paper_title: 论文标题（可选）
            
        Returns:
            ContextMatchResult: 匹配结果
        """
        system_prompt = """你是一个学术论文引用审核专家。你的任务是判断一篇论文是否被正确引用。

你需要分析：
1. 论文的摘要/主题是否与引用上下文相关
2. 引用是否准确反映了论文的内容
3. 是否存在过度引用或误引的情况

请以JSON格式返回结果：
{
    "is_match": true/false,
    "confidence": 0.0-1.0,
    "explanation": "解释为什么匹配或不匹配",
    "suggestion": "如果不匹配，给出改进建议"
}

只返回JSON，不要有其他内容。"""

        user_prompt = f"""请判断以下论文是否被正确引用：

【论文标题】
{paper_title}

【论文摘要】
{paper_abstract if paper_abstract else "（摘要不可用）"}

【引用上下文】
{citation_context}

请分析这个引用是否恰当。"""

        response = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        if not response:
            return ContextMatchResult(
                is_match=True,  # 默认通过
                confidence=0.0,
                explanation="无法获取LLM响应，跳过检查"
            )
        
        try:
            # 尝试解析JSON
            # 处理可能的markdown代码块
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response)
            return ContextMatchResult(
                is_match=result.get("is_match", True),
                confidence=result.get("confidence", 0.5),
                explanation=result.get("explanation", ""),
                suggestion=result.get("suggestion", "")
            )
        except json.JSONDecodeError:
            # 如果解析失败，尝试从文本中提取关键信息
            is_match = "不匹配" not in response and "不相关" not in response
            return ContextMatchResult(
                is_match=is_match,
                confidence=0.5,
                explanation=response[:500]
            )
    
    def correct_bib_entry(
        self,
        original_bib: str,
        verified_info: Dict[str, Any],
        entry_type: str
    ) -> BibCorrectionResult:
        """
        修正BIB条目
        
        Args:
            original_bib: 原始BIB条目
            verified_info: 验证后的正确信息
            entry_type: 条目类型 (article/inproceedings等)
            
        Returns:
            BibCorrectionResult: 修正结果
        """
        system_prompt = """你是一个学术参考文献格式化专家。你的任务是修正和完善BibTeX条目。

规则：
1. 对于@article，必须包含：title, author, journal, year, volume, pages
2. 对于@inproceedings，必须包含：title, author, booktitle, year, pages
3. 如果有DOI，添加doi字段
4. 保持原始的引用键（cite_key）不变
5. 作者格式：Last, First and Last, First
6. 页码格式：123--456

请以JSON格式返回：
{
    "corrected_bib": "修正后的完整BibTeX条目",
    "changes": ["修改1", "修改2", ...],
    "explanation": "修改说明"
}

只返回JSON，不要有其他内容。"""

        verified_info_str = "\n".join([f"- {k}: {v}" for k, v in verified_info.items() if v])
        
        user_prompt = f"""请修正以下BibTeX条目：

【原始条目】
{original_bib}

【验证后的正确信息】
{verified_info_str}

【条目类型】
{entry_type}

请根据验证信息修正条目，确保格式正确且信息完整。"""

        response = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        if not response:
            return BibCorrectionResult(
                corrected_bib=original_bib,
                changes=[],
                explanation="无法获取LLM响应，保持原样"
            )
        
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response)
            return BibCorrectionResult(
                corrected_bib=result.get("corrected_bib", original_bib),
                changes=result.get("changes", []),
                explanation=result.get("explanation", "")
            )
        except json.JSONDecodeError:
            return BibCorrectionResult(
                corrected_bib=original_bib,
                changes=[],
                explanation=f"JSON解析失败: {response[:200]}"
            )
    
    def batch_analyze_citations(
        self,
        citations_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量分析引用（一次API调用处理多个引用）
        
        Args:
            citations_data: 引用数据列表，每个包含paper_abstract, citation_context, paper_title
            
        Returns:
            分析结果列表
        """
        if not citations_data:
            return []
        
        system_prompt = """你是一个学术论文引用审核专家。请批量分析以下引用是否恰当。

对于每个引用，请判断：
1. 论文的摘要/主题是否与引用上下文相关
2. 引用是否准确反映了论文的内容

请以JSON数组格式返回，每个元素包含：
{
    "index": 0,
    "is_match": true/false,
    "confidence": 0.0-1.0,
    "explanation": "简短解释"
}

只返回JSON数组，不要有其他内容。"""

        citations_text = ""
        for i, data in enumerate(citations_data):
            citations_text += f"""
--- 引用 #{i} ---
【论文标题】{data.get('paper_title', '')}
【论文摘要】{data.get('paper_abstract', '摘要不可用')[:300]}
【引用上下文】{data.get('citation_context', '')[:300]}

"""

        user_prompt = f"请分析以下{len(citations_data)}个引用：\n{citations_text}"
        
        response = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.2)
        
        if not response:
            return [{"index": i, "is_match": True, "confidence": 0, "explanation": "API调用失败"} 
                    for i in range(len(citations_data))]
        
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            return json.loads(response)
        except json.JSONDecodeError:
            return [{"index": i, "is_match": True, "confidence": 0, "explanation": "解析失败"} 
                    for i in range(len(citations_data))]


# 测试代码 - 模拟LLM响应
class MockLLMClient(LLMClient):
    """模拟LLM客户端，用于测试"""
    
    def _call_api(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> Optional[str]:
        """模拟API调用"""
        user_message = messages[-1]["content"]
        
        # 模拟上下文匹配检查
        if "引用上下文" in user_message:
            # 根据内容判断是否匹配
            if "game theory" in user_message.lower() and "offloading" in user_message.lower():
                return json.dumps({
                    "is_match": True,
                    "confidence": 0.92,
                    "explanation": "论文摘要讨论了基于博弈论的D2D协作卸载方案，与引用上下文中提到的边缘计算任务卸载主题高度相关。",
                    "suggestion": ""
                })
            elif "deep reinforcement learning" in user_message.lower() and "vehicle" in user_message.lower():
                return json.dumps({
                    "is_match": True,
                    "confidence": 0.88,
                    "explanation": "论文研究了车联网中的深度强化学习方法，与引用上下文讨论的内容一致。",
                    "suggestion": ""
                })
            else:
                return json.dumps({
                    "is_match": False,
                    "confidence": 0.75,
                    "explanation": "引用上下文与论文主题不够相关。",
                    "suggestion": "建议查找更相关的参考文献。"
                })
        
        # 模拟BIB修正 - 动态解析原始BIB并添加DOI
        if "BibTeX" in user_message:
            import re
            # 提取原始BIB
            bib_match = re.search(r'@(\w+)\{([^,]+),([^@]+)\}', user_message, re.DOTALL)
            if bib_match:
                entry_type = bib_match.group(1)
                cite_key = bib_match.group(2)
                
                # 提取DOI
                doi_match = re.search(r'doi:\s*([^\n,]+)', user_message, re.IGNORECASE)
                doi = doi_match.group(1).strip() if doi_match else ""
                
                # 提取原始字段并添加DOI
                fields_text = bib_match.group(3)
                if doi and "doi=" not in fields_text.lower():
                    fields_text = fields_text.rstrip().rstrip('}').rstrip(',')
                    fields_text += f",\n  doi={{{doi}}}"
                
                corrected = f"@{entry_type}{{{cite_key},{fields_text}\n}}"
                
                return json.dumps({
                    "corrected_bib": corrected,
                    "changes": ["添加了DOI字段"] if doi else [],
                    "explanation": "根据验证信息补充了DOI字段。"
                })
        
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("测试LLM客户端（使用模拟客户端）")
    print("=" * 60)
    
    client = MockLLMClient()
    
    # 测试上下文匹配
    print("\n--- 测试1: 上下文匹配检查 ---")
    result = client.check_context_match(
        paper_abstract="This paper proposes a game theory based D2D collaborative offloading scheme for workflow applications in mobile edge computing.",
        citation_context="Various game-theoretic approaches have been proposed for task offloading in MEC environments.",
        paper_title="Game Theory based D2D Collaborative Offloading"
    )
    print(f"匹配: {result.is_match}")
    print(f"置信度: {result.confidence}")
    print(f"解释: {result.explanation}")
    
    # 测试BIB修正
    print("\n--- 测试2: BIB条目修正 ---")
    original_bib = """@inproceedings{qian2022game,
  title={Game theory based D2D collaborative offloading for workflow applications in mobile edge computing},
  author={Qian, Cheng and Zhao, Gansen and Luo, Haoyu},
  booktitle={2022 IEEE International Conference on Web Services (ICWS)},
  pages={276--285},
  year={2022},
  organization={IEEE}
}"""
    
    correction = client.correct_bib_entry(
        original_bib=original_bib,
        verified_info={
            "doi": "10.1109/ICWS55610.2022.00049",
            "title": "Game Theory based D2D Collaborative Offloading for Workflow Applications in Mobile Edge Computing"
        },
        entry_type="inproceedings"
    )
    
    print(f"修改项: {correction.changes}")
    print(f"说明: {correction.explanation}")
    print(f"\n修正后的BIB:\n{correction.corrected_bib}")
