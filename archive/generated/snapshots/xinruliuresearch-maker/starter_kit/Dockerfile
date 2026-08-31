FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/submission
COPY --chown=65532:65532 . .
USER 65532:65532

EXPOSE 8000

CMD ["python", "scripts/run_all_checks.py", "--quick", "--report-dir", "/tmp/loomq-reports"]
