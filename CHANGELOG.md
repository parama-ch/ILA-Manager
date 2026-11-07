# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-07

### Added
- **HDL Parsers**:
  - VHDL parser (`.vhd`, `.vhdl`) supporting entities, architectures, generics, ports, signals, `std_logic`, `std_logic_vector`, `signed`, `unsigned`, custom types, 1D/2D arrays, and records.
  - Verilog / SystemVerilog parser (`.v`, `.sv`) supporting modules, ANSI and non-ANSI ports, parameters, wires, regs, logic, packed ranges, and unpacked arrays.
  - Safe expression evaluator for arithmetic constants, generics, and `$clog2` without Python `eval`.
- **ILA Port Manager**:
  - Interactive table with probe reordering via drag-and-drop or move buttons.
  - Direct probe swapping (e.g. `probe3` ⇄ `probe5`) via dedicated Swap button and Alt-drag.
  - Tree picker for hierarchical signals (arrays, records, and bit-slices).
  - Probe insertion at any position and append button.
  - Support for unmapped probes with placeholder comments and pre-generate warnings.
- **HDL Port-Map Generator**:
  - VHDL Direct Entity Instantiation (`u_<name> : entity work.<name>`) without component declarations.
  - Strict VHDL 1-bit vector mapping syntax (`probeN(0) => onebitsignal`).
  - Automatic VHDL type conversions (`unsigned`/`signed` to `std_logic_vector`) and intermediate signals for integers and enums.
  - Verilog / SystemVerilog named port mapping.
- **Smart Vivado TCL Generator**:
  - Self-checking script detecting existing IP (`create_ip` vs `set_property`).
  - Default `CONFIG.C_INPUT_PIPE_STAGES` = 4 (overriding Vivado's default of 1).
  - Probe width, probe type (0/1/2), and match unit configurations.
- **Import Capabilities**:
  - Scans HDL files for existing ILA instances to recover probe-to-signal bindings.
  - Parses existing Vivado TCL configuration scripts.
- **Diff & Sync Engine**:
  - Tracks signal width changes, deleted signals, and out-of-range slices on project reload.
  - Interactive Diff Review dialog with one-click resolution and fuzzy rename suggestions.
- **Web UI & CLI**:
  - Local FastAPI web application with Vanilla JS ES modules (no Node.js build step required).
  - Dark/Light EDA theme.
  - Bilingual interface (English & Thai) with instant language toggle.
  - Headless CLI commands for batch script generation.
