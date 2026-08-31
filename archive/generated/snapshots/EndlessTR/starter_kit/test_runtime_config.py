"""Tests for starter_kit.quantumhelper_web.runtime_config (任务书 §19-§23).

Covers the runtime > environment > none priority, the safe (key-free)
``effective()`` view, ``resolve()`` returning the full in-memory triple,
``clear()`` returning to environment fallback, and ``test_connection`` against a
mocked ``chat_completion``.  No real network access.
"""

import os
import threading
from contextlib import contextmanager
from unittest import mock

from starter_kit.quantumhelper_web import runtime_config as rc


@contextmanager
def llm_env(**values):
    """Temporarily control only the LOOMQ_LLM_* environment variables."""
    keys = (rc.ENV_BASE_URL, rc.ENV_API_KEY, rc.ENV_MODEL)
    saved = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_runtime_set_effective_is_safe_and_reports_runtime():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://api.example.com/v1/", "sk-secret-123", "deepseek-v4-flash")
        eff = cfg.effective()

        assert eff["configured"] is True
        assert eff["source"] == "runtime"
        assert eff["api_key_present"] is True
        assert eff["model"] == "deepseek-v4-flash"
        assert eff["base_url"] == "https://api.example.com/v1"  # trailing slash stripped
        assert "api_key" not in eff  # only api_key_present, never the raw key
        assert "sk-secret-123" not in repr(eff)


def test_environment_fallback_when_runtime_unset():
    with llm_env(
        LOOMQ_LLM_BASE_URL="https://env.example.com/v1",
        LOOMQ_LLM_API_KEY="env-secret-key",
        LOOMQ_LLM_MODEL="env-model",
    ):
        cfg = rc.RuntimeConfig()
        eff = cfg.effective()

        assert eff["configured"] is True
        assert eff["source"] == "environment"
        assert eff["api_key_present"] is True
        assert eff["model"] == "env-model"
        assert eff["base_url"] == "https://env.example.com/v1"
        assert "env-secret-key" not in repr(eff)


def test_none_when_no_runtime_and_no_env():
    with llm_env():
        cfg = rc.RuntimeConfig()
        eff = cfg.effective()

        assert eff["configured"] is False
        assert eff["source"] == "none"
        assert eff["api_key_present"] is False
        assert eff["model"] is None
        assert eff["base_url"] is None


def test_resolve_prefers_runtime_over_env():
    with llm_env(
        LOOMQ_LLM_BASE_URL="https://env.example.com/v1",
        LOOMQ_LLM_API_KEY="env-key",
        LOOMQ_LLM_MODEL="env-model",
    ):
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")

        assert cfg.resolve() == ("https://run.example.com/v1", "run-key", "run-model")


def test_resolve_returns_none_without_any_config():
    with llm_env():
        cfg = rc.RuntimeConfig()
        assert cfg.resolve() is None


def test_clear_returns_to_environment_fallback():
    with llm_env(
        LOOMQ_LLM_BASE_URL="https://env.example.com/v1",
        LOOMQ_LLM_API_KEY="env-key",
        LOOMQ_LLM_MODEL="env-model",
    ):
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")
        assert cfg.resolve()[2] == "run-model"

        cfg.clear()
        assert cfg.effective()["source"] == "environment"
        assert cfg.resolve()[2] == "env-model"


def test_clear_with_no_env_is_none():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")
        cfg.clear()

        assert cfg.effective()["source"] == "none"
        assert cfg.resolve() is None


def test_set_rejects_empty_fields():
    import pytest  # noqa: PLC0415

    cfg = rc.RuntimeConfig()
    with pytest.raises(ValueError):
        cfg.set("", "key", "model")
    with pytest.raises(ValueError):
        cfg.set("https://x.example.com", "", "model")
    with pytest.raises(ValueError):
        cfg.set("https://x.example.com", "key", "   ")
    with pytest.raises(ValueError):
        cfg.set("http://remote.example.com/v1", "key", "model")


def test_test_connection_success_with_mocked_completion():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")
        fake = mock.Mock(return_value={"choices": [{"message": {"content": "正常"}}]})

        with mock.patch.object(rc, "_chat_completion", return_value=fake):
            result = rc.test_connection(cfg)

        assert result["ok"] is True
        assert result["message"] == "API 连接正常"
        assert isinstance(result["latency_ms"], int)
        assert result["model"] == "run-model"
        fake.assert_called_once()


def test_test_connection_failure_is_friendly_and_hides_key():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")

        def boom(*args, **kwargs):
            raise RuntimeError("LoomQ L2 API returned HTTP 401")

        with mock.patch.object(rc, "_chat_completion", return_value=boom):
            result = rc.test_connection(cfg)

        assert result["ok"] is False
        assert "401" in result["message"]
        assert "run-key" not in result["message"]
        assert "run-key" not in repr(result)
        assert result["model"] == "run-model"


def test_test_connection_uses_request_local_override_without_mutating_env():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")
        seen = {}

        def capture(*args, **kwargs):
            from starter_kit import llm_client  # noqa: PLC0415

            base, key, model, _timeout, _max_output = llm_client._configuration()
            seen.update(base=base, key=key, model=model)
            seen["environment_untouched"] = all(
                os.environ.get(name) is None for name in rc.REQUIRED_ENV
            )
            return {"choices": [{"message": {"content": "ok"}}]}

        with mock.patch.object(rc, "_chat_completion", return_value=capture):
            rc.test_connection(cfg)

        assert seen == {
            "base": "https://run.example.com/v1",
            "key": "run-key",
            "model": "run-model",
            "environment_untouched": True,
        }
        assert os.environ.get(rc.ENV_BASE_URL) is None
        assert os.environ.get(rc.ENV_API_KEY) is None
        assert os.environ.get(rc.ENV_MODEL) is None


def test_completion_wrapper_accepts_positional_messages():
    with llm_env():
        cfg = rc.RuntimeConfig()
        cfg.set("https://run.example.com/v1", "run-key", "run-model")
        fake = mock.Mock(return_value={"choices": [{"message": {"content": "ok"}}]})
        with mock.patch.object(rc, "_chat_completion", return_value=fake):
            completion = rc.completion_for_config(cfg)
            result = completion([{"role": "user", "content": "hello"}], max_tokens=8)

        assert result["choices"][0]["message"]["content"] == "ok"
        fake.assert_called_once_with(
            [{"role": "user", "content": "hello"}], max_tokens=8
        )


def test_concurrent_runtime_configs_are_request_isolated():
    from starter_kit import llm_client  # noqa: PLC0415

    first = rc.RuntimeConfig()
    first.set("https://first.example.com/v1", "first-key", "first-model")
    second = rc.RuntimeConfig()
    second.set("https://second.example.com/v1", "second-key", "second-model")
    barrier = threading.Barrier(2)
    seen = {}
    errors = []

    def capture(_messages):
        barrier.wait(timeout=2)
        return llm_client._configuration()[:3]

    def invoke(name, completion):
        try:
            seen[name] = completion([])
        except Exception as exc:  # pragma: no cover - assertion reports details
            errors.append(exc)

    with mock.patch.object(rc, "_chat_completion", return_value=capture):
        calls = {
            "first": rc.completion_for_config(first),
            "second": rc.completion_for_config(second),
        }
        threads = [
            threading.Thread(target=invoke, args=(name, completion))
            for name, completion in calls.items()
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

    assert errors == []
    assert seen == {
        "first": ("https://first.example.com/v1", "first-key", "first-model"),
        "second": ("https://second.example.com/v1", "second-key", "second-model"),
    }


def test_env_file_is_allowlisted_and_does_not_override_environment(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOOMQ_LLM_BASE_URL=https://file.example.com/v1\n"
        "LOOMQ_LLM_API_KEY=file-key\n"
        "LOOMQ_LLM_MODEL=file-model\n"
        "UNRELATED_SECRET=must-not-load\n",
        encoding="utf-8",
    )
    with llm_env(LOOMQ_LLM_MODEL="environment-model"):
        os.environ.pop("UNRELATED_SECRET", None)
        assert rc.load_env_file(env_file) is True
        assert os.environ[rc.ENV_MODEL] == "environment-model"
        assert os.environ[rc.ENV_BASE_URL] == "https://file.example.com/v1"
        assert os.environ[rc.ENV_API_KEY] == "file-key"
        assert "UNRELATED_SECRET" not in os.environ


def test_test_connection_when_not_configured_is_friendly():
    with llm_env():
        cfg = rc.RuntimeConfig()
        result = rc.test_connection(cfg)

        assert result["ok"] is False
        assert "尚未配置" in result["message"]
        assert result["latency_ms"] is None
        assert result["model"] == ""


def test_get_runtime_config_returns_process_singleton():
    first = rc.get_runtime_config()
    second = rc.get_runtime_config()
    assert first is second
    first.clear()
    assert first.effective()["source"] in ("none", "environment")
