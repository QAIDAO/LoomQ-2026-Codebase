from starter_kit.adapter import agent_chat

# 测试1：后端推荐
print("=== 测试后端推荐 ===")
response1 = agent_chat("我需要运行一个30比特电路，选哪个平台？")
print(response1)
print("\n" + "="*50 + "\n")

# 测试2：生成贝尔态
print("=== 测试生成贝尔态 ===")
response2 = agent_chat("生成一个贝尔态，并测量两个比特。")
print(response2)