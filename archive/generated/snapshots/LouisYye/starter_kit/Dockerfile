FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# pyqpanda 依赖 libcurl.so.4
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/submission
COPY requirements.txt requirements-spinq.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# SpinQit pins NumPy and ANTLR versions that conflict with Qiskit and Braket,
# so it runs in an isolated Python environment via backend/spinq.py.
RUN python -m venv /opt/spinq-venv \
    && /opt/spinq-venv/bin/python -m pip install --no-cache-dir \
        -r requirements-spinq.txt

ENV LOOMQ_SPINQ_PYTHON=/opt/spinq-venv/bin/python
COPY . .

CMD ["python", "evaluator.py", "--json-out", "/tmp/loomq-public-report.json"]
