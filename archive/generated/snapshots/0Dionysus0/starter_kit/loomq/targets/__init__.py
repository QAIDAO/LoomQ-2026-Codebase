"""本模块主要针对不同的量子计算硬件后端（backend）将IR导出转换为对应的文本代码，并负责后续的运行调度和执行。

该目录下的每一个后端模块（e.g. spinq.py/originq.py/braket.py都严格表现为下列三者:
    BACKEND_ID: str
        后端的唯一标准识别符，必须与backend_capabilities.json配置文件中定义的后端名称保持一致
    emit(circuit: Circuit) -> str
        转译函数，接收一个Circuit，将其转换为target后端可识别的文本代码
    execute(circuit: Circuit, shots: int) -> dict
        任务执行函数， 接收量子电路与shots（采样重复次数）并在对应的硬件或者模拟器上运行后返回符合Unified Result Schema的result dictionary
        (结果字典存储key-value pairs，在量子电路中封装execute()的运行结果，包含测量统计，执行状态和元数据。）

设计理念与架构优势：
     这部分代码中没有包含针对特定硬件目标的量子门分解和scoring logic，从而实现parsing、IR、simulation的跨后端共享。
     系统的中间层高度统一，因此替换或新增后端都只需要增加一对emit()/execute()函数，无需大幅修改代码，从而实现与硬件解耦。
"""

from . import braket, originq, spinq

TARGETS = {"spinq": spinq, "originq": originq, "braket": braket}
