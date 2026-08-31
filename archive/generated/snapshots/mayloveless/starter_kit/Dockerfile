FROM node:22-bookworm-slim AS web-builder

WORKDIR /workspace/web

COPY web/package.json web/pnpm-lock.yaml ./

RUN corepack enable && pnpm install --frozen-lockfile

COPY web/ ./

RUN pnpm build


FROM python:3.10-slim-bookworm

ARG DEBIAN_MIRROR=https://mirrors.aliyun.com
ARG PYPI_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/submission

COPY requirements.txt requirements-spinq.txt requirements-spinq-cloud.txt requirements-originq.txt ./

# pyQPanda 的 manylinux wheel 在 slim 镜像中仍需要 libcurl.so.4。
# 默认使用国内 HTTPS 镜像；构建参数仍可切回官方源，并保留有限重试。
RUN sed -i \
       -e "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" \
       -e "s|https://deb.debian.org|${DEBIAN_MIRROR}|g" \
       /etc/apt/sources.list.d/debian.sources \
    && set -eux; \
       apt_updated=0; \
       for attempt in 1 2 3 4 5; do \
           if apt-get update -o Acquire::Retries=5; then \
               apt_updated=1; \
               break; \
           fi; \
           rm -rf /var/lib/apt/lists/*; \
           sleep $((attempt * 2)); \
       done; \
       test "$apt_updated" -eq 1; \
       apt-get install -y --no-install-recommends -o Acquire::Retries=5 libcurl4; \
       rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
       --index-url "${PYPI_INDEX_URL}" \
       --timeout 300 --retries 10 \
       -r requirements.txt

# SpinQ Cloud SDK 固定 ANTLR 4.9.2，而 Braket verifier 需要 4.13.2，必须隔离解释器。
# 账号、私钥和真机后端仅在 docker run 时通过环境变量/挂载提供，绝不进入镜像层。
RUN python -m venv /opt/spinq-cloud-venv \
    && /opt/spinq-cloud-venv/bin/pip install --no-cache-dir \
       --index-url "${PYPI_INDEX_URL}" \
       --timeout 300 --retries 10 \
       -r requirements-spinq-cloud.txt \
    && /opt/spinq-cloud-venv/bin/python -c "import spinqit_mcp_tools; from Crypto.PublicKey import RSA"

# SpinQit 与 Braket 依赖不同 ANTLR 版本，使用独立虚拟环境。
# SpinQit 未区分 CPU/GPU 的 torch 依赖；评测只使用本地模拟器，直接安装官方 CPU wheel，避免 CUDA/cuDNN/Triton 和额外索引解析问题。
RUN python -m venv /opt/spinq-venv \
    && /opt/spinq-venv/bin/pip install --no-cache-dir \
       --index-url "${PYPI_INDEX_URL}" \
       --timeout 300 --retries 10 \
       "https://download-r2.pytorch.org/whl/cpu/torch-2.13.0%2Bcpu-cp310-cp310-manylinux_2_28_x86_64.whl" \
    && /opt/spinq-venv/bin/pip install --no-cache-dir \
       --index-url "${PYPI_INDEX_URL}" \
       --timeout 300 --retries 10 \
       -r requirements-spinq.txt

# pyQPanda 带原生动态库，使用独立解释器与主 Braket 环境隔离。
RUN python -m venv /opt/originq-venv \
    && /opt/originq-venv/bin/pip install --no-cache-dir \
       --index-url "${PYPI_INDEX_URL}" \
       --timeout 300 --retries 10 \
       -r requirements-originq.txt

ENV LOOMQ_SPINQ_PYTHON=/opt/spinq-venv/bin/python \
    LOOMQ_ORIGINQ_PYTHON=/opt/originq-venv/bin/python \
    LOOMQ_SPINQ_CLOUD_PYTHON=/opt/spinq-cloud-venv/bin/python

COPY . .

# Web 静态资源由独立的 Node 构建阶段产生，不将本地 node_modules 带入运行镜像。
COPY --from=web-builder /workspace/web/dist ./web/dist

EXPOSE 8765

CMD ["python","evaluator.py","--level","l1","--target","spinq,originq,braket","--json-out","/tmp/loomq-public-report.json"]
