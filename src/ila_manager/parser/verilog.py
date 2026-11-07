"""Verilog and SystemVerilog parser for modules, ports, nets, parameters, and arrays."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ila_manager.models import Signal, TypeNode
from ila_manager.parser.expr import evaluate_expression
from ila_manager.parser.lexer import split_declarations, strip_comments_verilog


class VerilogParser:
    """Parser for Verilog and SystemVerilog source files."""

    def __init__(self, filename: str = ""):
        self.filename = filename

    def parse(self, text: str) -> Dict[str, List[Signal]]:
        """Parse Verilog text and return signals grouped by module name."""
        clean_text = strip_comments_verilog(text)
        modules: Dict[str, List[Signal]] = {}

        # Match modules: module <name> ... endmodule
        mod_pattern = re.compile(
            r"\bmodule\s+([a-zA-Z0-9_]+)\s*(?:#\s*\((.*?)\)\s*)?(?:\((.*?)\)\s*)?;(.*?)\bendmodule\b",
            re.DOTALL,
        )

        for match in mod_pattern.finditer(clean_text):
            mod_name = match.group(1)
            param_block = match.group(2) or ""
            port_block = match.group(3) or ""
            body_block = match.group(4) or ""

            # Calculate starting line
            line_offset = clean_text[: match.start()].count("\n") + 1

            signals: List[Signal] = []
            parameters: Dict[str, int] = {}

            # 1. Parse module parameters #(parameter WIDTH = 8, ...)
            if param_block:
                self._parse_parameters(param_block, parameters)

            # 2. Parse body parameters (parameter / localparam)
            self._parse_parameters(body_block, parameters)

            # 3. Parse ANSI ports in ( ... )
            if port_block:
                ansi_ports = self._parse_ansi_ports(port_block, parameters, line_offset)
                signals.extend(ansi_ports)

            # 4. Parse internal declarations and non-ANSI ports in body
            body_signals = self._parse_body_declarations(
                body_block, parameters, line_offset
            )

            # Merge: if a signal was declared as a non-ANSI port name in port_block
            # and re-declared with type in body_block, keep the body's typed definition
            existing_names = {s.name for s in signals}
            for bs in body_signals:
                if bs.name in existing_names:
                    # Update the existing port with complete type info if needed
                    for i, s in enumerate(signals):
                        if s.name == bs.name:
                            signals[i] = bs
                            break
                else:
                    signals.append(bs)

            modules[mod_name] = signals

        return modules

    def _parse_parameters(self, text: str, params: Dict[str, int]) -> None:
        """Extract parameter and localparam defaults into params dict."""
        param_pattern = re.compile(
            r"\b(?:parameter|localparam)\s*(?:\[.*?\])?\s*([a-zA-Z0-9_]+)\s*=\s*([^,;)]+)",
        )
        for m in param_pattern.finditer(text):
            p_name = m.group(1)
            p_expr = m.group(2).strip()
            val = evaluate_expression(p_expr, params)
            if val is not None:
                params[p_name] = val

    def _parse_range(
        self, range_str: str, params: Dict[str, int]
    ) -> Tuple[Optional[int], Optional[int], bool, Optional[str]]:
        """Parse Verilog packed range: '[left:right]'."""
        m = re.search(r"\[\s*([^:]+)\s*:\s*([^\]]+)\s*\]", range_str)
        if m:
            l_expr = m.group(1).strip()
            r_expr = m.group(2).strip()
            left = evaluate_expression(l_expr, params)
            right = evaluate_expression(r_expr, params)
            asc = (left is not None and right is not None and left < right)
            return left, right, asc, range_str
        return None, None, False, range_str

    def _parse_ansi_ports(
        self, port_block: str, params: Dict[str, int], base_line: int
    ) -> List[Signal]:
        """Parse ANSI style ports in module header."""
        ports: List[Signal] = []
        # Split by comma but respect parentheses and brackets
        raw_decls = []
        curr = []
        depth = 0
        for char in port_block:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            if char == "," and depth == 0:
                raw_decls.append("".join(curr).strip())
                curr = []
            else:
                curr.append(char)
        if curr:
            raw_decls.append("".join(curr).strip())

        for decl in raw_decls:
            if not decl:
                continue

            # Match direction
            m_dir = re.match(
                r"^\s*(input|output|inout)\s*(reg|wire|logic)?\s*(\[.*?\])?\s*([a-zA-Z0-9_]+)\s*(\[.*?\])?$",
                decl,
            )
            if m_dir:
                direction = m_dir.group(1)
                net_type = m_dir.group(2) or "wire"
                range_str = m_dir.group(3) or ""
                name = m_dir.group(4)
                unpacked_str = m_dir.group(5) or ""

                kind = "port_inout" if direction == "inout" else f"port_{direction}"
                type_node = self._make_type(net_type, range_str, unpacked_str, params)

                ports.append(
                    Signal(
                        name=name,
                        kind=kind,
                        type=type_node,
                        line=base_line,
                        file=self.filename,
                    )
                )

        return ports

    def _parse_body_declarations(
        self, body: str, params: Dict[str, int], base_line: int
    ) -> List[Signal]:
        """Parse signals, wires, regs, logic, and non-ANSI ports in module body."""
        signals: List[Signal] = []
        statements = split_declarations(body)

        for stmt in statements:
            # Check for net or port declaration
            # input / output / inout / wire / reg / logic / bit
            m = re.match(
                r"^\s*(input|output|inout|wire|reg|logic|bit)\s*(?:signed|unsigned)?\s*(\[.*?\])?\s*(.+)$",
                stmt,
            )
            if not m:
                continue

            decl_kw = m.group(1)
            range_str = m.group(2) or ""
            rest = m.group(3).strip()

            kind = "signal"
            if decl_kw in ("input", "output", "inout"):
                kind = "port_inout" if decl_kw == "inout" else f"port_{decl_kw}"
                base_type = "wire"
            else:
                base_type = decl_kw

            # Split comma-separated items: a, b = 0, c[0:7]
            items = [item.strip() for item in rest.split(",") if item.strip()]
            for item in items:
                # Strip initial assignment if present: foo = 8'h0
                m_init = re.match(r"^([a-zA-Z0-9_]+)\s*(\[.*?\])?(?:\s*=.*)?$", item)
                if m_init:
                    name = m_init.group(1)
                    unpacked_str = m_init.group(2) or ""
                    type_node = self._make_type(
                        base_type, range_str, unpacked_str, params
                    )
                    signals.append(
                        Signal(
                            name=name,
                            kind=kind,
                            type=type_node,
                            line=base_line,
                            file=self.filename,
                        )
                    )

        return signals

    def _make_type(
        self,
        base_type: str,
        range_str: str,
        unpacked_str: str,
        params: Dict[str, int],
    ) -> TypeNode:
        """Construct a TypeNode from Verilog type specifications."""
        left, right, asc, width_expr = (None, None, False, None)

        if range_str:
            left, right, asc, width_expr = self._parse_range(range_str, params)

        # Base node (vector or 1-bit)
        if range_str and left is not None and right is not None:
            base_node = TypeNode(
                kind="vector",
                left=left,
                right=right,
                ascending=asc,
                base=base_type,
                width_expr=width_expr,
            )
        elif range_str:
            base_node = TypeNode(
                kind="vector",
                base=base_type,
                width_expr=width_expr or range_str,
            )
        else:
            base_node = TypeNode(kind="bit", base=base_type)

        # If unpacked array present: e.g. [0:15] or [16]
        if unpacked_str:
            # Check if range [0:15] or single size [16]
            m_arr_range = re.search(r"\[\s*([^:]+)\s*:\s*([^\]]+)\s*\]", unpacked_str)
            if m_arr_range:
                arr_l = evaluate_expression(m_arr_range.group(1).strip(), params)
                arr_r = evaluate_expression(m_arr_range.group(2).strip(), params)
                arr_asc = (
                    arr_l is not None and arr_r is not None and arr_l < arr_r
                )
                return TypeNode(
                    kind="array",
                    left=arr_l,
                    right=arr_r,
                    ascending=arr_asc,
                    element=base_node,
                    base=f"{base_type} array",
                    width_expr=unpacked_str,
                )
            m_arr_size = re.search(r"\[\s*([^\]]+)\s*\]", unpacked_str)
            if m_arr_size:
                size_val = evaluate_expression(m_arr_size.group(1).strip(), params)
                if size_val is not None:
                    return TypeNode(
                        kind="array",
                        left=0,
                        right=size_val - 1,
                        ascending=True,
                        element=base_node,
                        base=f"{base_type} array",
                        width_expr=unpacked_str,
                    )

        return base_node


def parse_verilog(text: str, filename: str = "") -> Dict[str, List[Signal]]:
    """Convenience helper to parse Verilog/SystemVerilog source text."""
    parser = VerilogParser(filename=filename)
    return parser.parse(text)
