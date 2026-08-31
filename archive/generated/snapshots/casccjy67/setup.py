"""一键安装依赖 + 验证 SDK 可用性"""
import subprocess
import sys
import os

PY312 = r"C:\Users\cjy\AppData\Local\Programs\Python\Python312\python.exe"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_cmd(cmd, timeout=600):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.stdout:
        print(result.stdout[-500:])
    if result.stderr:
        print("STDERR:", result.stderr[-500:])
    return result.returncode

def main():
    print("=" * 50)
    print("LoomQ 环境安装脚本")
    print("=" * 50)

    # 1. 安装 Braket SDK
    print("\n[1/3] 安装 amazon-braket-sdk...")
    code = run_cmd(f'"{PY312}" -m pip install amazon-braket-sdk', timeout=600)

    # 2. 安装 openai
    print("\n[2/3] 安装 openai...")
    code2 = run_cmd(f'"{PY312}" -m pip install openai pyyaml', timeout=120)

    # 3. 验证
    print("\n[3/3] 验证安装...")
    verify_script = """
import sys
print(f"Python: {sys.version}")

try:
    from braket.circuits import Circuit
    from braket.devices import LocalSimulator
    print("Braket: OK")
except ImportError as e:
    print(f"Braket: MISSING ({e})")

try:
    import openai
    print(f"OpenAI: OK ({openai.__version__})")
except ImportError:
    print("OpenAI: MISSING")

try:
    import yaml
    print(f"PyYAML: OK")
except ImportError:
    print("PyYAML: MISSING")
"""
    run_cmd(f'"{PY312}" -c "{verify_script}"', timeout=30)

    # 4. 跑测试
    print("\n[4/4] 运行测试套件...")
    run_cmd(f'cd /d "{PROJECT_DIR}" && "{PY312}" -m starter_kit.tests.test_transpile', timeout=60)

if __name__ == "__main__":
    main()
