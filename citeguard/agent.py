"""
CiteGuard Agent - 核心逻辑
整合所有模块，实现完整的论文引用检查流程
"""
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .bib_parser import BibParser, BibEntry
from .paper_search import PaperSearcher, PaperInfo
from .latex_parser import LatexParser, CitationContext
from .llm_client import LLMClient, ContextMatchResult, BibCorrectionResult


@dataclass
class VerificationResult:
    """单篇论文验证结果"""
    cite_key: str
    original_entry: BibEntry
    
    # 真实性验证
    is_verified: bool = False
    verification_message: str = ""
    verified_info: Optional[PaperInfo] = None
    
    # 上下文匹配
    context_checks: List[Dict] = field(default_factory=list)
    all_contexts_match: bool = True
    
    # 修正后的BIB
    corrected_entry: Optional[BibEntry] = None
    corrections: List[str] = field(default_factory=list)


@dataclass
class CheckReport:
    """检查报告"""
    timestamp: str
    total_citations: int
    verified_count: int
    fake_count: int
    context_mismatch_count: int
    
    results: List[VerificationResult] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """生成Markdown格式的报告"""
        lines = [
            "# CiteGuard 论文引用检查报告",
            f"\n生成时间: {self.timestamp}",
            f"\n## 概览",
            f"- 总引用数: {self.total_citations}",
            f"- 验证通过: {self.verified_count}",
            f"- 可能虚假: {self.fake_count}",
            f"- 上下文不匹配: {self.context_mismatch_count}",
            "\n---\n",
            "## 一、虚假论文核实结果\n"
        ]
        
        # 虚假论文部分
        fake_papers = [r for r in self.results if not r.is_verified]
        if fake_papers:
            for r in fake_papers:
                lines.append(f"### ❌ {r.cite_key}")
                lines.append(f"- **标题**: {r.original_entry.title}")
                lines.append(f"- **作者**: {r.original_entry.author}")
                lines.append(f"- **问题**: {r.verification_message}")
                lines.append("")
        else:
            lines.append("✅ 所有论文均验证通过，未发现虚假论文。\n")
        
        # 验证通过的论文
        lines.append("### 验证通过的论文\n")
        verified_papers = [r for r in self.results if r.is_verified]
        for r in verified_papers:
            doi_info = f" (DOI: {r.verified_info.doi})" if r.verified_info and r.verified_info.doi else ""
            lines.append(f"- ✅ **{r.cite_key}**: {r.original_entry.title[:60]}...{doi_info}")
        
        lines.append("\n---\n")
        lines.append("## 二、上下文匹配报告\n")
        
        # 上下文匹配部分（只检查验证通过的）
        for r in verified_papers:
            lines.append(f"### {r.cite_key}")
            lines.append(f"**论文标题**: {r.original_entry.title}\n")
            
            if not r.context_checks:
                lines.append("- 未在tex文件中找到引用\n")
                continue
            
            for i, check in enumerate(r.context_checks, 1):
                status = "✅" if check.get("is_match", True) else "⚠️"
                source_file = check.get('source_file', '')
                file_info = f", 文件: {source_file}" if source_file else ""
                lines.append(f"**引用位置 #{i}** (第{check.get('line_number', '?')}行, {check.get('section', '未知章节')}{file_info})")
                lines.append(f"- 状态: {status} {'匹配' if check.get('is_match', True) else '不匹配'}")
                lines.append(f"- 置信度: {check.get('confidence', 0):.0%}")
                lines.append(f"- 说明: {check.get('explanation', '')}")
                if check.get("suggestion"):
                    lines.append(f"- 建议: {check.get('suggestion')}")
                lines.append(f"- 引用上下文: \"{check.get('context', '')[:150]}...\"")
                lines.append("")
        
        lines.append("\n---\n")
        lines.append("## 三、修正后的BIB文件\n")
        lines.append("```bibtex")
        
        for r in self.results:
            if r.corrected_entry:
                lines.append(r.corrected_entry.to_bibtex())
            else:
                lines.append(r.original_entry.to_bibtex())
            lines.append("")
        
        lines.append("```")
        
        return "\n".join(lines)


class CiteGuardAgent:
    """CiteGuard Agent - 论文引用检查代理"""
    
    def __init__(self, api_key: str = None, use_mock: bool = False):
        """
        初始化Agent
        
        Args:
            api_key: 硅基流动API密钥
            use_mock: 是否使用模拟LLM（用于测试）
        """
        self.bib_parser = BibParser()
        self.paper_searcher = PaperSearcher()
        self.latex_parser = LatexParser()
        
        if use_mock:
            from .llm_client import MockLLMClient
            self.llm_client = MockLLMClient()
        else:
            self.llm_client = LLMClient(api_key=api_key)
        
        self.results: List[VerificationResult] = []
    
    def check_citations(
        self, 
        bib_file: str = None,
        tex_file: str = None,
        tex_files: List[str] = None,
        bib_content: str = None,
        tex_content: str = None,
        verbose: bool = True
    ) -> CheckReport:
        """
        执行完整的引用检查流程
        
        Args:
            bib_file: BIB文件路径
            tex_file: 单个TEX文件路径（向后兼容）
            tex_files: 多个TEX文件路径列表
            bib_content: BIB内容（如果不使用文件）
            tex_content: TEX内容（如果不使用文件）
            verbose: 是否输出详细信息
            
        Returns:
            CheckReport: 检查报告
        """
        self.results = []
        
        # 处理tex_file和tex_files的兼容性
        if tex_file and not tex_files:
            tex_files = [tex_file]
        
        # 1. 解析BIB文件
        if verbose:
            print("\n" + "=" * 60)
            print("步骤1: 解析BIB文件")
            print("=" * 60)
        
        if bib_file:
            bib_entries = self.bib_parser.parse_file(bib_file)
        else:
            bib_entries = self.bib_parser.parse_string(bib_content)
        
        if verbose:
            print(f"找到 {len(bib_entries)} 个引用条目")
        
        # 2. 解析TEX文件（如果提供）
        citations_in_tex = {}
        if tex_files or tex_content:
            if verbose:
                print("\n" + "=" * 60)
                print("步骤2: 解析TEX文件，提取引用上下文")
                print("=" * 60)
            
            if tex_files:
                # 解析多个tex文件并合并结果
                for tex_f in tex_files:
                    if verbose:
                        print(f"  解析: {tex_f}")
                    file_citations = self.latex_parser.parse_file(tex_f)
                    # 合并引用上下文，添加文件来源信息
                    for cite_key, contexts in file_citations.items():
                        # 为每个上下文添加文件来源
                        for ctx in contexts:
                            ctx.source_file = os.path.basename(tex_f)
                        if cite_key in citations_in_tex:
                            citations_in_tex[cite_key].extend(contexts)
                        else:
                            citations_in_tex[cite_key] = contexts
            else:
                citations_in_tex = self.latex_parser.parse_string(tex_content)
            
            if verbose:
                print(f"在TEX中找到 {len(citations_in_tex)} 个不同的引用")
        
        # 3. 逐一验证论文真实性
        if verbose:
            print("\n" + "=" * 60)
            print("步骤3: 验证论文真实性")
            print("=" * 60)
        
        verified_count = 0
        fake_count = 0
        
        for entry in bib_entries:
            if verbose:
                print(f"\n正在验证: {entry.cite_key}")
                print(f"  标题: {entry.title[:50]}...")
            
            # 搜索验证
            is_verified, paper_info, message = self.paper_searcher.verify_paper(
                title=entry.title,
                author=entry.author,
                year=entry.year
            )
            
            result = VerificationResult(
                cite_key=entry.cite_key,
                original_entry=entry,
                is_verified=is_verified,
                verification_message=message,
                verified_info=paper_info
            )
            
            if is_verified:
                verified_count += 1
                if verbose:
                    print(f"  ✅ {message}")
            else:
                fake_count += 1
                if verbose:
                    print(f"  ❌ {message}")
            
            self.results.append(result)
        
        # 4. 对验证通过的论文检查上下文匹配
        if verbose:
            print("\n" + "=" * 60)
            print("步骤4: 检查引用上下文匹配")
            print("=" * 60)
        
        context_mismatch_count = 0
        
        for result in self.results:
            if not result.is_verified:
                continue
            
            contexts = citations_in_tex.get(result.cite_key, [])
            if not contexts:
                if verbose:
                    print(f"\n{result.cite_key}: 未在TEX中找到引用")
                continue
            
            if verbose:
                print(f"\n检查 {result.cite_key} 的 {len(contexts)} 处引用...")
            
            # 获取摘要
            abstract = ""
            if result.verified_info:
                abstract = result.verified_info.abstract
            
            # 检查每处引用
            for ctx in contexts:
                match_result = self.llm_client.check_context_match(
                    paper_abstract=abstract,
                    citation_context=ctx.sentence,
                    paper_title=result.original_entry.title
                )
                
                check_info = {
                    "line_number": ctx.line_number,
                    "section": ctx.section,
                    "context": ctx.sentence,
                    "is_match": match_result.is_match,
                    "confidence": match_result.confidence,
                    "explanation": match_result.explanation,
                    "suggestion": match_result.suggestion,
                    "source_file": getattr(ctx, 'source_file', '')  # 来源文件
                }
                
                result.context_checks.append(check_info)
                
                if not match_result.is_match:
                    result.all_contexts_match = False
                    context_mismatch_count += 1
                
                if verbose:
                    status = "✅" if match_result.is_match else "⚠️"
                    file_info = f"[{ctx.source_file}] " if getattr(ctx, 'source_file', '') else ""
                    print(f"  {status} {file_info}第{ctx.line_number}行: {match_result.explanation[:50]}...")
        
        # 5. 修正BIB条目
        if verbose:
            print("\n" + "=" * 60)
            print("步骤5: 修正BIB条目")
            print("=" * 60)
        
        for result in self.results:
            if result.is_verified and result.verified_info:
                # 准备验证信息
                verified_info = {
                    "title": result.verified_info.title,
                    "authors": ", ".join(result.verified_info.authors) if result.verified_info.authors else "",
                    "year": result.verified_info.year,
                    "doi": result.verified_info.doi,
                    "venue": result.verified_info.venue,
                    "volume": result.verified_info.volume,
                    "pages": result.verified_info.pages,
                    "publisher": result.verified_info.publisher
                }
                
                correction = self.llm_client.correct_bib_entry(
                    original_bib=result.original_entry.to_bibtex(),
                    verified_info=verified_info,
                    entry_type=result.original_entry.entry_type
                )
                
                # 解析修正后的BIB
                corrected_entries = self.bib_parser.parse_string(correction.corrected_bib)
                if corrected_entries:
                    result.corrected_entry = corrected_entries[0]
                    result.corrections = correction.changes
                    
                    if verbose and correction.changes:
                        print(f"\n{result.cite_key}:")
                        for change in correction.changes:
                            print(f"  - {change}")
            else:
                # 未验证的保持原样
                result.corrected_entry = result.original_entry
        
        # 6. 生成报告
        report = CheckReport(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_citations=len(bib_entries),
            verified_count=verified_count,
            fake_count=fake_count,
            context_mismatch_count=context_mismatch_count,
            results=self.results
        )
        
        return report
    
    def export_corrected_bib(self, filepath: str):
        """导出修正后的BIB文件"""
        entries = []
        for result in self.results:
            if result.corrected_entry:
                entries.append(result.corrected_entry)
            else:
                entries.append(result.original_entry)
        
        self.bib_parser.export_to_file(filepath, entries)
    
    def export_report(self, filepath: str, report: CheckReport):
        """导出报告到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report.to_markdown())


# 测试代码
if __name__ == "__main__":
    # 测试数据
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

@article{fake2023paper,
  title={A completely fake paper that does not exist in any database},
  author={Fake, Author and Nobody, Someone},
  journal={Journal of Fake Research},
  volume={1},
  pages={1--10},
  year={2023}
}
"""
    
    test_tex = r"""
\documentclass{article}
\begin{document}

\section{Introduction}

Mobile edge computing (MEC) has emerged as a promising paradigm to address the increasing demand for low-latency applications \cite{qian2022game}. Deep reinforcement learning approaches have been applied to optimize resource allocation in connected vehicles \cite{he2017integrated}.

\section{Related Work}

Qian et al. proposed a game theory based D2D collaborative offloading scheme \cite{qian2022game}, which demonstrated significant improvements in workflow execution time.

He et al. \cite{he2017integrated} proposed a deep reinforcement learning approach for connected vehicles.

Some fake research claims extraordinary results \cite{fake2023paper}.

\end{document}
"""
    
    print("=" * 60)
    print("CiteGuard Agent 完整测试")
    print("=" * 60)
    
    # 使用模拟LLM进行测试
    agent = CiteGuardAgent(use_mock=True)
    
    # 执行检查
    report = agent.check_citations(
        bib_content=test_bib,
        tex_content=test_tex,
        verbose=True
    )
    
    # 输出报告
    print("\n" + "=" * 60)
    print("生成的报告")
    print("=" * 60)
    print(report.to_markdown())
