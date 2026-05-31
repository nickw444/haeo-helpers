"""CLI entrypoint for importing and running native scenario fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from tools.scenario_runner.energy_assistant_importer import import_energy_assistant_capture
from tools.scenario_runner.comparison import compare_scenario_outputs
from tools.scenario_runner.graphing import render_rows_svg
from tools.scenario_runner.haeo_native import run_native_haeo
from tools.scenario_runner.haeo_visuals import render_with_haeo_tooling
from tools.scenario_runner.fixtures import load_native_fixture
from tools.scenario_runner.runner import run_haeo_scenario


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_scenario",
        description="Import and execute native HAEO scenario fixtures.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a native scenario fixture")
    run_parser.add_argument("fixture_path", type=Path, help="Fixture directory or scenario.json path")
    run_parser.add_argument(
        "--runner",
        choices=["native", "cli"],
        default="native",
        help="Execution backend for HAEO scenario runs",
    )
    run_parser.add_argument(
        "--diag-command",
        default="diag",
        help="Path or command name for HAEO diag executable",
    )
    run_parser.add_argument(
        "--outputs-file",
        type=Path,
        default=None,
        help="Optional path to persist generated HAEO outputs JSON",
    )
    run_parser.add_argument(
        "--graph-file",
        type=Path,
        default=None,
        help="Optional path to render an SVG graph from HAEO rows",
    )

    import_parser = subparsers.add_parser("import-ea", help="One-time import from energy-assistant capture")
    import_parser.add_argument("source_path", type=Path, help="EA capture file or directory")
    import_parser.add_argument("destination_path", type=Path, help="Target scenario.json path")
    import_parser.add_argument("--name", required=True, help="Scenario display name")
    import_parser.add_argument("--timezone", default="UTC", help="Timezone metadata for the fixture")

    import_all_parser = subparsers.add_parser(
        "import-ea-batch",
        help="Bulk-import energy-assistant scenario directories",
    )
    import_all_parser.add_argument(
        "source_root",
        type=Path,
        help="EA root directory containing scenario subdirectories",
    )
    import_all_parser.add_argument(
        "destination_root",
        type=Path,
        help="Target root for native scenario fixture directories",
    )
    import_all_parser.add_argument("--timezone", default="UTC", help="Timezone metadata for imported fixtures")

    run_batch_parser = subparsers.add_parser(
        "run-batch",
        help="Run all native scenarios under a root directory",
    )
    run_batch_parser.add_argument("scenario_root", type=Path, help="Root containing */scenario.json fixtures")
    run_batch_parser.add_argument(
        "--runner",
        choices=["native", "cli"],
        default="native",
        help="Execution backend for HAEO scenario runs",
    )
    run_batch_parser.add_argument(
        "--outputs-dir",
        type=Path,
        required=False,
        default=None,
        help="Directory to write per-scenario HAEO outputs JSON (defaults alongside each scenario)",
    )
    run_batch_parser.add_argument(
        "--diag-command",
        default="diag",
        help="Path or command name for HAEO diag executable",
    )
    run_batch_parser.add_argument(
        "--render-graphs",
        action="store_true",
        help="Render SVG graph alongside each generated HAEO output file",
    )
    run_batch_parser.add_argument(
        "--haeo-repo-path",
        type=Path,
        default=Path(".haeo_upstream"),
        help="Path to cloned HAEO repository for upstream visualization tooling",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare EA source output points with HAEO output points for a scenario",
    )
    compare_parser.add_argument("fixture_path", type=Path, help="Fixture directory or scenario.json path")
    compare_parser.add_argument("haeo_outputs_file", type=Path, help="HAEO output JSON file path")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the scenario CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        result = run_haeo_scenario(
            args.fixture_path,
            runner=args.runner,
            diag_command=(args.diag_command,),
        )
        if args.outputs_file is not None:
            args.outputs_file.parent.mkdir(parents=True, exist_ok=True)
            args.outputs_file.write_text(json.dumps({"outputs": result.outputs}, indent=2) + "\n")
        if args.graph_file is not None:
            rows = result.outputs.get("haeo_rows", [])
            if isinstance(rows, list):
                args.graph_file.parent.mkdir(parents=True, exist_ok=True)
                render_rows_svg(rows=rows, path=args.graph_file, title=str(args.fixture_path))
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.return_code

    if args.command == "import-ea":
        output_path = import_energy_assistant_capture(
            source_path=args.source_path,
            destination_path=args.destination_path,
            scenario_name=args.name,
            timezone=args.timezone,
        )
        print(f"Wrote fixture: {output_path}")
        return 0

    if args.command == "import-ea-batch":
        source_root: Path = args.source_root
        destination_root: Path = args.destination_root
        imported = 0
        for scenario_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
            destination_path = destination_root / scenario_dir.name / "scenario.json"
            output_path = import_energy_assistant_capture(
                source_path=scenario_dir,
                destination_path=destination_path,
                scenario_name=scenario_dir.name,
                timezone=args.timezone,
            )
            imported += 1
            print(f"Wrote fixture: {output_path}")
        print(f"Imported {imported} scenarios.")
        return 0

    if args.command == "run-batch":
        scenario_files = sorted(args.scenario_root.glob("*/scenario.json"))
        if not scenario_files:
            print("No scenario files found.", file=sys.stderr)
            return 1

        failures = 0
        for scenario_file in scenario_files:
            result = run_haeo_scenario(
                scenario_file,
                runner=args.runner,
                diag_command=(args.diag_command,),
            )
            if args.outputs_dir is None:
                out_path = scenario_file.parent / "haeo_outputs.json"
            else:
                out_path = args.outputs_dir / scenario_file.parent.name / "haeo_outputs.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps({"outputs": result.outputs}, indent=2) + "\n")
            if args.render_graphs:
                if args.runner == "native":
                    fixture = load_native_fixture(scenario_file)
                    output_sensors, network = run_native_haeo(fixture)
                    try:
                        render_with_haeo_tooling(
                            output_sensors=output_sensors,
                            scenario_name=scenario_file.parent.name,
                            output_dir=out_path.parent / "visualizations",
                            network=network,
                            haeo_repo_path=args.haeo_repo_path,
                        )
                        fallback_graph = out_path.parent / "haeo_output_graph.svg"
                        if fallback_graph.exists():
                            fallback_graph.unlink()
                    except Exception as exc:
                        print(f"[{scenario_file.parent.name}] warning: upstream visualization failed: {exc}")
                        rows = result.outputs.get("haeo_rows", [])
                        if isinstance(rows, list):
                            render_rows_svg(
                                rows=rows,
                                path=out_path.parent / "haeo_output_graph.svg",
                                title=scenario_file.parent.name,
                            )
                else:
                    rows = result.outputs.get("haeo_rows", [])
                    if isinstance(rows, list):
                        render_rows_svg(
                            rows=rows,
                            path=out_path.parent / "haeo_output_graph.svg",
                            title=scenario_file.parent.name,
                        )
            print(f"[{scenario_file.parent.name}] return_code={result.return_code} outputs={out_path}")
            if result.return_code != 0:
                failures += 1
        return 1 if failures else 0

    if args.command == "compare":
        comparison = compare_scenario_outputs(
            scenario_path=args.fixture_path,
            haeo_outputs_path=args.haeo_outputs_file,
        )
        print(f"scenario={comparison.scenario_name}")
        print(f"ea_output_points={comparison.ea_output_points}")
        print(f"haeo_output_points={comparison.haeo_output_points}")
        for note in comparison.notes:
            print(f"note={note}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
