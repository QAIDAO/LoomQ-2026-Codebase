FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# pyqpanda 依赖 libcurl.so.4
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/submission
COPY requirements.txt .

# SpinQit requires antlr4-python3-runtime==4.9.2, while Braket's default
# simulator requires antlr4-python3-runtime==4.13.2.  Keep the four exact
# public pins in requirements.txt, but install their incompatible SDK stacks
# into separate Python 3.10 environments instead of forcing one resolver.
RUN python -m pip install --no-cache-dir \
    numpy==1.26.4 \
    pyqpanda==3.8.5 \
    spinqit==0.2.4

RUN python -m venv /opt/loomq-braket-venv \
    && /opt/loomq-braket-venv/bin/pip install --no-cache-dir \
        numpy==1.26.4 \
        amazon-braket-sdk==1.108.0

ENV LOOMQ_BRAKET_PYTHON=/opt/loomq-braket-venv/bin/python \
    PYTHONPATH=/workspace

COPY . .
# Keep the evaluator's top-level imports at /workspace/submission.  Package
# tests use `docker run -w /workspace ...` so this symlink resolves starter_kit.
RUN ln -s /workspace/submission /workspace/starter_kit

CMD ["python", "evaluator.py", "--json-out", "/tmp/loomq-public-report.json"]
