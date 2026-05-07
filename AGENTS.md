# Agent Notes

- Keep helper implementations organized by helper kind under
  `custom_components/haeo_helpers/helpers/<helper_kind>/`, not primarily by HA
  platform domain.
- This repository is intentionally a collection of small HAEO-adjacent helpers;
  avoid adding broad framework abstractions until there are multiple helpers
  with the same real need.
- Forecast-source helpers should treat the source entity's `forecast` attribute
  as the public contract and preserve/proxy non-forecast attributes unless the
  helper's purpose explicitly replaces them.
- For entity-vs-constant config inputs, use Home Assistant's `ChooseSelector`
  pattern. Its translation labels live under
  `selector.<translation_key>.choices`, not `options`.
- Use `scripts/test` for the local pytest suite. It is written to work even
  when the virtualenv is not shell-activated.
- `pytest-homeassistant-custom-component` can pull a mismatched Home Assistant
  version if left floating; keep the test dependency pinned to a version that
  supports the Home Assistant pin in `requirements.txt`.
