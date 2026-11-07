"""Tests for project serialization and loading."""

from pathlib import Path

from ila_manager.models import Ila, Probe, ProbeMapping, Project
from ila_manager.project_io import load_project, save_project


def test_save_and_load_project(tmp_path: Path):
    proj_file = tmp_path / "test.ilaproj"
    dummy_hdl = tmp_path / "dummy.vhd"
    dummy_hdl.write_text("library ieee;", encoding="utf-8")

    project = Project(
        version=1,
        source_files=[str(dummy_hdl)],
        ilas=[
            Ila(
                name="ila_core",
                pipe_stages=4,
                probes=[
                    Probe(index=0, mapping=ProbeMapping(signal="clk"), width=1),
                    Probe(index=1, mapping=ProbeMapping(signal="data"), width=16),
                ],
            )
        ],
    )

    save_project(project, str(proj_file))
    assert proj_file.is_file()

    loaded, missing = load_project(str(proj_file))
    assert len(missing) == 0
    assert len(loaded.ilas) == 1
    assert loaded.ilas[0].name == "ila_core"
    assert loaded.ilas[0].pipe_stages == 4
    assert len(loaded.ilas[0].probes) == 2
    assert loaded.ilas[0].probes[1].width == 16
