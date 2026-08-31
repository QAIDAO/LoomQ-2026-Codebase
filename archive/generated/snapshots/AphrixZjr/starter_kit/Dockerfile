# Docker Hub Official Image, pinned to the linux/amd64 digest verified for the
# competition image on 2026-08-03.
FROM python:3.10-slim@sha256:c1e4e6c01eb489c422288b2de34b0761ca316f7a2d98e2c33f47659a73ed108a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The legacy local-simulator pyqpanda wheel depends on libcurl.so.4.
# pyqpanda3 is installed alongside it, but hardware scripts import only v3.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/submission
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# `.dockerignore` admits only the normalized formal summaries used by the
# read-only Web replay.  Fail the build if a raw/request/QASM evidence artifact
# ever leaks into the image or if one of the four replay inputs is missing.
RUN python -c "from pathlib import Path; from web.app import ARCHIVED_HARDWARE_SUMMARIES; root = Path('evidence'); expected = {'files/hardware/%s/%s' % (key[0], identity['filename']) for key, identity in ARCHIVED_HARDWARE_SUMMARIES.items()}; actual = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}; assert actual == expected, 'unexpected Web evidence files: %r' % sorted(actual ^ expected)"

# Verify that the L1, L2, L3 and Bonus entry points share one usable image,
# including all three SDKs exposed by the L2 backend selector.
RUN python -c "import adapter, loomq_l1, loomq_l2, loomq_l3, quantum_riscv, riscv_emulator, web.app; from l1_spinq import _load_sdk as spinq; from l1_originq import _load_sdk as originq; from l1_braket import _load_sdk as braket; spinq(); originq(); braket()"

EXPOSE 8765

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import json, urllib.request; value=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=2)); assert value['status'] == 'ok'" || exit 1

CMD ["python", "web/server.py", "--host", "0.0.0.0", "--port", "8765"]
