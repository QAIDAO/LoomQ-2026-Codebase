#!/usr/bin/env python3
"""Plugin architecture for L1 backends.

A backend is a module in `starter_kit/plugins/` exporting a `register()`
factory that returns a BackendPlugin instance. The loader discovers modules
at runtime (packaged directory first, then any extra directory from
PluginConfig), validates the contract, and hands the registry to the
runner — adding a platform means dropping in one file, never touching the
pipeline.

BackendPlugin contract (attributes + methods):
    target        unique short id, e.g. "spinq"      (str)
    backend_id    canonical result id when the native path executes
    dialect       emitter key: "qasm2" | "qasm3" | "originir"
    capabilities  dict merged into agent knowledge (max_qubits, queue, cost...)
    emit(circuit) -> str                             native IR text
    run(circuit, shots, config) -> ExecutionOutcome  unified clbit-keyed counts
    available(config) -> bool                        native SDK usable?
    engine_label -> label of the last execution path ("native:<sdk>" /
                    "builtin:statevector"); updated by run()
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable

try:
    from .config import LoomqConfig
except ImportError:
    from config import LoomqConfig


class PluginError(RuntimeError):
    pass


@dataclass
class ExecutionOutcome:
    """Result of one execution path, already normalized to clbit keys."""
    backend_id: str
    engine_label: str
    counts: dict[str, int]


@dataclass
class BackendPlugin:
    target: str
    backend_id: str
    dialect: str
    capabilities: dict = field(default_factory=dict)
    emit: Callable = None                    # Circuit -> str
    run: Callable = None                     # (Circuit, shots, LoomqConfig) -> ExecutionOutcome
    available: Callable[[LoomqConfig], bool] = lambda _cfg: True
    engine_label: str = ""
    display_name: str = ""

    def validate(self) -> None:
        missing = [name for name in ("target", "backend_id", "dialect", "emit", "run")
                   if not getattr(self, name, None)]
        if missing:
            raise PluginError("plugin %r misses %s" % (self.target or "?", ", ".join(missing)))
        if self.dialect not in ("qasm2", "qasm3", "originir"):
            raise PluginError("plugin %r has unknown dialect %r" % (self.target, self.dialect))


@dataclass
class PluginRegistry:
    plugins: dict[str, BackendPlugin]

    def get(self, target: str) -> BackendPlugin:
        try:
            return self.plugins[target]
        except KeyError:
            raise PluginError("unknown target %r (registered: %s)"
                              % (target, ", ".join(sorted(self.plugins)))) from None

    def targets(self) -> tuple[str, ...]:
        return tuple(sorted(self.plugins))

    def enabled_plugins(self, config: LoomqConfig) -> list[BackendPlugin]:
        return [p for t, p in sorted(self.plugins.items())
                if config.plugins.is_enabled(t)]

    def capability_table(self) -> list[dict]:
        rows = []
        for plugin in self.plugins.values():
            row = {"id": plugin.backend_id, "platform": plugin.target,
                   "kind": plugin.capabilities.get("kind", "simulator"),
                   "max_qubits": plugin.capabilities.get("max_qubits", 0),
                   "queue": plugin.capabilities.get("queue", "none"),
                   "cost": plugin.capabilities.get("cost", "free"),
                   "requires_account": plugin.capabilities.get("requires_account", False),
                   "notes": plugin.capabilities.get("notes", "")}
            rows.append(row)
        return rows

def _module_name(path: str) -> str:
    base = os.path.basename(path)
    return os.path.splitext(base)[0]


def _load_module(path: str) -> ModuleType:
    name = "_loomq_plugin_" + _module_name(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PluginError("cannot load plugin module at %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_plugin_file(path: str) -> BackendPlugin:
    module = _load_module(path)
    factory = getattr(module, "register", None)
    if factory is None or not callable(factory):
        raise PluginError("plugin %s does not expose register()" % path)
    plugin = factory()
    # Structural check instead of isinstance(): a dynamically-exec'd plugin
    # may bind BackendPlugin from a second copy of this module (bare vs
    # package import), which would make class-identity checks unreliable.
    required = ("target", "backend_id", "dialect", "emit", "run")
    if not all(getattr(plugin, name, None) for name in required):
        raise PluginError("plugin %s register() returned %r missing %s"
                          % (path, type(plugin).__name__,
                             ", ".join(n for n in required
                                       if not getattr(plugin, n, None))))
    validator = getattr(plugin, "validate", None)
    if callable(validator):
        validator()
    return plugin


def packaged_plugin_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


def load_plugins(config: LoomqConfig) -> PluginRegistry:
    directories = [packaged_plugin_dir()]
    extra = config.plugins.directory
    if extra and os.path.isdir(extra):
        directories.append(extra)

    registry: dict[str, BackendPlugin] = {}
    for directory in directories:
        for entry in sorted(os.listdir(directory)):
            if not entry.endswith("_plugin.py") or entry.startswith("_"):
                continue
            plugin = load_plugin_file(os.path.join(directory, entry))
            if plugin.target in registry:
                continue                      # packaged plugins take precedence
            registry[plugin.target] = plugin

    disabled = [t for t in registry if not config.plugins.is_enabled(t)]
    for target in disabled:
        del registry[target]
    if not registry:
        raise PluginError("no backend plugins loaded")
    return PluginRegistry(registry)


if __name__ == "__main__":
    from config import LoomqConfig as Cfg
    reg = load_plugins(Cfg.load())
    print("loaded targets:", reg.targets())
