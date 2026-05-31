# HAEO Diagnostics Mapping Reference

This document records the diagnostics shape targeted by the `haeo-helpers` scenario runner.
It is based on HAEO's `diag` tooling and the public scenario fixture example from
`hass-energy/haeo` (`tests/scenarios/scenario1`).

## Required sections

The scenario runner writes a diagnostics payload with:

- `config` (object)
- `environment` (object)
- `inputs` (array of entity states)
- `outputs` (object, optional for precomputed output baselines)

The runner writes a unified payload compatible with HAEO's diagnostics loader:

```json
{
  "data": {
    "config": {},
    "environment": {},
    "inputs": [],
    "outputs": {}
  }
}
```

## Concrete sample fields

### `config`

Representative fields observed in HAEO scenario data:

```json
{
  "minor_version": 3,
  "tier_1_count": 5,
  "tier_1_duration": 1,
  "version": 1,
  "participants": {
    "Battery": {
      "name": "Battery",
      "element_type": "battery"
    },
    "Grid": {
      "name": "Grid",
      "element_type": "grid"
    }
  }
}
```

### `environment`

Representative fields:

```json
{
  "diagnostic_request_time": "2025-10-05T10:59:21.998507+00:00",
  "ha_version": "2025.9.4",
  "haeo_version": "0.1.0",
  "timezone": "UTC"
}
```

### `inputs`

Each item is an entity snapshot with attributes that may include forecast data:

```json
[
  {
    "entity_id": "sensor.energy_production_d2_east",
    "state": "20.07175",
    "attributes": {
      "watts": {
        "2025-10-07T00:00:00+11:00": 0,
        "2025-10-07T00:15:00+11:00": 0
      }
    }
  }
]
```

## Native fixture to diagnostics mapping

`haeo-helpers` stores native fixtures at `tests/data/scenarios/.../scenario.json` with this structure:

```json
{
  "schema_version": 1,
  "metadata": {},
  "source": {},
  "haeo": {
    "config": {},
    "environment": {},
    "inputs": [],
    "outputs": {}
  }
}
```

At runtime, `tools/scenario_runner/diagnostics_builder.py` maps `haeo.config`,
`haeo.environment`, `haeo.inputs`, and `haeo.outputs` directly into HAEO diagnostics payload sections.