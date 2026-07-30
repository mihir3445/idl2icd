from __future__ import annotations

from importlib.metadata import entry_points

import pluggy

from idl2icd.plugins.spec import DDSICDHookSpec

ENTRY_POINT_GROUP = "idl2icd.plugins"


def build_plugin_manager(enabled: list[str] | None = None) -> pluggy.PluginManager:
    """Discovers plugins via the `idl2icd.plugins` entry-point group and
    registers them. If `enabled` is given (from idl2icd.yaml's
    `plugins.enabled` list), only those names are loaded; otherwise all
    discovered plugins load. The built-in "core" plugin always loads.
    """
    pm = pluggy.PluginManager("idl2icd")
    pm.add_hookspecs(DDSICDHookSpec)

    from idl2icd.plugins.core_plugin import CorePlugin
    pm.register(CorePlugin(), name="core")

    discovered = entry_points(group=ENTRY_POINT_GROUP)
    for ep in discovered:
        if enabled is not None and ep.name not in enabled:
            continue
        try:
            plugin_cls = ep.load()
            pm.register(plugin_cls(), name=ep.name)
        except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001
            import sys
            print(f"[idl2icd] Warning: failed to load plugin '{ep.name}': {exc}", file=sys.stderr)

    return pm


def list_available_plugins() -> list[str]:
    return ["core"] + [ep.name for ep in entry_points(group=ENTRY_POINT_GROUP)]
