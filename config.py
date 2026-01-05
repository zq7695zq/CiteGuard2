"""
CiteGuard 配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 硅基流动API配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-dwxsrbmfmsjemoazxuodmnjtlbspvijxdvdlsqrpeiaekakq")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3.2"  # 可以换成其他模型

# CrossRef API配置
CROSSREF_API_URL = "https://api.crossref.org/works"
CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", "ayanami1999@qq.com")  # 礼貌池需要邮箱

# Semantic Scholar API配置
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")  # 可选

# 请求配置
REQUEST_TIMEOUT = 30
REQUEST_RETRY = 3
REQUEST_DELAY = 1.0  # API请求间隔，避免限流
