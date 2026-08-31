# test_agent.py
from starter_kit.adapter import agent_chat

if __name__ == "__main__":
    print("🧪 测试 L2 Agent 自愈闭环...")
    # 故意给一个复杂点的 GHZ 态描述
    user_input = "生成一个3比特的GHZ纠缠态，并测量所有比特。"
    print(f"👤 用户: {user_input}\n")
    
    result_qasm = agent_chat(user_input)
    
    print("🤖 Agent 返回的 QASM 代码：")
    print("--------------------------------------------------")
    print(result_qasm)
    print("--------------------------------------------------")
    print("✅ 测试完成。请检查上方代码是否符合预期。")