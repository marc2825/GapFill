#!/usr/bin/env python3
"""Black-box regressions for Phase 3 CSP CLI safety invariants."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run(*values: object, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(value) for value in values],
        check=False,
        capture_output=True,
        text=True,
    )
    if (result.returncode == 0) != expect_success:
        raise AssertionError(
            f"unexpected exit {result.returncode}: {' '.join(map(str, values))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def outputs(directory: Path, prefix: str) -> list[str]:
    return [
        "--correction",
        str(directory / f"{prefix}-correction.png"),
        "--corrected",
        str(directory / f"{prefix}-corrected.png"),
        "--manifest",
        str(directory / f"{prefix}-manifest.json"),
        "--contact-sheet",
        str(directory / f"{prefix}-review.png"),
        "--no-highlight",
    ]


def all_output_paths(directory: Path, prefix: str) -> dict[str, Path]:
    return {
        "--correction": directory / f"{prefix}-correction.png",
        "--highlight": directory / f"{prefix}-highlight.png",
        "--corrected": directory / f"{prefix}-corrected.png",
        "--manifest": directory / f"{prefix}-manifest.json",
        "--contact-sheet": directory / f"{prefix}-review.png",
        "--save-settings": directory / f"{prefix}-settings.ini",
    }


def flatten(paths: dict[str, Path]) -> list[str]:
    result: list[str] = []
    for option, path in paths.items():
        result.extend((option, str(path)))
    return result


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: phase3_cli_safety.py CLI CLI_FIXTURE")
    cli = Path(sys.argv[1]).resolve()
    fixture = Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory(prefix="gap-assist-phase3-") as temporary:
        root = Path(temporary)

        alias_dir = root / "input-alias"
        alias_dir.mkdir()
        source = alias_dir / "source.png"
        run(fixture, "create", source)
        original = source.read_bytes()
        alias_outputs = outputs(alias_dir, "alias")
        alias_outputs[1] = str(source)
        run(cli, "--input", source, *alias_outputs, expect_success=False)
        if source.read_bytes() != original:
            raise AssertionError("input/output alias changed the source bytes")

        for role in all_output_paths(alias_dir, "input-role"):
            paths = all_output_paths(alias_dir, role.removeprefix("--"))
            paths[role] = source
            run(cli, "--input", source, *flatten(paths), expect_success=False)
            if source.read_bytes() != original:
                raise AssertionError(f"{role} input alias changed the source bytes")

        roles = list(all_output_paths(alias_dir, "roles"))
        for left_index, left in enumerate(roles):
            for right in roles[left_index + 1 :]:
                paths = all_output_paths(
                    alias_dir, f"pair-{left.removeprefix('--')}-{right.removeprefix('--')}"
                )
                shared = alias_dir / "shared-output"
                paths[left] = shared
                paths[right] = shared
                run(cli, "--input", source, *flatten(paths), expect_success=False)
                if source.read_bytes() != original:
                    raise AssertionError("inter-output collision changed the source bytes")

        order_dir = root / "settings-order"
        order_dir.mkdir()
        order_source = order_dir / "source.png"
        selection = order_dir / "selection.png"
        settings = order_dir / "settings.ini"
        run(fixture, "create", order_source)
        run(fixture, "create-selection", selection)
        settings.write_text("scope=whole\n", encoding="utf-8")
        first = run(
            cli,
            "--input",
            order_source,
            "--selection",
            selection,
            "--settings",
            settings,
            *outputs(order_dir, "first"),
        )
        second = run(
            cli,
            "--input",
            order_source,
            "--settings",
            settings,
            "--selection",
            selection,
            *outputs(order_dir, "second"),
        )
        if first.stdout != second.stdout:
            raise AssertionError("moving --settings changed the effective CLI result")
        for suffix in ("correction.png", "corrected.png", "manifest.json", "review.png"):
            if (order_dir / f"first-{suffix}").read_bytes() != (
                order_dir / f"second-{suffix}"
            ).read_bytes():
                raise AssertionError(f"moving --settings changed {suffix} bytes")

        decision_dir = root / "decision-precedence"
        decision_dir.mkdir()
        decision_source = decision_dir / "source.png"
        decisions = decision_dir / "decisions.txt"
        run(fixture, "create", decision_source)
        decisions.write_text("0=skip\n", encoding="utf-8")
        decision = run(
            cli,
            "--input",
            decision_source,
            "--decisions",
            decisions,
            "--apply-high",
            *outputs(decision_dir, "decision"),
        )
        if "Applied: 0" not in decision.stdout:
            raise AssertionError("--apply-high overrode an explicit Skip")

        decisions.write_text("0=mark_only\n", encoding="utf-8")
        marked = run(
            cli,
            "--input",
            decision_source,
            "--decisions",
            decisions,
            "--apply-high",
            *outputs(decision_dir, "marked"),
        )
        if "Applied: 0" not in marked.stdout:
            raise AssertionError("--apply-high overrode an explicit Mark")

        force_dir = root / "force"
        force_dir.mkdir()
        force_source = force_dir / "source.png"
        run(fixture, "create", force_source)
        force_original = force_source.read_bytes()
        force_outputs = outputs(force_dir, "result")
        run(cli, "--input", force_source, *force_outputs)
        previous = {
            path.name: path.read_bytes()
            for path in force_dir.iterdir()
            if path != force_source
        }
        run(
            cli,
            "--input",
            force_source,
            *force_outputs,
            expect_success=False,
        )
        current = {
            path.name: path.read_bytes()
            for path in force_dir.iterdir()
            if path != force_source
        }
        if current != previous:
            raise AssertionError("default existing-output refusal changed outputs")
        run(cli, "--input", force_source, *force_outputs, "--force")
        if force_source.read_bytes() != force_original:
            raise AssertionError("--force changed the input source")


if __name__ == "__main__":
    main()
