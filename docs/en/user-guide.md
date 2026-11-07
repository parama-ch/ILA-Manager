# ILA Manager User Guide

Welcome to the comprehensive user guide for **ILA Manager**. This document explains all features, keyboard shortcuts, Vivado integration steps, and troubleshooting.

---

## Table of Contents
1. [Introduction](#introduction)
2. [Installation & Setup](#installation--setup)
3. [User Interface Overview](#user-interface-overview)
4. [Working with HDL Sources](#working-with-hdl-sources)
5. [Managing ILA Probes](#managing-ila-probes)
   - [Adding Probes](#adding-probes)
   - [Reordering Probes](#reordering-probes)
   - [Swapping Probes](#swapping-probes)
   - [Bit Slicing & Array Indexing](#bit-slicing--array-indexing)
6. [ILA Core Configuration](#ila-core-configuration)
   - [Flip-Flop Pipeline Stages](#flip-flop-pipeline-stages)
   - [Sample Depth & Trigger Comparators](#sample-depth--trigger-comparators)
7. [Vivado Integration](#vivado-integration)
8. [Project Save, Load & Diff Review](#project-save-load--diff-review)
9. [Headless CLI Operations](#headless-cli-operations)

---

## 1. Introduction
Vivado's Integrated Logic Analyzer (ILA) core is the industry-standard debug core for Xilinx/AMD FPGAs. However, managing dozens of probe indices manually is tedious and error-prone. **ILA Manager** provides a visual drag-and-drop workflow that bridges your HDL files and Vivado TCL automation.

---

## 2. Installation & Setup
Install `ila-manager` via pip:
```bash
pip install git+https://github.com/parama-ch/ILA-Manager.git
```
Then start the tool with:
```bash
ila-manager
```
This automatically boots a local lightweight server and opens `http://127.0.0.1:8765` in your browser.

---

## 3. User Interface Overview
The UI consists of three responsive panels:
1. **Left Panel (HDL Sources & Signals)**: Drop zone for source files, module unit selector, and searchable/filterable list of extracted ports and internal signals.
2. **Center Panel (ILA Port Manager)**: Global options toolbar and an interactive table displaying probes, mapping expressions, bit widths, probe types, and action buttons.
3. **Right Panel (Live Generated Code)**: Live code viewer for Vivado TCL, VHDL port map, and Verilog port map with 1-click copy and download buttons.

---

## 4. Working with HDL Sources
- Drag one or more `.vhd`, `.vhdl`, `.v`, or `.sv` files onto the drop zone in the left panel.
- Use the **Target Module / Unit** dropdown to select the target entity/architecture where the ILA will be instantiated.
- Filter signals using the **All**, **Ports**, or **Signals** tabs, or type in the search box to find specific nets quickly.

---

## 5. Managing ILA Probes
### Adding Probes
- Click the `+` button on any signal in the left panel to append it to the probe list.
- Or drag a signal from the left list and drop it into the center table.

### Reordering Probes
- Click and drag the `⋮⋮` handle on any probe row to drag it up or down.
- Or use the `↑` and `↓` arrow buttons to move a probe one position at a time.

### Swapping Probes
- **Method 1**: Click the `⇄ Swap Probes` button in the header toolbar, select `probeA` and `probeB`, and click **Swap**.
- **Method 2**: Click the `⇄` button on any probe row to quickly swap with another probe.
- **Method 3**: Hold down the `Alt` key while dragging one probe row onto another.

### Bit Slicing & Array Indexing
- For vectors, arrays, or records, click the `✂` icon in the signal list or click the mapping expression in the probe table.
- A dialog opens where you can:
  - Select array indices (e.g. `2` for `mem(2)`).
  - Select record fields (e.g. `tdata`).
  - Enter custom bit ranges (e.g. `15 downto 8` or `[7:0]`).

---

## 6. ILA Core Configuration
### Flip-Flop Pipeline Stages
In Vivado IP customization, `C_INPUT_PIPE_STAGES` defaults to 1. In high-speed FPGA designs, routing signals across the chip directly into the ILA causes severe setup timing violations.
**ILA Manager sets the default to 4 pipeline stages**, inserting flip-flop retiming registers to guarantee clean timing closure.

### Sample Depth & Trigger Comparators
- **Sample Depth**: Choose from 1024 up to 65536 samples.
- **Trigger Match Units**:
  - *Same count for all*: Sets `ALL_PROBE_SAME_MU = true` with a uniform comparator count.
  - *Individual per probe*: Enables custom match units (1 to 16) per individual probe.

---

## 7. Vivado Integration
1. In the right panel, select the **Vivado TCL** tab and click **Copy**.
2. In Vivado's Tcl Console, paste or run:
   ```tcl
   source ila_0.tcl
   ```
3. Copy the **VHDL Port Map** or **Verilog Port Map** snippet into your top-level or target architecture.
   - For VHDL, notice that single-bit signals use the strict vector syntax:
     ```vhdl
     probe0(0) => my_one_bit_signal,
     ```
   - Notice that direct entity instantiation is used:
     ```vhdl
     u_ila_0 : entity work.ila_0
     ```

---

## 8. Project Save, Load & Diff Review
- Click **Save Project** in the top navigation bar to save your configuration as a `.ilaproj` file.
- When you reopen the project after modifying your HDL files (e.g. changing an 8-bit signal to 16-bit, or renaming a signal), ILA Manager automatically opens the **Diff Review Dialog**:
  - **Update to new width**: Automatically syncs the probe width to match the updated HDL.
  - **Remap to suggestion**: Automatically re-links probes when signals were renamed.
  - **Delete probe**: Cleans up probes whose signals were removed.

---

## 9. Headless CLI Operations
Generate scripts directly from Makefiles or CI:
```bash
ila-manager generate my_project.ilaproj --ila ila_0 --out ./build
```
Extract signals from any HDL file to JSON:
```bash
ila-manager parse src/sample_fifo.v
```
