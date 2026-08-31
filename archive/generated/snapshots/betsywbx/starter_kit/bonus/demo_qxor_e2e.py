"""
端到端测试: 用 qxor 实现一个真实的 QEC 奇偶校验修正判断程序。

场景: 两个稳定子测量位 c[0], c[1] 已经通过 classical 块的映射进了 x10, x11。
根据这两位的奇偶校验(XOR)结果决定是否需要施加修正:
  - 校验为0(两次测量一致) -> 无需修正, x2 = 0
  - 校验为1(两次测量不一致) -> 需要修正, x2 = 1

这个逻辑用题面给定的6条基础指令(li/add/sub/addi/beq/bne/j)做不到——
没有任何组合能从"加减法+相等比较"推出"按位异或"的语义,这正是qxor存在的意义。
"""

from riscv_emulator_ext import TinyRISCVEmulatorExt

QEC_PARITY_CHECK_ASM = """
qxor x1, x10, x11      ; x1 = c[0] XOR c[1] (奇偶校验结果)
beq x1, x0, NO_ERROR    ; 校验为0(x0恒为0) -> 无需修正
li x2, 1                ; 校验为1 -> 标记需要修正
j END
NO_ERROR:
li x2, 0
END:
"""


def run_case(c0: int, c1: int) -> dict:
    emu = TinyRISCVEmulatorExt()
    emu.load_program(QEC_PARITY_CHECK_ASM)
    emu.set_register("x10", c0)
    emu.set_register("x11", c1)
    return emu.execute()


if __name__ == "__main__":
    # 穷举4种测量值组合,验证奇偶校验语义完全正确
    test_cases = [
        (0, 0, 0),  # 一致 -> 无需修正
        (0, 1, 1),  # 不一致 -> 需要修正
        (1, 0, 1),  # 不一致 -> 需要修正
        (1, 1, 0),  # 一致 -> 无需修正
    ]

    all_passed = True
    for c0, c1, expected_x2 in test_cases:
        result = run_case(c0, c1)
        actual_x2 = result.get("x2", 0)
        status = "PASS" if actual_x2 == expected_x2 else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"c[0]={c0}, c[1]={c1}  ->  x2(需要修正)={actual_x2}  "
              f"期望={expected_x2}  [{status}]  完整寄存器状态={result}")

    print()
    if all_passed:
        print("✅ 全部4种测量值组合通过 —— qxor 语义在端到端场景中验证正确")
    else:
        print("❌ 存在失败用例")
        raise SystemExit(1)