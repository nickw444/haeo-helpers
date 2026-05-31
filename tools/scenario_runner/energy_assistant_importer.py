"""One-time importer from energy-assistant captures to native fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import math

from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.const import CURVE_LINEAR
from custom_components.haeo_helpers.helpers.forecast_risk_adjustment.sensor import (
    adjust_forecast_for_risk,
)
from custom_components.haeo_helpers.helpers.forecast_statistic.const import (
    AGGREGATION_MEAN,
    AGGREGATION_PERCENTILE,
)
from custom_components.haeo_helpers.helpers.forecast_statistic.sensor import (
    _calculate_percentile,
)

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional outside scenario tooling venv
    yaml = None

SCHEMA_VERSION = 1


def import_energy_assistant_capture(
    *,
    source_path: Path,
    destination_path: Path,
    scenario_name: str,
    timezone: str = "UTC",
) -> Path:
    """Convert a capture payload into the native scenario fixture format."""
    if source_path.is_dir():
        normalized = _normalize_scenario_directory_to_haeo_payload(source_path, timezone=timezone)
    else:
        capture_payload = _load_source_payload(source_path)
        normalized = _normalize_capture_to_haeo_payload(capture_payload, timezone=timezone)
    fixture_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "name": scenario_name,
            "captured_at": datetime.now(UTC).isoformat(),
            "timezone": timezone,
        },
        "source": {
            "kind": "energy_assistant",
            "path": str(source_path),
        },
        "haeo": normalized,
    }
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(json.dumps(fixture_payload, indent=2) + "\n")
    return destination_path


def _load_source_payload(source_path: Path) -> dict[str, Any]:
    """Load an EA source payload from file or directory."""
    if source_path.is_file():
        return json.loads(source_path.read_text())

    for candidate in ("fixture.json", "inputs.json", "resolved_inputs.json", "scenario.json"):
        candidate_path = source_path / candidate
        if candidate_path.exists():
            return json.loads(candidate_path.read_text())

    msg = f"Could not find a supported capture file in {source_path}."
    raise FileNotFoundError(msg)


def _normalize_scenario_directory_to_haeo_payload(
    source_dir: Path,
    *,
    timezone: str,
) -> dict[str, Any]:
    """Normalize an EA fixture directory (config/input/output files)."""
    config_path = source_dir / "config.yaml"
    input_path = source_dir / "input.json"
    output_path = source_dir / "output.json"

    if not config_path.exists() or not input_path.exists():
        msg = (
            f"Unsupported EA scenario directory at {source_dir}; "
            "expected at least config.yaml and input.json."
        )
        raise FileNotFoundError(msg)

    config_raw = config_path.read_text()
    input_payload = json.loads(input_path.read_text())
    output_payload = json.loads(output_path.read_text()) if output_path.exists() else {}

    if yaml is None:
        msg = (
            "PyYAML is required for importing Energy Assistant scenario directories. "
            "Install scenario dependencies first."
        )
        raise RuntimeError(msg)
    config_payload = yaml.safe_load(config_raw) or {}

    return {
        "config": _build_haeoish_config(
            config_payload=config_payload,
            input_payload=input_payload,
        ),
        "environment": _build_environment(input_payload, timezone=timezone),
        "inputs": _build_inputs_from_ea_input_payload(input_payload, config_payload=config_payload),
        "outputs": _build_outputs_from_ea_output_payload(output_payload),
    }


def _normalize_capture_to_haeo_payload(
    capture_payload: dict[str, Any],
    *,
    timezone: str,
) -> dict[str, Any]:
    """Normalize EA payloads into HAEO diagnostics-style sections."""
    if all(key in capture_payload for key in ("config", "environment", "inputs")):
        return {
            "config": capture_payload["config"],
            "environment": capture_payload["environment"],
            "inputs": capture_payload["inputs"],
            "outputs": capture_payload.get("outputs", {}),
        }

    if "data" in capture_payload and isinstance(capture_payload["data"], dict):
        data_payload = capture_payload["data"]
        if all(key in data_payload for key in ("config", "environment", "inputs")):
            return {
                "config": data_payload["config"],
                "environment": data_payload["environment"],
                "inputs": data_payload["inputs"],
                "outputs": data_payload.get("outputs", {}),
            }

    msg = (
        "Unsupported capture format. Expected diagnostics-style payload with "
        "'config', 'environment', and 'inputs'. Convert source capture first."
    )
    raise ValueError(msg)


def _build_haeoish_config(*, config_payload: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a HAEO-like config object from EA config payload."""
    ems_config = config_payload.get("ems", {}) if isinstance(config_payload, dict) else {}
    plant_config = config_payload.get("plant", {}) if isinstance(config_payload, dict) else {}
    input_registry = input_payload.get("inputs", {})
    input_keys = set(input_registry.keys()) if isinstance(input_registry, dict) else set()
    input_keys |= _helper_input_keys(plant_config)

    high_res_step = int(ems_config.get("high_res_timestep_minutes", 5))
    high_res_horizon = int(ems_config.get("high_res_horizon_minutes", 120))
    regular_step = int(ems_config.get("timestep_minutes", 30))
    regular_horizon = int(ems_config.get("horizon_minutes", 24 * 60))
    tier_1_count = max(1, high_res_horizon // high_res_step)
    remaining_minutes = max(regular_horizon - high_res_horizon, 0)
    tier_2_count = max(1, math.ceil(remaining_minutes / regular_step)) if remaining_minutes else 1

    participants: dict[str, dict[str, Any]] = {}
    for raw_name, element in plant_config.items():
        if not isinstance(element, dict):
            continue
        participant = _build_participant_from_plant_element(
            raw_name,
            element,
            input_keys=input_keys,
        )
        if participant is None:
            continue
        participants[participant["name"]] = participant

    return {
        "version": 1,
        "minor_version": 3,
        "tier_1_count": tier_1_count,
        "tier_1_duration": high_res_step,
        "tier_2_count": tier_2_count,
        "tier_2_duration": regular_step,
        "participants": participants,
        "source_metadata": {
            "source_kind": "energy_assistant",
            "raw_config": config_payload,
        },
    }


def _build_environment(input_payload: dict[str, Any], *, timezone: str) -> dict[str, Any]:
    """Build environment block from EA input payload."""
    captured_at = str(input_payload.get("captured_at", datetime.now(UTC).isoformat()))
    return {
        "diagnostic_request_time": captured_at,
        "diagnostic_target_time": None,
        "ha_version": "unknown",
        "haeo_version": "unknown",
        "horizon_start": captured_at,
        "optimization_end_time": captured_at,
        "optimization_start_time": captured_at,
        "timezone": timezone,
    }


def _build_inputs_from_ea_input_payload(
    input_payload: dict[str, Any],
    *,
    config_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Translate EA inputs registry into diagnostics-style entity states."""
    registry = input_payload.get("inputs", {})
    entities: list[dict[str, Any]] = []
    for key, value in registry.items():
        entity_id = f"sensor.ea_{key}"
        kind = value.get("kind") if isinstance(value, dict) else None
        unit = _unit_for_input_kind(kind)
        device_class = _device_class_for_input_kind(kind)
        if isinstance(value, dict) and "points" in value and isinstance(value["points"], dict):
            points = value["points"]
            sorted_items = sorted(points.items())
            forecast = [{"time": timestamp, "value": point_value} for timestamp, point_value in sorted_items]
            state_value = value.get("realtime_value", forecast[0]["value"] if forecast else 0)
            attributes = {
                "source_key": key,
                "kind": kind,
                "interval_minutes": value.get("interval_minutes"),
                "forecast": forecast,
            }
            if kind == "price":
                attributes["interpolation_mode"] = "previous"
        else:
            scalar_value = value.get("value") if isinstance(value, dict) else value
            state_value = scalar_value
            attributes = {"source_key": key}
            if kind is not None:
                attributes["kind"] = kind
        if unit is not None:
            attributes["unit_of_measurement"] = unit
        if device_class is not None:
            attributes["device_class"] = device_class
        entities.append(
            {
                "entity_id": entity_id,
                "state": str(state_value),
                "attributes": attributes,
            }
        )
    if config_payload.get("plant") and input_payload.get("captured_at"):
        entities.extend(_build_helper_transform_entities(input_payload=input_payload, config_payload=config_payload))
    return entities


def _build_outputs_from_ea_output_payload(output_payload: dict[str, Any]) -> dict[str, Any]:
    """Store EA output payload in diagnostics outputs namespace."""
    return {
        "ea_output_payload": {
            "state": "available",
            "attributes": output_payload,
        }
    }


def _unit_for_input_kind(kind: Any) -> str | None:
    """Return HAEO parser-compatible unit metadata for an EA input kind."""
    return {
        "power": "kW",
        "price": "$/kWh",
        "percentage": "%",
    }.get(kind)


def _device_class_for_input_kind(kind: Any) -> str | None:
    """Return Home Assistant-style device class metadata for an EA input kind."""
    return {
        "power": "power",
        "price": "monetary",
        "percentage": "battery",
    }.get(kind)


def _build_helper_transform_entities(
    *,
    input_payload: dict[str, Any],
    config_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build HAEO source entities produced by haeo-helpers transforms."""
    plant_config = config_payload.get("plant", {}) if isinstance(config_payload, dict) else {}
    entities: list[dict[str, Any]] = []
    captured_at = datetime.fromisoformat(str(input_payload.get("captured_at")))
    for raw_name, element in plant_config.items():
        if not isinstance(element, dict):
            continue
        if element.get("type") == "grid":
            entities.extend(_build_grid_risk_adjustment_entities(element, input_payload=input_payload))
            continue
        if element.get("type") == "battery":
            entity = _build_battery_stored_energy_value_entity(raw_name, element, input_payload=input_payload)
            if entity is not None:
                entities.append(entity)
    for entity in entities:
        entity["attributes"]["haeo_helpers_reference_time"] = captured_at.isoformat()
    return entities


def _helper_input_keys(plant_config: dict[str, Any]) -> set[str]:
    """Return generated helper input keys referenced by HAEO config."""
    keys: set[str] = set()
    for raw_name, element in plant_config.items():
        if not isinstance(element, dict):
            continue
        if element.get("type") == "grid":
            for direction_name, config_key in (("import", "price_import"), ("export", "price_export")):
                price_config = element.get(config_key, {})
                if isinstance(price_config, dict) and price_config.get("filters"):
                    keys.add(f"grid_price_{direction_name}_risk_adjusted")
            continue
        if element.get("type") == "battery" and "stored_energy_value" in element:
            keys.add(f"{raw_name}_stored_energy_value")
    return keys


def _build_grid_risk_adjustment_entities(
    element: dict[str, Any],
    *,
    input_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply forecast risk adjustment helper semantics to EA grid price filters."""
    result: list[dict[str, Any]] = []
    for direction_name, config_key in (
        ("import", "price_import"),
        ("export", "price_export"),
    ):
        price_config = element.get(config_key, {})
        source_key = _source_ref_to_input_key(price_config.get("source"))
        if source_key is None:
            continue
        source_entity = _entity_from_input_key(source_key, input_payload)
        if source_entity is None:
            continue
        forecast = source_entity["attributes"].get("forecast")
        if not isinstance(forecast, list):
            continue
        basis_bias_pct = 0.0
        risk_bias_pct = 0.0
        ramp_start_after_minutes = 30.0
        ramp_duration_minutes = 90.0
        curve = CURVE_LINEAR
        for forecast_filter in price_config.get("filters", []):
            if not isinstance(forecast_filter, dict):
                continue
            if forecast_filter.get("type") == "bias":
                basis_bias_pct += float(forecast_filter.get("bias_pct", 0.0))
            elif forecast_filter.get("type") == "risk":
                risk_bias_pct += float(forecast_filter.get("bias_pct", 0.0))
                ramp_start_after_minutes = float(
                    forecast_filter.get("ramp_start_after_minutes", ramp_start_after_minutes)
                )
                ramp_duration_minutes = float(forecast_filter.get("ramp_duration_minutes", ramp_duration_minutes))
                curve = str(forecast_filter.get("curve", curve))
        adjusted_forecast, closest_value = adjust_forecast_for_risk(
            forecast,
            reference_now=datetime.fromisoformat(str(input_payload.get("captured_at"))),
            basis_bias_pct=basis_bias_pct,
            risk_bias_pct=risk_bias_pct,
            ramp_start_after_minutes=ramp_start_after_minutes,
            ramp_duration_minutes=ramp_duration_minutes,
            curve=curve,
        )
        entity_id = _helper_input_entity_id(f"grid_price_{direction_name}_risk_adjusted")
        attributes = dict(source_entity["attributes"])
        attributes["forecast"] = adjusted_forecast
        attributes["source_key"] = source_key
        attributes["haeo_helpers_transform"] = "forecast_risk_adjustment"
        attributes["haeo_helpers_basis_bias_pct"] = basis_bias_pct
        attributes["haeo_helpers_risk_bias_pct"] = risk_bias_pct
        attributes["haeo_helpers_ramp_start_after_minutes"] = ramp_start_after_minutes
        attributes["haeo_helpers_ramp_duration_minutes"] = ramp_duration_minutes
        attributes["haeo_helpers_curve"] = curve
        result.append(
            {
                "entity_id": entity_id,
                "state": str(closest_value if closest_value is not None else source_entity["state"]),
                "attributes": attributes,
            }
        )
    return result


def _build_battery_stored_energy_value_entity(
    raw_name: str,
    element: dict[str, Any],
    *,
    input_payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a scalar input entity using forecast statistic helper semantics."""
    stored_energy_value = element.get("stored_energy_value")
    if isinstance(stored_energy_value, int | float):
        value = float(stored_energy_value)
        source_key = None
        statistic = AGGREGATION_PERCENTILE
    elif isinstance(stored_energy_value, dict):
        source_key = _source_ref_to_input_key(stored_energy_value.get("source"))
        statistic = str(stored_energy_value.get("statistic", "median"))
        source_entity = _entity_from_input_key(source_key, input_payload) if source_key else None
        if source_entity is None:
            return None
        forecast = source_entity["attributes"].get("forecast")
        if not isinstance(forecast, list):
            return None
        values = [
            float(point["value"])
            for point in forecast
            if isinstance(point, dict)
            and isinstance(point.get("value"), int | float)
            and not isinstance(point.get("value"), bool)
            and math.isfinite(float(point["value"]))
        ]
        if not values:
            return None
        if statistic == AGGREGATION_MEAN:
            value = sum(values) / len(values)
        else:
            value = _calculate_percentile(values, 50.0)
    else:
        return None
    entity_id = _helper_input_entity_id(f"{raw_name}_stored_energy_value")
    return {
        "entity_id": entity_id,
        "state": str(max(0.0, value)),
        "attributes": {
            "source_key": source_key,
            "kind": "price",
            "unit_of_measurement": "$/kWh",
            "device_class": "monetary",
            "haeo_helpers_transform": "forecast_statistic",
            "haeo_helpers_statistic": statistic,
        },
    }


def _build_participant_from_plant_element(
    raw_name: str,
    element: dict[str, Any],
    *,
    input_keys: set[str],
) -> dict[str, Any] | None:
    """Map EA plant element config into HAEO participant config."""
    name = _titleize(raw_name)
    element_type = str(element.get("type", "node"))

    if element_type == "switchboard":
        return {
            "name": name,
            "element_type": "node",
            "role": {"is_sink": False, "is_source": False},
        }

    if element_type == "grid":
        constraints = element.get("constraints", {})
        price_import_src = _source_ref_to_input_key(element.get("price_import", {}).get("source"))
        price_export_src = _source_ref_to_input_key(element.get("price_export", {}).get("source"))
        return {
            "name": name,
            "element_type": "grid",
            "connection": {"type": "connection_target", "value": _titleize(str(element.get("connection", "switchboard")))},
            "power_limits": {
                "max_power_source_target": {
                    "type": "constant",
                    "value": float(constraints.get("max_import_kw", 13.0)),
                },
                "max_power_target_source": {
                    "type": "constant",
                    "value": float(constraints.get("max_export_kw", 13.0)),
                },
            },
            "pricing": {
                "price_source_target": _entity_or_constant(
                    _risk_adjusted_source_key("import", price_import_src, element.get("price_import", {})),
                    input_keys,
                    fallback=0.25,
                ),
                "price_target_source": _entity_or_constant(
                    _risk_adjusted_source_key("export", price_export_src, element.get("price_export", {})),
                    input_keys,
                    fallback=0.08,
                ),
            },
        }

    if element_type in {"load", "load_controlled_ev"}:
        source = _source_ref_to_input_key(element.get("power"))
        if source is None and element_type == "load_controlled_ev":
            source = _source_ref_to_input_key(element.get("realtime_power"))
        return {
            "name": name,
            "element_type": "load",
            "connection": {"type": "connection_target", "value": _titleize(str(element.get("connection", "switchboard")))},
            "forecast": {
                "forecast": _entity_or_constant(source, input_keys, fallback=0.0),
            },
            "curtailment": {},
            "pricing": {},
        }

    if element_type == "inverter":
        peak_power = float(element.get("peak_power_kw", 10.0))
        return {
            "name": name,
            "element_type": "inverter",
            "connection": {"type": "connection_target", "value": _titleize(str(element.get("connection", "switchboard")))},
            "efficiency": {
                "efficiency_source_target": {"type": "constant", "value": 1.0},
                "efficiency_target_source": {"type": "constant", "value": 1.0},
            },
            "power_limits": {
                "max_power_source_target": {"type": "constant", "value": peak_power},
                "max_power_target_source": {"type": "constant", "value": peak_power},
            },
        }

    if element_type == "pv":
        source = _source_ref_to_input_key(element.get("forecast"))
        return {
            "name": name,
            "element_type": "solar",
            "connection": {"type": "connection_target", "value": _titleize(str(element.get("connection", "switchboard")))},
            "forecast": {
                "forecast": _entity_or_constant(source, input_keys, fallback=0.0),
            },
            "curtailment": {"curtailment": {"type": "constant", "value": True}},
            "pricing": {},
        }

    if element_type == "battery":
        soc_src = _source_ref_to_input_key(element.get("state_of_charge_pct"))
        capacity = float(element.get("capacity_kwh", 10.0))
        min_soc = float(element.get("min_soc_pct", 10.0))
        max_soc = float(element.get("max_soc_pct", 100.0))
        charge_kw = float(element.get("max_charge_kw", 5.0))
        discharge_kw = float(element.get("max_discharge_kw", 5.0))
        efficiency_pct = float(element.get("storage_efficiency_pct", 95.0))
        stored_energy_value_src = f"{raw_name}_stored_energy_value"
        return {
            "name": name,
            "element_type": "battery",
            "connection": {"type": "connection_target", "value": _titleize(str(element.get("connection", "switchboard")))},
            "efficiency": {
                "efficiency_source_target": {"type": "constant", "value": efficiency_pct},
                "efficiency_target_source": {"type": "constant", "value": efficiency_pct},
            },
            "limits": {
                "min_charge_percentage": {"type": "constant", "value": min_soc},
                "max_charge_percentage": {"type": "constant", "value": max_soc},
            },
            "power_limits": {
                "max_power_source_target": {"type": "constant", "value": discharge_kw},
                "max_power_target_source": {"type": "constant", "value": charge_kw},
            },
            "pricing": {
                "price_source_target": {"type": "constant", "value": float(element.get("discharge_cost_per_kwh", 0.0))},
                "price_target_source": {"type": "constant", "value": float(element.get("charge_cost_per_kwh", 0.0))},
                "salvage_value": _entity_or_constant(
                    stored_energy_value_src,
                    input_keys | {stored_energy_value_src},
                    fallback=0.0,
                ),
            },
            "storage": {
                "capacity": {"type": "constant", "value": capacity},
                "initial_charge_percentage": _entity_or_constant(soc_src, input_keys, fallback=50.0),
            },
            "partitioning": {},
        }

    return None


def _entity_or_constant(source_key: str | None, input_keys: set[str], *, fallback: float) -> dict[str, Any]:
    """Build HAEO source reference as entity when available, else constant."""
    if source_key is not None and source_key in input_keys:
        return {"type": "entity", "value": [f"sensor.ea_{source_key}"]}
    return {"type": "constant", "value": fallback}


def _risk_adjusted_source_key(direction_name: str, source_key: str | None, price_config: Any) -> str | None:
    """Return helper-adjusted source key when the EA price config has filters."""
    if source_key is None:
        return None
    if isinstance(price_config, dict) and price_config.get("filters"):
        return f"grid_price_{direction_name}_risk_adjusted"
    return source_key


def _helper_input_entity_id(source_key: str) -> str:
    """Return the scenario entity ID for a helper-produced input key."""
    return f"sensor.ea_{source_key}"


def _entity_from_input_key(source_key: str | None, input_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Build a diagnostics-style entity from a raw EA input key."""
    if source_key is None:
        return None
    registry = input_payload.get("inputs", {})
    if not isinstance(registry, dict) or source_key not in registry:
        return None
    for entity in _build_inputs_from_ea_input_payload({"inputs": {source_key: registry[source_key]}}, config_payload={}):
        return entity
    return None


def _source_ref_to_input_key(value: Any) -> str | None:
    """Extract EA input key from refs like 'inputs.grid_price_import'."""
    if not isinstance(value, str):
        return None
    if not value.startswith("inputs."):
        return None
    return value.split(".", 1)[1]


def _titleize(value: str) -> str:
    """Convert snake_case names to titleized labels."""
    return " ".join(part.capitalize() for part in value.split("_"))


