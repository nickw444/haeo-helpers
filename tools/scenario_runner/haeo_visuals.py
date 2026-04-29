"""Bridge to HAEO upstream scenario visualization tooling."""

from __future__ import annotations

from pathlib import Path
import importlib
import sys
from typing import Any


def render_with_haeo_tooling(
    *,
    output_sensors: dict[str, dict[str, Any]],
    scenario_name: str,
    output_dir: Path,
    network: Any,
    haeo_repo_path: Path,
) -> None:
    """Render HAEO optimization/network visuals via upstream test tooling."""
    plot_module_path = haeo_repo_path / "tests" / "scenarios" / "visualisation" / "plot.py"
    if not plot_module_path.exists():
        msg = f"Could not find HAEO visualization tooling at {plot_module_path}"
        raise FileNotFoundError(msg)

    parent = str((haeo_repo_path).resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)

    output_dir.mkdir(parents=True, exist_ok=True)

    plot_mod = importlib.import_module("tests.scenarios.visualisation.plot")
    graph_mod = importlib.import_module("tests.scenarios.visualisation.graph")

    output_dir = output_dir.resolve()

    card_fn = getattr(plot_mod, "create_card_visualization")
    card_fn(
        _with_card_entity_aliases(output_sensors),
        str(output_dir / f"{scenario_name}_optimization.svg"),
    )

    graph_fn = getattr(graph_mod, "create_graph_visualization")
    graph_fn(
        network,
        str(output_dir / f"{scenario_name}_network_topology.svg"),
        f"{scenario_name.title()} Network Topology",
        generate_png=False,
    )

    stale_png = output_dir / f"{scenario_name}_network_topology.png"
    stale_png.unlink(missing_ok=True)


def _with_card_entity_aliases(
    output_sensors: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Add canonical entity aliases expected by HAEO forecast card."""
    aliased = dict(output_sensors)

    alias_patterns = {
        "sensor.grid_import_power": "grid_power_import",
        "sensor.grid_export_power": "grid_power_export",
        "sensor.solar_power": "solar_power",
        "sensor.load_power": "load_power",
        "sensor.battery_charge_power": "battery_power_charge",
        "sensor.battery_discharge_power": "battery_power_discharge",
        "sensor.battery_state_of_charge": "battery_state_of_charge",
    }

    for canonical_id, suffix in alias_patterns.items():
        if canonical_id in aliased:
            continue
        source = _first_entity_with_suffix(output_sensors, suffix)
        if source is None:
            continue
        cloned = {
            "entity_id": canonical_id,
            "state": source.get("state"),
            "attributes": dict(source.get("attributes", {})),
        }
        aliased[canonical_id] = cloned

    semantic_aliases = {
        "number.solar_forecast": {
            "element_type": "solar",
            "field_name": "forecast",
            "source_role": "forecast",
        },
        "sensor.constant_load_power": {
            "element_type": "load",
            "field_name": "forecast",
            "source_role": "forecast",
        },
        "number.grid_import_price": {
            "element_type": "grid",
            "field_name": "price_source_target",
        },
        "number.grid_export_price": {
            "element_type": "grid",
            "field_name": "price_target_source",
        },
    }
    for canonical_id, required_attrs in semantic_aliases.items():
        if canonical_id in aliased:
            continue
        source = _first_entity_with_attrs(output_sensors, required_attrs)
        if source is None:
            continue
        cloned = {
            "entity_id": canonical_id,
            "state": source.get("state"),
            "attributes": dict(source.get("attributes", {})),
        }
        aliased[canonical_id] = cloned

    return aliased


def _first_entity_with_suffix(
    output_sensors: dict[str, dict[str, Any]],
    suffix: str,
) -> dict[str, Any] | None:
    """Find first entity whose id ends with the expected semantic output suffix."""
    for entity_id, payload in output_sensors.items():
        if entity_id.endswith(f"_{suffix}"):
            return payload
    return None


def _first_entity_with_attrs(
    output_sensors: dict[str, dict[str, Any]],
    required_attrs: dict[str, str],
) -> dict[str, Any] | None:
    """Find first entity whose attributes contain all required key/value pairs."""
    for payload in output_sensors.values():
        attrs = payload.get("attributes", {})
        if all(attrs.get(key) == value for key, value in required_attrs.items()):
            return payload
    return None
