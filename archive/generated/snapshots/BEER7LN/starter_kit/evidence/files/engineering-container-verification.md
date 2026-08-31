# Container verification record

- Verification date: 2026-08-14 (UTC+8)
- Host runtime: Docker Desktop 29.7.2, `desktop-linux` builder, WSL 2 backend
- Image tag: `loomq-submission:validation`
- Image manifest: `sha256:9c00dcdfca15235d4a75eee04b142e9712ef7dbc6f4742504d10a57d10f1edaf`
- Source snapshot: local working tree based on commit `c5f0b35`; rebuild from the final submitted commit before submission.

## Build

From `starter_kit/`:

```powershell
docker build --progress=plain -t loomq-submission:validation .
```

The image was built successfully from the checked-in `Dockerfile`, including the pinned SDK dependencies in `requirements.txt`.

## Executed checks

```powershell
docker run --rm loomq-submission:validation python evaluator.py --level l1 --target spinq,originq,braket
docker run --rm loomq-submission:validation python evaluator.py --level l3
docker run --rm -e LOOMQ_REQUIRE_NATIVE=1 loomq-submission:validation python -m unittest tests.test_l1_native -q
docker run --rm loomq-submission:validation python -m unittest tests.test_l3_hybrid tests.test_l3_bonus_contract -q
docker run --rm -d --name loomq-l2-smoke -p 127.0.0.1:18765:8765 loomq-submission:validation python l2_app.py --host 0.0.0.0 --port 8765
```

Observed results:

- L1 public evaluator: 6/6 passed across SpinQ, OriginQ and Braket targets.
- L3 public evaluator: 1/1 passed.
- Forced native-SDK L1 test suite: 6 passed.
- L3 compiler plus custom RISC-V extension suite: 19 passed.
- The containerized L2 service returned HTTP 200 from `/api/health`; the temporary `loomq-l2-smoke` container was then removed.

## Configuration boundary

The Dockerfile's default evaluator command also attempts L2 because `submission.yaml` declares it. Without organizer-injected `LOOMQ_LLM_BASE_URL`, `LOOMQ_LLM_API_KEY` and `LOOMQ_LLM_MODEL`, L2 intentionally reports a missing-configuration error. This is expected secret-safe behavior, not a fallback or an attempted external model call. The explicit L1/L3 commands above are the reproducible offline container checks.

No API key, token, cookie, user identifier or hardware credential was placed in the image or this record.