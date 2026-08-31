#!/usr/bin/env python3
"""Minimal dependency-injection container.

Providers are lazily-invoked factories registered under a string key and may
resolve further dependencies from the container itself — construction order
never matters. Singletons memoize on first resolve; `scope()` forks a child
container for per-call overrides (tests inject fakes without patching).

Everything the system needs (config, plugins, LLM transport, engine) is
wired in `bootstrap()`; no consumer ever constructs its own dependencies.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

try:
    from .config import LoomqConfig
except ImportError:
    from config import LoomqConfig

Provider = Callable[["Container"], Any]


class DependencyError(KeyError):
    pass


class Container:
    def __init__(self, parent: Optional["Container"] = None) -> None:
        self._parent = parent
        self._providers: dict[str, Provider] = {}
        self._singletons: dict[str, Any] = {}

    def register(self, key: str, provider: Provider) -> "Container":
        self._providers[key] = provider
        self._singletons.pop(key, None)
        return self

    def register_instance(self, key: str, instance: Any) -> "Container":
        self._providers[key] = lambda _c: instance
        self._singletons[key] = instance
        return self

    def register_singleton(self, key: str, provider: Provider) -> "Container":
        self.register(key, provider)

        def memoized(container: Container) -> Any:
            if key not in container._singletons:
                container._singletons[key] = provider(container)
            return container._singletons[key]

        return self.register(key, memoized)

    def resolve(self, key: str) -> Any:
        if key in self._singletons:
            return self._singletons[key]
        provider = self._providers.get(key)
        if provider is None:
            if self._parent is not None:
                return self._parent.resolve(key)
            raise DependencyError("no provider registered for %r" % key)
        return provider(self)

    def call(self, key: str) -> Any:
        """Invoke the provider freshly (no singleton caching)."""
        provider = self._providers.get(key)
        if provider is None:
            if self._parent is not None:
                return self._parent.call(key)
            raise DependencyError("no provider registered for %r" % key)
        return provider(self)

    def scope(self, overrides: Optional[Mapping[str, Any]] = None) -> "Container":
        child = Container(parent=self)
        for key, value in (overrides or {}).items():
            child.register_instance(key, value)
        return child

    def has(self, key: str) -> bool:
        return key in self._providers or key in self._singletons or (
            self._parent.has(key) if self._parent else False)


# --------------------------------------------------------------------------
# composition root
# --------------------------------------------------------------------------

def bootstrap(config: Optional[LoomqConfig] = None) -> Container:
    """Wire every dependency; the only place that knows concrete modules."""
    cfg = config or LoomqConfig.load()

    container = Container()
    container.register_instance("config", cfg)
    container.register_singleton("plugin_registry", _provide_plugin_registry)
    container.register_singleton("llm_transport", _provide_llm_transport)
    container.register_singleton("runner", _provide_runner)
    return container


def _provide_plugin_registry(container: Container):
    try:
        from .plugin_loader import load_plugins
    except ImportError:
        from plugin_loader import load_plugins
    cfg: LoomqConfig = container.resolve("config")
    return load_plugins(cfg)


def _provide_llm_transport(container: Container):
    try:
        from .llm_client import chat_completion
    except ImportError:
        from llm_client import chat_completion
    cfg: LoomqConfig = container.resolve("config")

    def transport(messages, **extra):
        return chat_completion(messages, **extra)

    return transport


def _provide_runner(container: Container):
    try:
        from .runner import CircuitRunner
    except ImportError:
        from runner import CircuitRunner
    return CircuitRunner(
        config=container.resolve("config"),
        registry=container.resolve("plugin_registry"),
    )
