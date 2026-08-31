#!/usr/bin/env python3
"""Hybrid-QASM 经典控制块 · 分词器（编译器第一步）

干什么：把一段源码文本切成一串"词"。

    "r1 = r1 + 5;"  ->  [r1] [=] [r1] [+] [5] [;]

为什么要单独一步：后面的语法分析只想关心"词和词的关系"，
不想再操心空格、换行、注释这些排版问题。分词器把这些噪音一次性清掉。

只认识经典块用得到的东西：
- 整数              123
- 名字              r1..r9 / c / if / else
- 运算符            +  -  ==  !=  =
- 标点              (  )  {  }  [  ]  ;  ,
- 注释              // 行尾   # 行尾   /* 块 */    （全部丢弃）
"""

from collections import namedtuple

# kind 取值：num（整数） / name（标识符或关键字） / op（运算符） / punct（标点） / eof（结束）
Token = namedtuple("Token", "kind text line col")

_TWO_CHAR_OPS = ("==", "!=")
_ONE_CHAR_OPS = "+-="
_PUNCTUATION = "(){}[];,"
_NAME_START = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_NAME_BODY = _NAME_START + "0123456789"
_DIGITS = "0123456789"


class HybridSyntaxError(ValueError):
    """经典块语法错误。消息里带行号，方便使用者自己定位。"""


def tokenize(text):
    """把 text 切成 Token 列表，末尾附一个 eof。

    text : str  经典块 `classical { ... }` 花括号里面的内容
    返回 : list[Token]
    """
    tokens = []
    i = 0
    n = len(text)
    line = 1
    line_start = 0

    def col_of(pos):
        return pos - line_start + 1

    while i < n:
        ch = text[i]

        # ---- 换行与空白 ----
        if ch == "\n":
            line += 1
            i += 1
            line_start = i
            continue
        if ch in " \t\r\f\v":
            i += 1
            continue

        # ---- 注释：// 到行尾、# 到行尾、/* ... */ ----
        if text.startswith("//", i) or ch == "#":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise HybridSyntaxError("第 %d 行：块注释 /* 没有闭合" % line)
            line += text.count("\n", i, end)
            last_nl = text.rfind("\n", i, end)
            if last_nl >= 0:
                line_start = last_nl + 1
            i = end + 2
            continue

        # ---- 整数 ----
        if ch in _DIGITS:
            j = i
            while j < n and text[j] in _DIGITS:
                j += 1
            tokens.append(Token("num", text[i:j], line, col_of(i)))
            i = j
            continue

        # ---- 名字（标识符 / 关键字）----
        if ch in _NAME_START:
            j = i
            while j < n and text[j] in _NAME_BODY:
                j += 1
            tokens.append(Token("name", text[i:j], line, col_of(i)))
            i = j
            continue

        # ---- 双字符运算符（必须先于单字符判断）----
        two = text[i : i + 2]
        if two in _TWO_CHAR_OPS:
            tokens.append(Token("op", two, line, col_of(i)))
            i += 2
            continue

        # ---- 单字符运算符 ----
        if ch in _ONE_CHAR_OPS:
            tokens.append(Token("op", ch, line, col_of(i)))
            i += 1
            continue

        # ---- 标点 ----
        if ch in _PUNCTUATION:
            tokens.append(Token("punct", ch, line, col_of(i)))
            i += 1
            continue

        raise HybridSyntaxError(
            "第 %d 行第 %d 列：经典块里出现了无法识别的字符 %r" % (line, col_of(i), ch)
        )

    tokens.append(Token("eof", "", line, col_of(i)))
    return tokens
