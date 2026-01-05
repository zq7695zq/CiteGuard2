"""
LaTeX引用提取模块
从tex文件中提取引用位置和上下文
"""
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class CitationContext:
    """引用上下文"""
    cite_key: str           # 引用键
    context: str            # 上下文文本
    sentence: str           # 包含引用的句子
    paragraph: str          # 包含引用的段落
    section: str            # 所在章节
    line_number: int        # 行号
    position: int           # 在文件中的位置
    source_file: str = ""   # 来源文件名（支持多文件时使用）


class LatexParser:
    """LaTeX文件解析器"""
    
    def __init__(self):
        self.content = ""
        self.citations: Dict[str, List[CitationContext]] = {}
    
    def parse_file(self, filepath: str) -> Dict[str, List[CitationContext]]:
        """解析tex文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.content = f.read()
        return self.parse_string(self.content)
    
    def parse_string(self, content: str) -> Dict[str, List[CitationContext]]:
        """解析tex字符串"""
        self.content = content
        self.citations = {}
        
        # 移除注释
        content_no_comments = self._remove_comments(content)
        
        # 查找所有引用
        # 支持多种引用格式: \cite{}, \citep{}, \citet{}, \citealp{}, etc.
        cite_patterns = [
            r'\\cite\{([^}]+)\}',
            r'\\citep\{([^}]+)\}',
            r'\\citet\{([^}]+)\}',
            r'\\citealp\{([^}]+)\}',
            r'\\citealt\{([^}]+)\}',
            r'\\citeauthor\{([^}]+)\}',
            r'\\citeyear\{([^}]+)\}',
            r'\\parencite\{([^}]+)\}',
            r'\\textcite\{([^}]+)\}',
            r'\\autocite\{([^}]+)\}',
        ]
        
        combined_pattern = '|'.join(f'({p})' for p in cite_patterns)
        
        for match in re.finditer(combined_pattern, content_no_comments):
            # 获取匹配的引用键
            full_match = match.group(0)
            # 提取大括号内的内容
            keys_match = re.search(r'\{([^}]+)\}', full_match)
            if not keys_match:
                continue
            
            keys_str = keys_match.group(1)
            # 处理多个引用键，如 \cite{key1, key2}
            cite_keys = [k.strip() for k in keys_str.split(',')]
            
            for cite_key in cite_keys:
                if not cite_key:
                    continue
                    
                # 获取上下文
                context = self._extract_context(content_no_comments, match.start(), cite_key)
                
                if cite_key not in self.citations:
                    self.citations[cite_key] = []
                self.citations[cite_key].append(context)
        
        return self.citations
    
    def _remove_comments(self, content: str) -> str:
        """移除LaTeX注释"""
        # 移除行注释（%开头的内容）
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 查找第一个未转义的%
            result = []
            i = 0
            while i < len(line):
                if line[i] == '%' and (i == 0 or line[i-1] != '\\'):
                    break
                result.append(line[i])
                i += 1
            cleaned_lines.append(''.join(result))
        return '\n'.join(cleaned_lines)
    
    def _extract_context(self, content: str, position: int, cite_key: str) -> CitationContext:
        """提取引用的上下文"""
        # 计算行号
        line_number = content[:position].count('\n') + 1
        
        # 提取句子（从上一个句号到下一个句号）
        sentence = self._extract_sentence(content, position)
        
        # 提取段落（从上一个空行到下一个空行）
        paragraph = self._extract_paragraph(content, position)
        
        # 提取章节标题
        section = self._extract_section(content, position)
        
        # 生成上下文（句子前后各扩展一些内容）
        context = self._extract_surrounding_context(content, position, window=500)
        
        return CitationContext(
            cite_key=cite_key,
            context=context,
            sentence=sentence,
            paragraph=paragraph,
            section=section,
            line_number=line_number,
            position=position
        )
    
    def _extract_sentence(self, content: str, position: int) -> str:
        """提取包含引用的句子"""
        # 句子结束符
        sentence_ends = '.!?'
        
        # 向前找句子开始
        start = position
        while start > 0:
            if content[start-1] in sentence_ends and start > 1:
                # 检查是否是缩写（如 e.g., i.e.）
                if not self._is_abbreviation(content, start-1):
                    break
            start -= 1
        
        # 向后找句子结束
        end = position
        while end < len(content) - 1:
            if content[end] in sentence_ends:
                if not self._is_abbreviation(content, end):
                    end += 1
                    break
            end += 1
        
        sentence = content[start:end].strip()
        # 清理LaTeX命令
        sentence = self._clean_latex(sentence)
        return sentence
    
    def _extract_paragraph(self, content: str, position: int) -> str:
        """提取包含引用的段落"""
        # 向前找段落开始（连续两个换行）
        start = position
        while start > 1:
            if content[start-2:start] == '\n\n':
                break
            start -= 1
        
        # 向后找段落结束
        end = position
        while end < len(content) - 1:
            if content[end:end+2] == '\n\n':
                break
            end += 1
        
        paragraph = content[start:end].strip()
        # 清理LaTeX命令
        paragraph = self._clean_latex(paragraph)
        return paragraph
    
    def _extract_section(self, content: str, position: int) -> str:
        """提取当前章节标题"""
        # 查找位置之前最近的section/subsection命令
        section_pattern = r'\\(section|subsection|subsubsection|chapter)\*?\{([^}]+)\}'
        
        # 只搜索position之前的内容
        content_before = content[:position]
        matches = list(re.finditer(section_pattern, content_before))
        
        if matches:
            last_match = matches[-1]
            return last_match.group(2)
        
        return ""
    
    def _extract_surrounding_context(self, content: str, position: int, window: int = 500) -> str:
        """提取引用周围的上下文"""
        start = max(0, position - window // 2)
        end = min(len(content), position + window // 2)
        
        # 调整到单词边界
        while start > 0 and content[start] not in ' \n\t':
            start -= 1
        while end < len(content) and content[end] not in ' \n\t':
            end += 1
        
        context = content[start:end].strip()
        # 清理LaTeX命令
        context = self._clean_latex(context)
        return context
    
    def _is_abbreviation(self, content: str, position: int) -> bool:
        """检查句号是否属于缩写"""
        abbreviations = ['e.g.', 'i.e.', 'et al.', 'vs.', 'etc.', 'Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.']
        
        # 获取句号前的几个字符
        start = max(0, position - 6)
        text_before = content[start:position+1].lower()
        
        for abbr in abbreviations:
            if text_before.endswith(abbr.lower()):
                return True
        
        return False
    
    def _clean_latex(self, text: str) -> str:
        """清理LaTeX命令，保留可读文本"""
        # 移除引用命令（保留引用标记以便识别）
        text = re.sub(r'\\cite[a-z]*\{([^}]+)\}', r'[CITE:\1]', text)
        
        # 移除常见格式命令
        text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\textit\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\emph\{([^}]+)\}', r'\1', text)
        text = re.sub(r'\\underline\{([^}]+)\}', r'\1', text)
        
        # 移除section命令
        text = re.sub(r'\\(sub)*section\*?\{([^}]+)\}', r'\2', text)
        
        # 移除其他常见命令
        text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\[a-zA-Z]+', '', text)
        
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def get_all_cite_keys(self) -> List[str]:
        """获取所有引用键"""
        return list(self.citations.keys())
    
    def get_contexts_for_key(self, cite_key: str) -> List[CitationContext]:
        """获取指定引用键的所有上下文"""
        return self.citations.get(cite_key, [])


# 测试代码
if __name__ == "__main__":
    test_tex = r"""
\documentclass{article}
\begin{document}

\section{Introduction}

Mobile edge computing (MEC) has emerged as a promising paradigm to address the increasing demand for low-latency and computation-intensive applications \cite{qian2022game}. Recent studies have shown that deep reinforcement learning can be effectively applied to optimize resource allocation in connected vehicles \cite{he2017integrated}.

\section{Related Work}

\subsection{Edge Computing}

Various game-theoretic approaches have been proposed for task offloading in MEC environments. Qian et al. proposed a game theory based D2D collaborative offloading scheme \cite{qian2022game}, which demonstrated significant improvements in workflow execution time.

\subsection{Deep Learning for Vehicles}

The integration of networking, caching, and computing has been studied in the context of connected vehicles. He et al. \cite{he2017integrated} proposed a deep reinforcement learning approach that jointly optimizes these three aspects.

\section{Methodology}

Our approach builds upon the insights from both game-theoretic \cite{qian2022game} and deep learning methods \cite{he2017integrated} to propose a hybrid solution.

\end{document}
"""
    
    parser = LatexParser()
    citations = parser.parse_string(test_tex)
    
    print(f"找到 {len(citations)} 个不同的引用键:\n")
    
    for cite_key, contexts in citations.items():
        print(f"=" * 60)
        print(f"引用键: {cite_key}")
        print(f"出现次数: {len(contexts)}")
        print(f"=" * 60)
        
        for i, ctx in enumerate(contexts, 1):
            print(f"\n--- 引用 #{i} ---")
            print(f"行号: {ctx.line_number}")
            print(f"章节: {ctx.section}")
            print(f"句子: {ctx.sentence[:100]}..." if len(ctx.sentence) > 100 else f"句子: {ctx.sentence}")
        print()
