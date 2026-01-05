"""
CiteGuard - 论文引用检查Agent
"""
from .agent import CiteGuardAgent
from .bib_parser import BibParser
from .paper_search import PaperSearcher
from .latex_parser import LatexParser
from .llm_client import LLMClient

__version__ = "1.0.0"
__all__ = ["CiteGuardAgent", "BibParser", "PaperSearcher", "LatexParser", "LLMClient"]
