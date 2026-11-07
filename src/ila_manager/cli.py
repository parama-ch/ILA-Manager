"""Command line interface for ILA Manager."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from ila_manager import __version__
from ila_manager.generators import generate_tcl, generate_verilog, generate_vhdl
from ila_manager.parser import parse_verilog, parse_vhdl
from ila_manager.project_io import load_project


def open_browser_delayed(url: str, delay: float = 1.0) -> None:
    """Open default browser in a background thread after the server has booted."""
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    t = threading.Thread(target=_open, daemon=True)
    t.start()


def run_generate(args: argparse.Namespace) -> int:
    """Headless code generation from a .ilaproj file."""
    proj_path = Path(args.project).resolve()
    if not proj_path.is_file():
        print(f"ERROR: Project file not found: {proj_path}", file=sys.stderr)
        return 1

    project, missing = load_project(str(proj_path))
    if missing:
        print(f"WARNING: Missing HDL source files: {missing}", file=sys.stderr)

    ila = project.get_ila(args.ila) if args.ila else (project.ilas[0] if project.ilas else None)
    if not ila:
        print(f"ERROR: ILA '{args.ila}' not found in project.", file=sys.stderr)
        return 1

    # Parse signals from sources
    all_signals = []
    for sf in project.source_files:
        p = Path(sf)
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            parsed = parse_vhdl(text, filename=str(p)) if p.suffix.lower() in (".vhd", ".vhdl") else parse_verilog(text, filename=str(p))
            for sigs in parsed.values():
                all_signals.extend(sigs)

    tcl_code = generate_tcl(ila)
    vhdl_code = generate_vhdl(ila, signals=all_signals)
    verilog_code = generate_verilog(ila, signals=all_signals)

    out_dir = Path(args.out).resolve() if args.out else Path(".").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tcl_file = out_dir / f"{ila.name}.tcl"
    vhdl_file = out_dir / f"{ila.name}_inst.vhd"
    v_file = out_dir / f"{ila.name}_inst.v"

    tcl_file.write_text(tcl_code, encoding="utf-8")
    vhdl_file.write_text(vhdl_code, encoding="utf-8")
    v_file.write_text(verilog_code, encoding="utf-8")

    print(f"SUCCESS: Generated ILA artifacts in {out_dir}:")
    print(f"  - Vivado TCL:   {tcl_file.name}")
    print(f"  - VHDL Portmap: {vhdl_file.name}")
    print(f"  - Verilog Port: {v_file.name}")
    return 0


def run_parse(args: argparse.Namespace) -> int:
    """Headless HDL signal extractor returning JSON."""
    hdl_path = Path(args.file).resolve()
    if not hdl_path.is_file():
        print(f"ERROR: File not found: {hdl_path}", file=sys.stderr)
        return 1

    text = hdl_path.read_text(encoding="utf-8", errors="replace")
    is_vhdl = hdl_path.suffix.lower() in (".vhd", ".vhdl")
    parsed = parse_vhdl(text, filename=str(hdl_path)) if is_vhdl else parse_verilog(text, filename=str(hdl_path))

    out = {unit: [s.to_dict() for s in sigs] for unit, sigs in parsed.items()}
    print(json.dumps(out, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ila-manager",
        description="Visual port manager and Vivado TCL / HDL port-map generator for AMD Vivado ILA IP cores",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # Serve command (default)
    p_serve = subparsers.add_parser("serve", help="Start the ILA Manager web server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    p_serve.add_argument("--no-browser", action="store_true", help="Do not automatically open default browser")

    # Generate command
    p_gen = subparsers.add_parser("generate", help="Generate TCL and HDL port maps from a project file")
    p_gen.add_argument("project", help="Path to .ilaproj project file")
    p_gen.add_argument("--ila", help="Name of ILA to generate (default: first ILA in project)")
    p_gen.add_argument("--out", "-o", help="Output directory to write files (default: current directory)")

    # Parse command
    p_parse = subparsers.add_parser("parse", help="Extract signals from an HDL file and print as JSON")
    p_parse.add_argument("file", help="Path to HDL source file (.vhd, .vhdl, .v, .sv)")

    # Root flags
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")

    args = parser.parse_args()

    if args.command == "generate":
        sys.exit(run_generate(args))
    elif args.command == "parse":
        sys.exit(run_parse(args))
    else:
        # Default action: start web server
        host = args.host
        port = args.port
        url = f"http://{host}:{port}"
        print("============================================================")
        print(f"  ILA Manager v{__version__}")
        print(f"  Running at: {url}")
        print("============================================================")

        if not args.no_browser:
            open_browser_delayed(url)

        from ila_manager.server import app
        uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
