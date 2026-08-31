#!/usr/bin/env python3
"""
LoomQ 可视化示例 - 展示量子电路执行过程
"""
import sys
sys.path.insert(0, ".")

from adapter import run, transpile
import json


def print_banner(text):
    """打印带边框的标题"""
    width = len(text) + 4
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n")


def visualize_counts(counts, shots):
    """可视化测量结果分布"""
    max_count = max(counts.values()) if counts else 1
    bar_width = 50

    print("测量结果分布：")
    print("-" * 60)
    for state, count in sorted(counts.items()):
        percentage = (count / shots) * 100
        bar_len = int((count / max_count) * bar_width)
        bar = "█" * bar_len
        print(f"|{state}⟩  {bar:<{bar_width}} {count:4d} ({percentage:5.1f}%)")
    print("-" * 60)
    print(f"总测量次数: {shots}")


def demo_bell_state():
    """演示贝尔态"""
    print_banner("示例1：贝尔态（Bell State）")

    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

    print("量子电路：")
    print("  q[0] --H--●---M")
    print("            |   |")
    print("  q[1] ----X---M")
    print()

    print("说明：")
    print("  1. H门：将q[0]变成叠加态 (|0⟩+|1⟩)/√2")
    print("  2. CX门：q[0]控制q[1]，创建纠缠")
    print("  3. 结果：两个量子比特完全关联")
    print()

    result = run(qasm, "spinq", shots=1000)
    visualize_counts(result["counts"], result["shots"])

    print("\n💡 解读：只有|00⟩和|11⟩出现，说明两个量子比特完全纠缠！")


def demo_ghz_state():
    """演示GHZ态"""
    print_banner("示例2：GHZ态（3比特纠缠）")

    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[0], q[2];
measure q -> c;
"""

    print("量子电路：")
    print("  q[0] --H--●---●---M")
    print("            |   |   |")
    print("  q[1] ----X---|---M")
    print("                |   |")
    print("  q[2] --------X---M")
    print()

    result = run(qasm, "originq", shots=1000)
    visualize_counts(result["counts"], result["shots"])

    print("\n💡 解读：3个量子比特同时纠缠，要么全0要么全1！")


def demo_superposition():
    """演示叠加态"""
    print_banner("示例3：均匀叠加（Uniform Superposition）")

    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
measure q -> c;
"""

    print("量子电路：")
    print("  q[0] --H---M")
    print("  q[1] --H---M")
    print("  q[2] --H---M")
    print()

    result = run(qasm, "braket", shots=1000)
    visualize_counts(result["counts"], result["shots"])

    print("\n💡 解读：每个量子比特独立叠加，8种状态均等出现！")


def demo_platform_comparison():
    """演示跨平台统一接口"""
    print_banner("示例4：跨平台统一接口")

    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

    print("同一份量子电路，在三个平台上运行：\n")

    platforms = [
        ("spinq", "量旋 SpinQit"),
        ("originq", "本源 pyqpanda"),
        ("braket", "AWS Braket")
    ]

    for target, name in platforms:
        result = run(qasm, target, shots=100)
        total_00 = result["counts"].get("00", 0)
        total_11 = result["counts"].get("11", 0)
        print(f"📊 {name:20s}: |00⟩={total_00:3d}, |11⟩={total_11:3d}")

    print("\n💡 统一的接口 + 统一的结果格式 = 真正的平台无关！")


def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║          LoomQ 量子接入平权计划 - 可视化演示                 ║
║                                                            ║
║   让不懂"黑话"的人，也能指挥最前沿的算力                      ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")

    demos = [
        ("1", "贝尔态（2比特纠缠）", demo_bell_state),
        ("2", "GHZ态（3比特纠缠）", demo_ghz_state),
        ("3", "均匀叠加（独立量子比特）", demo_superposition),
        ("4", "跨平台对比", demo_platform_comparison),
    ]

    if len(sys.argv) > 1:
        # 命令行参数指定示例编号
        demo_num = sys.argv[1]
        for num, name, func in demos:
            if num == demo_num:
                func()
                return
        print(f"错误：未知的示例编号 '{demo_num}'")
        print("可用选项: 1, 2, 3, 4")
    else:
        # 交互式菜单
        print("请选择要运行的示例：")
        for num, name, _ in demos:
            print(f"  {num}. {name}")
        print("  a. 运行全部")
        print("  q. 退出")

        try:
            choice = input("\n你的选择: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return

        if choice == "q":
            print("再见！")
            return
        elif choice == "a":
            for num, name, func in demos:
                func()
                try:
                    input("\n按Enter继续下一个示例...")
                except (EOFError, KeyboardInterrupt):
                    return
        else:
            for num, name, func in demos:
                if num == choice:
                    func()
                    return
            print("无效的选择！")


if __name__ == "__main__":
    main()
