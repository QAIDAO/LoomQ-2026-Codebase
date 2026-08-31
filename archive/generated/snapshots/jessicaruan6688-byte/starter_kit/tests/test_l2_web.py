"""Smoke tests for the minimal L2 web shell (no live LLM calls)."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from web.server import L2WebHandler, l2_configured
from llm_client import REQUIRED_ENV


def _http_get(url: str) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _http_post(url: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _http_bytes(url: str) -> tuple[int, bytes, str]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read(), resp.headers.get_content_type()


def test_health_endpoint() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, data = _http_get(f"http://{host}:{port}/api/health")
        assert status == 200
        assert data["ok"] is True
        assert "l2_configured" in data
        assert data["l2_configured"] == l2_configured()
        assert data["hardware_ready"] is True
    finally:
        server.shutdown()


def test_experiments_replay_spinq_jobs() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, data = _http_get(f"http://{host}:{port}/api/experiments")
        assert status == 200
        ids = [item["id"] for item in data["experiments"]]
        assert ids == ["bell", "ghz3"]
        bell = data["experiments"][0]
        assert bell["job_id"] == "G-260809-0018"
        assert bell["replay"] is True
        assert "00" in bell["experiment"]
        assert "11" in bell["experiment"]
        ghz = data["experiments"][1]
        assert ghz["job_id"] == "S-260810-0001"
        assert "000" in ghz["experiment"]
        assert "111" in ghz["experiment"]
    finally:
        server.shutdown()


def test_home_is_first_experiment_not_thin_shell() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body, content_type = _http_bytes(f"http://{host}:{port}/")
        html = body.decode("utf-8")
        assert status == 200
        assert content_type == "text/html"
        assert "第一次量子实验" in html or "真机归档回放" in html
        assert "薄壳" not in html
        css_status, css_body, _ = _http_bytes(f"http://{host}:{port}/style.css")
        assert css_status == 200
        assert b"bar-row" in css_body
        js_status, js_body, _ = _http_bytes(f"http://{host}:{port}/app.js")
        assert js_status == 200
        assert b"renderExperiment" in js_body
    finally:
        server.shutdown()


def test_backends_and_local_simulate() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, data = _http_get(f"http://{host}:{port}/api/backends")
        assert status == 200
        ids = {item["id"] for item in data["backends"]}
        assert "originq_local_simulator" in ids
        assert "braket_local_simulator" in ids
        fits = [item["id"] for item in data["backends"] if item["fits_15q_no_queue"]]
        assert "spinq_cloud_qpu" not in fits
        assert any("simulator" in item for item in fits)
        qasm = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"
        )
        status, sim = _http_post(f"http://{host}:{port}/api/simulate", {"qasm": qasm})
        assert status == 200
        assert sim["probabilities"]["00"] > 0.49
        assert sim["probabilities"]["11"] > 0.49
        assert set(sim["peaks"]) == {"00", "11"}
    finally:
        server.shutdown()
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, data = _http_post(
            f"http://{host}:{port}/api/chat",
            {"prompt": ""},
        )
        assert status == 400
        assert "error" in data
    finally:
        server.shutdown()


def test_chat_missing_env_returns_503() -> None:
    saved = {name: os.environ.get(name) for name in REQUIRED_ENV}
    for name in REQUIRED_ENV:
        os.environ.pop(name, None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), L2WebHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("web.server._load_dotenv", lambda: None):
            status, data = _http_post(
                f"http://{host}:{port}/api/chat",
                {"prompt": "hello"},
            )
        assert status == 503
        assert "missing" in data
    finally:
        server.shutdown()
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
