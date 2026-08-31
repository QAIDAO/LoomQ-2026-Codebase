FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

COPY . /app/starter_kit

EXPOSE 8000
CMD ["python", "starter_kit/quantumhelper_web/server.py", "--host", "0.0.0.0"]
