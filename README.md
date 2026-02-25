# HAEO Helpers

HAEO Helpers is a Home Assistant integration that will provide helper entities
to pair with [HAEO](https://github.com/hass-energy/haeo) and support equivalent
helper-oriented workflows to
[Energy Assistant](https://github.com/nickw444/energy-assistant).

This repository is currently tailored as a clean integration skeleton:
- `haeo_helpers` domain and config flow are in place.
- Integration metadata is aligned for this project.
- Functional behavior is intentionally deferred to follow-up work.

## Project layout

File | Purpose
-- | --
`.devcontainer.json` | Dev container config for local development.
`.github/workflows/*.yml` | CI workflows for linting and validation.
`custom_components/haeo_helpers/*` | Integration source code and config flow.
`config/configuration.yaml` | Development Home Assistant config.
`scripts/*` | Helper scripts for setup, linting, and local runs.

## Development

1. Open this repository in a dev container or local Python environment.
1. Run `scripts/setup`.
1. Run `scripts/develop` to start Home Assistant with this integration loaded.
1. Run `scripts/lint` before opening a pull request.

## Next steps

1. Implement HAEO-specific helper entity behavior.
1. Define how HAEO helpers map to Energy Assistant capabilities.
1. Add tests (for example with `pytest-homeassistant-custom-component`).
1. Add brand assets (logo/icon) via Home Assistant brands.
1. Publish releases and submit to HACS when ready.
