#!/usr/bin/env python3
"""从 .env 文件里补上模型服务配置

**为什么需要这个文件。**

赛题硬性要求：源码里不得出现任何服务地址、密钥或模型名，配置只能从环境变量读。
这条要求本身是对的，但它带来一个副作用——每次运行前都得先手动把变量塞进环境：

    set -a && . ./.env && set +a && python ...

这串东西对使用者（包括评委）是纯粹的噪音，而且很容易漏掉，
漏掉之后看到的是"缺少环境变量"，看起来像程序坏了。

所以这里做一件很小的事：**启动时去几个约定的位置找 .env，把缺的变量补上。**
硬编码的是"去哪儿找文件"，不是配置本身——文件不在仓库里，值也不在源码里，
既不违反那条要求，又让"一条命令跑通"成立。

两条安全约束：

- **已经在环境里的值优先。**正式评测时组委会直接注入环境变量，
  绝不能被开发机上遗留的 .env 盖掉。
- **只读 LOOMQ_ 开头的键**，其余一律忽略；任何时候不打印值。
  （前缀原本是 LOOMQ_LLM_，接真机时放宽到 LOOMQ_，好让 LOOMQ_ORIGINQ_TOKEN
  走同一条路——仍然是白名单，不会把 .env 里别的东西读进环境。）
"""

import os

ENV_KEYS = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")

# 真机凭证。与模型服务的三个变量分开，因为它们的用途和泄露后果都不同。
HARDWARE_KEY = "LOOMQ_ORIGINQ_TOKEN"

_PREFIX = "LOOMQ_"

_HERE = os.path.dirname(os.path.abspath(__file__))
_STARTER_KIT = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_STARTER_KIT)


def search_paths():
    """按顺序去哪儿找 .env，找到第一个能读出东西的就停。

    仓库外的兄弟目录排在仓库内之前是**故意的**：本仓库是公开 fork，
    密钥放在仓库外面才不会有哪天被 commit 进去的风险。
    （.gitignore 也拦了 .env，但少一条依赖总是好的。）
    """
    return tuple(
        path
        for path in (
            os.environ.get("LOOMQ_ENV_FILE"),
            os.path.join(os.getcwd(), ".env"),
            os.path.join(_REPO_ROOT, ".env"),
            os.path.join(os.path.dirname(_REPO_ROOT), ".env"),
            os.path.expanduser("~/.loomq.env"),
        )
        if path
    )


def load():
    """补上缺失的 LOOMQ_LLM_* 变量。返回实际读取的文件路径，没读到返回 None。"""
    for path in search_paths():
        if not os.path.isfile(path):
            continue
        loaded = False
        try:
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw or raw.startswith("#") or "=" not in raw:
                        continue
                    key, value = raw.split("=", 1)
                    key = key.strip()
                    if key.startswith(_PREFIX) and not os.environ.get(key):
                        os.environ[key] = value.strip().strip('"').strip("'")
                        loaded = True
        except OSError:
            continue
        if loaded:
            return path
    return None


def missing_keys():
    """还差哪几个变量。空列表表示配置齐了。"""
    return [key for key in ENV_KEYS if not os.environ.get(key)]


def require(program):
    """给命令行工具用：加载配置，齐了就返回 True，不齐就打印怎么配再返回 False。

    不打印任何值，只打印键名和候选路径。
    """
    source = load()
    missing = missing_keys()
    if not missing:
        if source:
            print("（已从 %s 读取配置，不打印内容）" % source)
        return True

    print("跑不了 %s：模型服务还没配好。" % program)
    print("缺少：%s" % "、".join(missing))
    print("\n最省事的做法：在下面任意一个位置建一个名叫 .env 的文件——\n")
    for path in search_paths():
        print("    %s" % path)
    print("\n内容三行，换成你自己的服务、密钥和模型名：\n")
    for key in ENV_KEYS:
        print("    %s=<你的值>" % key)
    print("\n（本项目不硬编码任何服务地址、密钥或模型名——这是赛题的硬性要求，")
    print("  也意味着换成任何 OpenAI 协议的服务都不用改一行代码。）")
    return False
