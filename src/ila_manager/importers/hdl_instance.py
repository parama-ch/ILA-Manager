"""Import existing ILA instances and port mappings from VHDL and Verilog files."""

from __future__ import annotations

import re
from typing import List, Optional

from ila_manager.models import (
    FieldStep,
    Ila,
    IndexStep,
    PathStep,
    Probe,
    ProbeMapping,
    RangeStep,
)
from ila_manager.parser.lexer import (
    strip_comments_verilog,
    strip_comments_vhdl,
)


def parse_expression_to_mapping(expr: str) -> Optional[ProbeMapping]:
    """Parse an HDL port connection expression into a ProbeMapping."""
    clean = expr.strip()
    if not clean:
        return None

    # Unwrap VHDL conversions: std_logic_vector(...)
    m_conv = re.match(r"^std_logic_vector\s*\((.*?)\)$", clean, re.IGNORECASE)
    if m_conv:
        clean = m_conv.group(1).strip()

    # Match root signal name: e.g. rx_data, s_axis.tdata, mem(2)(7 downto 0)
    m_root = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", clean)
    if not m_root:
        return None

    root_name = m_root.group(1)
    remainder = clean[len(root_name) :].strip()
    path: List[PathStep] = []

    # Parse subsequent steps: .field, (idx), (range), [idx], [range]
    i = 0
    n = len(remainder)

    while i < n:
        c = remainder[i]

        # Record field: .field_name
        if c == ".":
            m_f = re.match(r"^\.([a-zA-Z_][a-zA-Z0-9_]*)", remainder[i:])
            if m_f:
                path.append(FieldStep(field=m_f.group(1)))
                i += len(m_f.group(0))
                continue
            i += 1
            continue

        # Parenthesized group: ( ... )
        if c == "(":
            # find matching )
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if remainder[j] == "(":
                    depth += 1
                elif remainder[j] == ")":
                    depth -= 1
                j += 1
            inside = remainder[i + 1 : j - 1].strip()
            i = j

            # Check if range: 15 downto 8 or 0 to 7
            m_downto = re.search(r"(\d+)\s+downto\s+(\d+)", inside, re.IGNORECASE)
            if m_downto:
                path.append(
                    RangeStep(
                        left=int(m_downto.group(1)),
                        right=int(m_downto.group(2)),
                        ascending=False,
                    )
                )
                continue
            m_to = re.search(r"(\d+)\s+to\s+(\d+)", inside, re.IGNORECASE)
            if m_to:
                path.append(
                    RangeStep(
                        left=int(m_to.group(1)),
                        right=int(m_to.group(2)),
                        ascending=True,
                    )
                )
                continue
            # Single integer index / bit
            if inside.isdigit():
                # If we already have something or next is range, could be index or bit
                val = int(inside)
                path.append(IndexStep(index=val))
                continue
            continue

        # Bracketed group: [ ... ]
        if c == "[":
            j = remainder.find("]", i)
            if j != -1:
                inside = remainder[i + 1 : j].strip()
                i = j + 1
                # Range [15:8]
                m_br = re.search(r"(\d+)\s*:\s*(\d+)", inside)
                if m_br:
                    left_val = int(m_br.group(1))
                    right_val = int(m_br.group(2))
                    path.append(RangeStep(left=left_val, right=right_val, ascending=(left_val < right_val)))
                elif inside.isdigit():
                    path.append(IndexStep(index=int(inside)))
                continue
            i += 1
            continue

        i += 1

    return ProbeMapping(signal=root_name, path=path)


def import_from_hdl(text: str, is_vhdl: bool = True) -> List[Ila]:
    """Scan HDL text for existing ILA instantiations and extract probe mappings."""
    ilas: List[Ila] = []

    if is_vhdl:
        clean = strip_comments_vhdl(text)
        # Match VHDL instantiation:
        # <label> : entity work.<ila_name> port map ( ... );
        # or <label> : <ila_name> port map ( ... );
        vhdl_inst_pattern = re.compile(
            r"([a-zA-Z0-9_]+)\s*:\s*(?:entity\s+work\.)?([a-zA-Z0-9_]+)\s+port\s+map\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )
        for match in vhdl_inst_pattern.finditer(clean):
            label = match.group(1)
            ila_name = match.group(2)
            ports_block = match.group(3)

            # Skip if module name doesn't sound like an ILA unless label starts with u_ila or ila
            if not ("ila" in ila_name.lower() or "ila" in label.lower()):
                continue

            clk_signal = "clk"
            probes_by_idx: dict[int, Probe] = {}

            # Split port map associations
            # port => expression,
            raw_ports = [p.strip() for p in ports_block.split(",") if p.strip()]
            for p in raw_ports:
                m_assoc = re.search(r"^([^=>]+)=>\s*(.+)$", p)
                if not m_assoc:
                    continue
                lhs = m_assoc.group(1).strip()
                rhs = m_assoc.group(2).strip()

                if lhs.lower() == "clk":
                    clk_signal = rhs
                    continue

                # Match probeN or probeN(0) or portN
                m_probe = re.search(r"(?:probe|port)\s*(\d+)", lhs, re.IGNORECASE)
                if m_probe:
                    idx = int(m_probe.group(1))
                    mapping = parse_expression_to_mapping(rhs)
                    probes_by_idx[idx] = Probe(
                        index=idx,
                        mapping=mapping,
                        width=1,  # initial width, will be updated when signals are linked
                    )

            if probes_by_idx:
                max_idx = max(probes_by_idx.keys())
                probes_list = []
                for i in range(max_idx + 1):
                    if i in probes_by_idx:
                        probes_list.append(probes_by_idx[i])
                    else:
                        probes_list.append(Probe(index=i, mapping=None, width=1))

                ila = Ila(
                    name=ila_name,
                    clock=clk_signal,
                    probes=probes_list,
                )
                ilas.append(ila)

    else:
        # Verilog instantiation
        clean = strip_comments_verilog(text)
        # <ila_name> <inst_name> ( .port(expr), ... );
        v_inst_pattern = re.compile(
            r"\b([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*;",
            re.DOTALL,
        )
        for match in v_inst_pattern.finditer(clean):
            ila_name = match.group(1)
            label = match.group(2)
            ports_block = match.group(3)

            if not ("ila" in ila_name.lower() or "ila" in label.lower()):
                continue

            clk_signal = "clk"
            probes_by_idx: dict[int, Probe] = {}

            # Match .port(expr)
            port_matches = re.finditer(r"\.([a-zA-Z0-9_]+)\s*\(\s*(.*?)\s*\)", ports_block)
            for pm in port_matches:
                p_name = pm.group(1)
                p_expr = pm.group(2)

                if p_name.lower() == "clk":
                    clk_signal = p_expr
                    continue

                m_probe = re.search(r"^probe(\d+)$", p_name, re.IGNORECASE)
                if m_probe:
                    idx = int(m_probe.group(1))
                    mapping = parse_expression_to_mapping(p_expr)
                    probes_by_idx[idx] = Probe(index=idx, mapping=mapping, width=1)

            if probes_by_idx:
                max_idx = max(probes_by_idx.keys())
                probes_list = []
                for i in range(max_idx + 1):
                    if i in probes_by_idx:
                        probes_list.append(probes_by_idx[i])
                    else:
                        probes_list.append(Probe(index=i, mapping=None, width=1))

                ila = Ila(
                    name=ila_name,
                    clock=clk_signal,
                    probes=probes_list,
                )
                ilas.append(ila)

    return ilas
