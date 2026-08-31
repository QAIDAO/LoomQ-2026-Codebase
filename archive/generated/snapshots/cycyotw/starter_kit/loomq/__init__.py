"""LoomQ 通用中间层实现（洽道量子 LoomQ-2026 赛题）。

子模块一览：
- hybrid_lexer   : 把经典控制块的文本切成词
- hybrid_parser  : 把词组装成语法树
- hybrid_codegen : 把语法树翻译成 RISC-V 汇编
- hybrid_interp  : 直接照语法树算答案（参考实现，只用于自测比对）
- hybrid         : 总装，对外提供 compile_hybrid()
"""

__all__ = [
    "hybrid",
    "hybrid_codegen",
    "hybrid_interp",
    "hybrid_lexer",
    "hybrid_parser",
]
