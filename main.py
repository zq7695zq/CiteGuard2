#!/usr/bin/env python
"""
CiteGuard - 论文引用检查Agent
主入口文件

使用方法:
    python main.py --bib paper.bib --tex paper.tex
    python main.py --bib paper.bib --tex paper.tex --output report.md
    python main.py --bib paper.bib  # 只检查论文真实性
"""
import argparse
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from citeguard.agent import CiteGuardAgent


def main():
    parser = argparse.ArgumentParser(
        description='CiteGuard - 论文引用检查Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py --bib refs.bib --tex paper.tex
    python main.py --bib refs.bib --tex paper.tex --output report.md
    python main.py --bib refs.bib --mock  # 使用模拟LLM测试
        """
    )
    
    parser.add_argument(
        '--bib', '-b',
        required=True,
        help='BIB文件路径'
    )
    
    parser.add_argument(
        '--tex', '-t',
        nargs='+',
        help='TEX文件路径，支持多个文件（可选，用于上下文检查）'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='citeguard_report.md',
        help='报告输出路径（默认: citeguard_report.md）'
    )
    
    parser.add_argument(
        '--output-bib',
        default='corrected.bib',
        help='修正后的BIB文件输出路径（默认: corrected.bib）'
    )
    
    parser.add_argument(
        '--api-key', '-k',
        help='硅基流动API密钥（也可通过环境变量SILICONFLOW_API_KEY设置）'
    )
    
    parser.add_argument(
        '--mock', '-m',
        action='store_true',
        help='使用模拟LLM（用于测试）'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='安静模式，减少输出'
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.bib):
        print(f"错误: BIB文件不存在: {args.bib}")
        sys.exit(1)
    
    if args.tex:
        for tex_file in args.tex:
            if not os.path.exists(tex_file):
                print(f"错误: TEX文件不存在: {tex_file}")
                sys.exit(1)
    
    # 创建Agent
    agent = CiteGuardAgent(
        api_key=args.api_key,
        use_mock=args.mock
    )
    
    # 执行检查
    print("\n" + "=" * 60)
    print("🔍 CiteGuard 论文引用检查Agent")
    print("=" * 60)
    
    report = agent.check_citations(
        bib_file=args.bib,
        tex_files=args.tex,
        verbose=not args.quiet
    )
    
    # 输出报告
    agent.export_report(args.output, report)
    print(f"\n📄 报告已保存到: {args.output}")
    
    # 输出修正后的BIB
    agent.export_corrected_bib(args.output_bib)
    print(f"📚 修正后的BIB已保存到: {args.output_bib}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 检查摘要")
    print("=" * 60)
    print(f"  总引用数: {report.total_citations}")
    print(f"  验证通过: {report.verified_count}")
    print(f"  可能虚假: {report.fake_count}")
    print(f"  上下文不匹配: {report.context_mismatch_count}")
    
    if report.fake_count > 0:
        print("\n⚠️  警告: 发现可能的虚假论文！请查看报告了解详情。")
    
    if report.context_mismatch_count > 0:
        print("\n⚠️  警告: 发现引用上下文不匹配！请查看报告了解详情。")
    
    print("\n✅ 检查完成！")


if __name__ == "__main__":
    main()
