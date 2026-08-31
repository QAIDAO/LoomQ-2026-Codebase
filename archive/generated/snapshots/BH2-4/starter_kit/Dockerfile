FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# pyqpanda 依赖 libcurl.so.4
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/submission
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 基线自检：离线可完整验证 L1（三目标）+ L3。
# L2 对话需 LOOMQ_LLM_* 环境变量（正式评测由组委会注入），此处不阻塞基线验证。
CMD ["sh", "-c", "python evaluator.py --level l1 --target spinq,originq,braket --json-out /tmp/loomq-l1.json && python evaluator.py --level l3 --json-out /tmp/loomq-l3.json && echo '[baseline] L1(3 targets)+L3 passed; L2 requires injected LOOMQ_LLM_* env'"]
