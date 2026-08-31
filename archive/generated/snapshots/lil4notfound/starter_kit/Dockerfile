ARG PYTHON_IMAGE=python:3.10-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/submission
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8765

CMD ["python", "evaluator.py", "--json-out", "/tmp/loomq-public-report.json"]
