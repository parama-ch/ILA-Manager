"""Project serialization and deserialization for .ilaproj files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ila_manager.models import Project, Signal, SignalSnapshot


def save_project(
    project: Project,
    file_path: str,
    signals_by_unit: Optional[Dict[str, List[Signal]]] = None,
) -> None:
    """Save Project to a .ilaproj JSON file with relative paths."""
    proj_dir = Path(file_path).resolve().parent
    data = project.to_dict()

    # Convert source_files to relative paths where possible
    rel_sources: List[str] = []
    for sf in project.source_files:
        try:
            rel_sources.append(os.path.relpath(sf, proj_dir))
        except ValueError:
            rel_sources.append(sf)
    data["source_files"] = rel_sources

    # Update snapshots for each probe
    for ila in project.ilas:
        unit_sigs = (signals_by_unit or {}).get(ila.target_unit, [])
        sig_map = {s.name: s for s in unit_sigs}
        for probe in ila.probes:
            if probe.mapping:
                sig = sig_map.get(probe.mapping.signal)
                if sig:
                    probe.snapshot = SignalSnapshot(
                        name=sig.name,
                        width=probe.width,
                        kind=sig.kind,
                        type_summary=sig.type.summary(),
                    )

    # Re-serialize with updated snapshots
    data["ilas"] = [ila.to_dict() for ila in project.ilas]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_project(
    file_path: str,
) -> Tuple[Project, List[str]]:
    """Load Project from a .ilaproj JSON file, resolving relative paths.

    Returns:
        (project, missing_files)
    """
    proj_dir = Path(file_path).resolve().parent
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    project = Project.from_dict(data)

    resolved_sources: List[str] = []
    missing_files: List[str] = []

    for sf in project.source_files:
        p = Path(sf)
        if not p.is_absolute():
            p = (proj_dir / p).resolve()
        resolved_str = str(p)
        resolved_sources.append(resolved_str)
        if not p.exists():
            missing_files.append(resolved_str)

    project.source_files = resolved_sources
    return project, missing_files
