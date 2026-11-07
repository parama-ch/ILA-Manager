"""FastAPI web server and REST API for ILA Manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ila_manager.diff import compute_diff
from ila_manager.generators import generate_tcl, generate_verilog, generate_vhdl
from ila_manager.importers import import_from_hdl, import_from_tcl
from ila_manager.models import Ila, Project, Signal
from ila_manager.parser import parse_verilog, parse_vhdl
from ila_manager.project_io import load_project, save_project

app = FastAPI(
    title="ILA Manager API",
    description="Backend API for Vivado ILA IP configuration and HDL port mapping",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files path
WEB_DIR = Path(__file__).resolve().parent / "web"


# Request / Response Schemas
class FileContent(BaseModel):
    filename: str
    content: str


class ParseRequest(BaseModel):
    paths: Optional[List[str]] = None
    files: Optional[List[FileContent]] = None


class GenerateRequest(BaseModel):
    ila: Dict[str, Any]
    signals: Optional[List[Dict[str, Any]]] = None


class DiffRequest(BaseModel):
    ila: Dict[str, Any]
    signals: List[Dict[str, Any]]


class SaveProjectRequest(BaseModel):
    file_path: str
    project: Dict[str, Any]
    signals_by_unit: Optional[Dict[str, List[Dict[str, Any]]]] = None


class LoadProjectRequest(BaseModel):
    file_path: str


class ImportHdlRequest(BaseModel):
    content: str
    is_vhdl: bool = True


class ImportTclRequest(BaseModel):
    content: str


@app.post("/api/hdl/parse")
async def api_parse_hdl(req: ParseRequest) -> Dict[str, Any]:
    """Parse one or more HDL files provided by disk path or raw content."""
    units: Dict[str, List[Dict[str, Any]]] = {}
    parsed_files: List[str] = []

    # 1. Parse from on-disk paths
    if req.paths:
        for path_str in req.paths:
            p = Path(path_str)
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                ext = p.suffix.lower()
                is_vhdl = ext in (".vhd", ".vhdl")
                parsed = (
                    parse_vhdl(text, filename=str(p))
                    if is_vhdl
                    else parse_verilog(text, filename=str(p))
                )
                for unit_name, sig_list in parsed.items():
                    units[unit_name] = [s.to_dict() for s in sig_list]
                parsed_files.append(str(p))
            except Exception:
                pass

    # 2. Parse from uploaded contents
    if req.files:
        for f in req.files:
            ext = Path(f.filename).suffix.lower()
            is_vhdl = ext in (".vhd", ".vhdl")
            parsed = (
                parse_vhdl(f.content, filename=f.filename)
                if is_vhdl
                else parse_verilog(f.content, filename=f.filename)
            )
            for unit_name, sig_list in parsed.items():
                units[unit_name] = [s.to_dict() for s in sig_list]
            parsed_files.append(f.filename)

    return {"units": units, "files": parsed_files}


@app.post("/api/import/hdl-instance")
async def api_import_hdl_instance(req: ImportHdlRequest) -> List[Dict[str, Any]]:
    """Scan HDL content for existing ILA instances and return reconstructed Ila objects."""
    ilas = import_from_hdl(req.content, is_vhdl=req.is_vhdl)
    return [ila.to_dict() for ila in ilas]


@app.post("/api/import/tcl")
async def api_import_tcl(req: ImportTclRequest) -> Optional[Dict[str, Any]]:
    """Parse a Vivado TCL script and extract the ILA configuration."""
    ila = import_from_tcl(req.content)
    if not ila:
        raise HTTPException(status_code=400, detail="No ILA configuration found in TCL script.")
    return ila.to_dict()


@app.post("/api/generate")
async def api_generate(req: GenerateRequest) -> Dict[str, str]:
    """Generate Vivado TCL, VHDL port map, and Verilog port map."""
    ila = Ila.from_dict(req.ila)
    signals = [Signal.from_dict(s) for s in (req.signals or [])]

    tcl_code = generate_tcl(ila)
    vhdl_code = generate_vhdl(ila, signals=signals)
    verilog_code = generate_verilog(ila, signals=signals)

    return {
        "tcl": tcl_code,
        "vhdl": vhdl_code,
        "verilog": verilog_code,
    }


@app.post("/api/diff")
async def api_diff(req: DiffRequest) -> List[Dict[str, Any]]:
    """Check for discrepancies between ILA probes and current HDL signals."""
    ila = Ila.from_dict(req.ila)
    signals = [Signal.from_dict(s) for s in req.signals]
    diff_items = compute_diff(ila, signals)
    return [d.to_dict() for d in diff_items]


@app.post("/api/project/save")
async def api_save_project(req: SaveProjectRequest) -> Dict[str, str]:
    """Save a project to a .ilaproj JSON file."""
    try:
        project = Project.from_dict(req.project)
        sig_map = None
        if req.signals_by_unit:
            sig_map = {
                u: [Signal.from_dict(s) for s in slist]
                for u, slist in req.signals_by_unit.items()
            }
        save_project(project, req.file_path, signals_by_unit=sig_map)
        return {"status": "ok", "message": f"Saved project to {req.file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/project/load")
async def api_load_project(req: LoadProjectRequest) -> Dict[str, Any]:
    """Load a .ilaproj file and check for missing files."""
    try:
        project, missing_files = load_project(req.file_path)
        return {
            "project": project.to_dict(),
            "missing_files": missing_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fs/list")
async def api_fs_list(path: str = Query(".")) -> Dict[str, Any]:
    """List directory contents for the in-app file browser."""
    target = Path(path).resolve()
    if not target.exists() or not target.is_dir():
        target = Path(".").resolve()

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            # Skip hidden files
            if entry.name.startswith("."):
                continue
            is_dir = entry.is_dir()
            ext = entry.suffix.lower()
            is_hdl = ext in (".vhd", ".vhdl", ".v", ".sv", ".tcl", ".ilaproj")
            items.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": is_dir,
                "is_hdl": is_hdl,
                "size": entry.stat().st_size if not is_dir else 0,
            })
    except PermissionError:
        pass

    return {
        "current_path": str(target),
        "parent_path": str(target.parent) if target.parent != target else None,
        "items": items,
    }


@app.get("/api/i18n/{lang}")
async def api_i18n(lang: str) -> Dict[str, Any]:
    """Return translation dictionary for 'en' or 'th'."""
    i18n_file = WEB_DIR / "i18n" / f"{lang}.json"
    if not i18n_file.exists():
        i18n_file = WEB_DIR / "i18n" / "en.json"
    with open(i18n_file, "r", encoding="utf-8") as f:
        return json.load(f)


# Serve Web UI static files
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
