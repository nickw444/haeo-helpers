"""Run HAEO in-process and emit raw HAEO-style outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.const import PERCENTAGE

from custom_components.haeo.const import (
    OUTPUT_NAME_OPTIMIZATION_COST,
    OUTPUT_NAME_OPTIMIZATION_DURATION,
    OUTPUT_NAME_OPTIMIZATION_STATUS,
)
from custom_components.haeo.coordinator.coordinator import _build_coordinator_output
from custom_components.haeo.core.adapters.registry import ELEMENT_TYPES, collect_model_elements
from custom_components.haeo.core.const import CONF_ELEMENT_TYPE
from custom_components.haeo.core.data.forecast_times import generate_forecast_timestamps, tiers_to_periods_seconds
from custom_components.haeo.core.data.loader.config_loader import load_element_config
from custom_components.haeo.core.model import Network, OutputData, OutputType
from custom_components.haeo.elements import (
    get_input_fields,
    get_list_input_fields,
    get_nested_config_value_by_path,
    iter_input_field_paths,
)
from custom_components.haeo.entities.plot_metadata import SOURCE_ROLE_KEY, SOURCE_ROLE_OUTPUT, classify_source_role
import numpy as np

from tools.scenario_runner.models import NativeScenarioFixture


def run_native_haeo(fixture: NativeScenarioFixture) -> tuple[dict[str, Any], Network]:
    """Run optimization and return HAEO-like sensor outputs plus network object."""
    config = fixture.config
    participants_config = config.get("participants", {})
    environment = fixture.environment
    start_str = str(environment.get("optimization_start_time") or environment.get("horizon_start") or "")
    start_ts = datetime.fromisoformat(start_str).timestamp() if start_str else datetime.now(UTC).timestamp()

    periods_seconds = tiers_to_periods_seconds(config, start_time=start_ts)
    forecast_times = generate_forecast_timestamps(periods_seconds, start_ts)

    class _StateProvider:
        def __init__(self, inputs: list[dict[str, Any]]) -> None:
            self._states = {item.get("entity_id"): item for item in inputs if item.get("entity_id")}

        def get(self, entity_id: str) -> Any:
            data = self._states.get(entity_id)
            if data is None:
                return None
            return type(
                "DiagEntityState",
                (),
                {
                    "entity_id": data["entity_id"],
                    "state": str(data.get("state", "unknown")),
                    "attributes": data.get("attributes", {}),
                },
            )()

    sp = _StateProvider(fixture.inputs)
    loaded = {
        name: load_element_config(name, cfg, sp, forecast_times)
        for name, cfg in participants_config.items()
    }

    periods_hours = np.asarray(periods_seconds, dtype=float) / 3600.0
    network = Network(name=str(fixture.metadata.get("name", "scenario")), periods=periods_hours)
    for elem in collect_model_elements(loaded):
        network.add(elem)
    cost = float(network.optimize())

    model_outputs = {element_name: element.outputs() for element_name, element in network.elements.items()}
    sensor_outputs: dict[str, Any] = {}

    for element_name, element_config in loaded.items():
        element_type = element_config[CONF_ELEMENT_TYPE]
        adapter_outputs = ELEMENT_TYPES[element_type].outputs(
            name=element_name,
            model_outputs=model_outputs,
            config=element_config,
            periods=network.periods,
        )
        for device_name, outputs in adapter_outputs.items():
            for output_name, output_data in outputs.items():
                coordinator_output = _build_coordinator_output(
                    output_name,
                    output_data,
                    forecast_times=forecast_times,
                    currency_sym="$",
                )
                state_value = coordinator_output.state
                if coordinator_output.unit == "%" and state_value is not None:
                    state_value = float(state_value) * 100.0
                forecast = coordinator_output.forecast or []
                serialized_forecast = [
                    {
                        "time": point["time"].isoformat(),
                        "value": (float(point["value"]) * 100.0 if coordinator_output.unit == "%" else point["value"]),
                    }
                    for point in forecast
                ]
                entity_id = f"sensor.{_slug(element_name)}_{_slug(device_name)}_{_slug(str(output_name))}"
                sensor_outputs[entity_id] = {
                    "entity_id": entity_id,
                    "state": None if state_value is None else str(state_value),
                    "attributes": {
                        "element_name": element_name,
                        "element_type": str(element_type),
                        "output_name": str(output_name),
                        "field_type": str(coordinator_output.type),
                        SOURCE_ROLE_KEY: SOURCE_ROLE_OUTPUT,
                        "advanced": coordinator_output.advanced,
                        "forecast": serialized_forecast,
                    },
                }
                attributes = sensor_outputs[entity_id]["attributes"]
                if coordinator_output.direction is not None:
                    attributes["direction"] = coordinator_output.direction
                if coordinator_output.unit is not None:
                    attributes["unit_of_measurement"] = coordinator_output.unit
                if coordinator_output.device_class is not None:
                    attributes["device_class"] = str(coordinator_output.device_class)
                if coordinator_output.state_class is not None:
                    attributes["state_class"] = str(coordinator_output.state_class)
                if coordinator_output.priority is not None:
                    attributes["priority"] = coordinator_output.priority
                if coordinator_output.fixed:
                    attributes["fixed"] = True

    _add_input_field_outputs(
        sensor_outputs=sensor_outputs,
        loaded_configs=loaded,
        raw_configs=participants_config,
        forecast_times=forecast_times,
    )

    duration = 0.0
    sensor_outputs["sensor.network_optimization_cost"] = {
        "entity_id": "sensor.network_optimization_cost",
        "state": str(cost),
        "attributes": {"output_name": OUTPUT_NAME_OPTIMIZATION_COST},
    }
    sensor_outputs["sensor.network_optimization_status"] = {
        "entity_id": "sensor.network_optimization_status",
        "state": "success",
        "attributes": {"output_name": OUTPUT_NAME_OPTIMIZATION_STATUS},
    }
    sensor_outputs["sensor.network_optimization_duration"] = {
        "entity_id": "sensor.network_optimization_duration",
        "state": str(duration),
        "attributes": {"output_name": OUTPUT_NAME_OPTIMIZATION_DURATION, "field_type": str(OutputType.DURATION)},
    }

    return sensor_outputs, network


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace(":", "_")


def _add_input_field_outputs(
    *,
    sensor_outputs: dict[str, Any],
    loaded_configs: dict[str, Any],
    raw_configs: dict[str, Any],
    forecast_times: tuple[float, ...],
) -> None:
    """Add HAEO-style input/config entities used by the forecast card."""
    for element_name, loaded_config in loaded_configs.items():
        raw_config = raw_configs[element_name]
        input_fields = {
            **get_input_fields(raw_config),
            **get_list_input_fields(raw_config),
        }
        for field_path, field_info in iter_input_field_paths(input_fields):
            if not field_info.time_series:
                continue

            loaded_value = get_nested_config_value_by_path(loaded_config, field_path)
            if loaded_value is None:
                continue

            values = _as_value_list(loaded_value)
            if not values:
                continue

            native_unit = getattr(field_info.entity_description, "native_unit_of_measurement", None)
            if native_unit == PERCENTAGE:
                values = [value * 100.0 for value in values]

            timestamps = forecast_times if field_info.boundaries else forecast_times[:-1]
            forecast = [
                {"time": datetime.fromtimestamp(timestamp, tz=UTC).isoformat(), "value": value}
                for timestamp, value in zip(timestamps, values, strict=False)
            ]
            if len(forecast) < 2:
                continue

            raw_value = get_nested_config_value_by_path(raw_config, field_path)
            config_mode = _config_mode(raw_value)
            state_value = forecast[0]["value"]
            entity_domain = "number"
            entity_id = f"{entity_domain}.{_slug(element_name)}_{_slug(field_info.field_name)}"
            attributes: dict[str, Any] = {
                "config_mode": config_mode,
                SOURCE_ROLE_KEY: classify_source_role(config_mode, field_info.field_name),
                "element_name": element_name,
                "element_type": str(loaded_config[CONF_ELEMENT_TYPE]),
                "field_name": field_info.field_name,
                "field_type": str(field_info.output_type),
                "time_series": field_info.time_series,
                "forecast": forecast,
            }
            if native_unit is not None:
                attributes["unit_of_measurement"] = native_unit
            if field_info.direction is not None:
                attributes["direction"] = field_info.direction

            sensor_outputs[entity_id] = {
                "entity_id": entity_id,
                "state": str(state_value),
                "attributes": attributes,
            }


def _as_value_list(value: Any) -> list[float]:
    """Convert scalar or vector loaded HAEO values into a list of floats."""
    if isinstance(value, np.ndarray):
        return [float(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]
    if isinstance(value, (float, int)):
        return [float(value)]
    return []


def _config_mode(value: Any) -> str:
    """Return HAEO config entity mode for a raw schema value."""
    if isinstance(value, dict) and value.get("type") == "entity":
        return "driven"
    return "editable"
