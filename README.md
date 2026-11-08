# ILA Manager 🔍

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AMD Vivado](https://img.shields.io/badge/EDA-AMD%20Vivado-red.svg)](https://www.xilinx.com/products/design-tools/vivado.html)
[![CI](https://github.com/parama-ch/ILA-Manager/actions/workflows/ci.yml/badge.svg)](https://github.com/parama-ch/ILA-Manager/actions)

> **English** | [ภาษาไทย](README.th.md)

**ILA Manager** is an open-source visual port manager and code generator for AMD/Xilinx Vivado Integrated Logic Analyzer (ILA) IP cores.

It eliminates manual, error-prone probe index bookkeeping in Vivado by letting FPGA engineers drag & drop HDL source files (VHDL, Verilog, SystemVerilog), pick signals down to bit-slices and array dimensions, reorder or swap probes (e.g. swap `probe3` ⇄ `probe5`), and automatically produce:
1. **A Smart Vivado TCL Script** (auto-detects create vs. update, defaults to **4 pipeline stages** for timing closure).
2. **Clean HDL Port-Map Snippets** (direct `entity work.<ila>` instantiation for VHDL with exact `probeN(0) => onebitsignal` vector syntax, and named port mapping for Verilog).
3. **Change Diffing & Sync**: detects when signal widths change or signals disappear in updated HDL files.

---

## Key Features

- **Drag & Drop HDL Parsing**:
  - Supports VHDL (`.vhd`, `.vhdl`), Verilog (`.v`), and SystemVerilog (`.sv`).
  - Resolves generics, parameters, and in-file package constants through a safe expression evaluator.
  - Supports 1-bit (`std_logic`, `bit`), vectors (`std_logic_vector`, `signed`, `unsigned`), 1D/2D arrays, and VHDL records.
- **Tree-Based Signal Picker**:
  - Drill down from signal → array index → record field → custom bit slice (e.g. `mem(2).data(15 downto 8)`).
- **Interactive ILA Port Manager**:
  - Reorder probes via drag & drop or move up/down buttons.
  - Direct probe swapping (e.g., `probe3` ⇄ `probe5`) via the Swap button or Alt-drag.
  - Insert new probes at any position or append signals directly.
  - Unmapped probes are preserved with placeholder comments and pre-generation warnings.
- **HDL Port-Map Generator**:
  - **VHDL Direct Entity Instantiation**: generates `u_<ila_name> : entity work.<ila_name>` without component declarations.
  - **VHDL 1-Bit Vector Syntax**: strictly maps single-bit signals as `probeN(0) => my_signal;` as required by Vivado's 1-bit vector probe ports.
  - **VHDL Type Conversion**: auto-converts `unsigned`/`signed` to `std_logic_vector`, and generates intermediate signals for `integer`/`natural`/`boolean`/`enum`.
  - **Verilog / SystemVerilog Instantiation**: generates clean `<ila_name> u_<ila_name> (...)` instances.
- **Smart Vivado TCL Script**:
  - Self-checking: runs `create_ip` if the IP does not exist, or updates via `set_property` if it already exists.
  - **Default `CONFIG.C_INPUT_PIPE_STAGES` = 4** (Vivado IP default is 1; 4 stages drastically improves timing closure at high clock frequencies).
  - Configurable probe types (`DATA AND TRIGGER`, `DATA ONLY`, `TRIGGER ONLY`).
  - Configurable match units (`ALL_PROBE_SAME_MU` toggle vs. individual `C_PROBE<N>_MU_CNT`).
  - Sample data depth (1024 to 131072) and Storage Qualification (`C_EN_STRG_QUAL`).
  - Version-agnostic (works across Vivado 2019.1 through 2024+).
- **Import Existing ILAs**:
  - Scans existing HDL files for instantiated ILA port maps to recover probe-to-signal bindings.
  - Parses existing Vivado TCL scripts.
- **Project Save / Load & Diff Sync**:
  - Saves project state as human-readable `.ilaproj` files (JSON).
  - Automatically re-scans HDL files on project open and presents an interactive **Diff Review dialog** if signals changed width or disappeared.
- **Bilingual (EN / TH)**:
  - Documentation available in English and Thai.
  - Web UI includes a real-time language switcher with English and Thai translations.
- **Zero Build Step Frontend**:
  - Pure Vanilla JavaScript ES modules and responsive CSS. No Node.js build required to install or develop.

---

## Installation

### Prerequisites
- Python 3.9 or higher.

### Install via pip / pipx
```bash
# Direct from GitHub
pip install git+https://github.com/parama-ch/ILA-Manager.git

# Or with pipx (recommended for isolated CLI tools)
pipx install git+https://github.com/parama-ch/ILA-Manager.git
```

### Development Installation
```bash
git clone https://github.com/parama-ch/ILA-Manager.git
cd ILA-Manager
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Launch the Web GUI
```bash
ila-manager
```
This starts the local server at `http://127.0.0.1:8765` and automatically opens your default browser.

To specify a port or disable browser auto-open:
```bash
ila-manager --port 9000 --no-browser
```

### 2. Workflow in the GUI
1. **Drop Sources**: Drag your Verilog / VHDL files into the left panel (or browse local directories).
2. **Select Target Unit**: Pick the module/architecture where the ILA will reside.
3. **Add & Reorder Probes**:
   - Click `+` on any signal or drag it onto the probe table.
   - Use the tree picker for arrays, record fields, or custom bit ranges (e.g. `[15:8]`).
   - Use the `⇄ Swap` button or drag probe cards to swap indices (e.g. `probe3` ⇄ `probe5`).
4. **Tune ILA Options**:
   - Set ILA name (e.g. `ila_0`), clock signal (`clk`), data depth (`1024`–`131072`), and probe types.
   - Notice that Flip-Flop Pipeline Stages defaults to **4** stages!
5. **Copy & Apply Output**:
   - **TCL Tab**: Click *Copy* and run `source ila_0.tcl` in Vivado's Tcl Console.
   - **HDL Tab**: Click *Copy* and paste the port map into your architecture/module body.

### 3. Headless CLI Mode (CI / Scripting)
You can also generate scripts directly from the command line:
```bash
# Generate TCL and VHDL snippets from a saved project
ila-manager generate examples/demo.ilaproj --ila ila_0 --out build/
```

---

## Generated Code Examples

### VHDL Direct Entity Instantiation
```vhdl
-- Generated by ILA Manager v0.1.0
-- Direct Entity Instantiation (no component declaration needed)
u_ila_0 : entity work.ila_0
    port map (
        clk       => clk,
        probe0(0) => rx_valid,                       -- 1-bit signal uses probe(0)
        probe1(0) => rx_status(3),                   -- Single bit from vector
        probe2    => rx_data(15 downto 8),           -- Sliced vector (8 bits)
        probe3    => rx_fifo_mem(2)(7 downto 0),     -- 2D array element slice
        probe4    => s_axis.tdata(31 downto 0),      -- Record field
        probe5    => std_logic_vector(packet_cnt_u)  -- unsigned -> slv conversion
    );
```

### Verilog / SystemVerilog Named Instantiation
```verilog
// Generated by ILA Manager v0.1.0
ila_0 u_ila_0 (
    .clk    (clk),
    .probe0 (rx_valid),
    .probe1 (rx_status[3]),
    .probe2 (rx_data[15:8]),
    .probe3 (rx_fifo_mem[2][7:0]),
    .probe4 (s_axis.tdata[31:0]),
    .probe5 (packet_cnt_u)
);
```

### Vivado TCL Configuration Script
```tcl
# Generated by ILA Manager v0.1.0 — ila_0 (6 probes)
set ila_name ila_0
if {[llength [get_ips -quiet $ila_name]] == 0} {
    create_ip -name ila -vendor xilinx.com -library ip -module_name $ila_name
}
set_property -dict [list \
    CONFIG.C_NUM_OF_PROBES       {6} \
    CONFIG.C_INPUT_PIPE_STAGES   {4} \
    CONFIG.C_DATA_DEPTH          {1024} \
    CONFIG.C_EN_STRG_QUAL        {0} \
    CONFIG.ALL_PROBE_SAME_MU     {true} \
    CONFIG.ALL_PROBE_SAME_MU_CNT {1} \
    CONFIG.C_PROBE0_WIDTH {1}  CONFIG.C_PROBE0_TYPE {0} \
    CONFIG.C_PROBE1_WIDTH {1}  CONFIG.C_PROBE1_TYPE {0} \
    CONFIG.C_PROBE2_WIDTH {8}  CONFIG.C_PROBE2_TYPE {0} \
    CONFIG.C_PROBE3_WIDTH {8}  CONFIG.C_PROBE3_TYPE {0} \
    CONFIG.C_PROBE4_WIDTH {32} CONFIG.C_PROBE4_TYPE {0} \
    CONFIG.C_PROBE5_WIDTH {16} CONFIG.C_PROBE5_TYPE {0} \
] [get_ips $ila_name]
generate_target all [get_files [get_property IP_FILE [get_ips $ila_name]]]
```

---

## Project Structure

```
ILA-Manager/
├── .github/workflows/ci.yml       # Automated test & lint matrix
├── src/ila_manager/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                    # CLI commands & argument parsing
│   ├── server.py                 # FastAPI application
│   ├── models.py                 # Core data structures (Signal, Probe, Ila, Project)
│   ├── selection.py              # Path selection & bit-slice evaluator
│   ├── diff.py                   # Signal discrepancy detector & rename suggestions
│   ├── project_io.py             # .ilaproj JSON serialization
│   ├── parser/
│   │   ├── lexer.py              # Tokenizer & comment stripper
│   │   ├── expr.py               # Safe integer expression evaluator
│   │   ├── vhdl.py               # VHDL entity, architecture, types, records
│   │   └── verilog.py            # Verilog / SystemVerilog parser
│   ├── importers/
│   │   ├── hdl_instance.py       # Scans HDL for existing ILA instances
│   │   └── tcl.py                # Parses Vivado TCL CONFIG properties
│   ├── generators/
│   │   ├── tcl.py                # Vivado TCL script generator
│   │   ├── vhdl.py               # VHDL entity work.<ila> generator
│   │   └── verilog.py            # Verilog port-map generator
│   └── web/                      # Frontend web UI (no Node build step needed)
│       ├── index.html
│       ├── styles.css
│       ├── js/                   # Vanilla ES modules
│       └── i18n/                 # en.json and th.json
├── tests/                        # Comprehensive pytest test suite
├── examples/                     # Ready-to-run HDL samples & project file
└── docs/                         # Detailed guides in English and Thai
```

---

## Testing

Run tests and style checks using `pytest` and `ruff`:
```bash
pytest -v
ruff check .
```

---

## License

This project is licensed under the [MIT License](LICENSE) — free for personal, academic, and commercial use.
