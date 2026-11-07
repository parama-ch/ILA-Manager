"""VHDL parser for packages, entities, architectures, signals, types, and ports."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ila_manager.models import Signal, TypeNode
from ila_manager.parser.expr import evaluate_expression
from ila_manager.parser.lexer import split_declarations, strip_comments_vhdl


class VhdlParser:
    """Parser for VHDL source files."""

    def __init__(self, filename: str = ""):
        self.filename = filename
        self.packages: Dict[str, Dict[str, TypeNode]] = {}
        self.package_constants: Dict[str, Dict[str, int]] = {}
        self.types: Dict[str, TypeNode] = {}
        self.constants: Dict[str, int] = {}

    def parse(self, text: str) -> Dict[str, List[Signal]]:
        """Parse VHDL text and return signals grouped by unit '<entity>.<architecture>'."""
        clean_text = strip_comments_vhdl(text)

        # 1. Parse packages
        self._parse_packages(clean_text)

        # 2. Parse entities (ports & generics)
        entities = self._parse_entities(clean_text)

        # 3. Parse architectures and attach entity ports
        units: Dict[str, List[Signal]] = {}
        for (
            ent_name,
            arch_name,
            decl_block,
            start_line,
        ) in self._extract_architectures(clean_text):
            unit_key = f"{ent_name}.{arch_name}"
            unit_signals: List[Signal] = []

            # Include entity ports
            ent_info = entities.get(ent_name.lower())
            unit_constants = dict(self.constants)
            if ent_info:
                unit_constants.update(ent_info.get("generics", {}))
                unit_signals.extend(ent_info.get("ports", []))

            # Parse architecture local types and constants
            local_types, local_consts = self._parse_declarative_region(
                decl_block, unit_constants
            )
            unit_constants.update(local_consts)

            # Combined type registry
            merged_types = dict(self.types)
            merged_types.update(local_types)

            # Parse local architecture signals
            arch_signals = self._parse_signals(
                decl_block, merged_types, unit_constants, start_line
            )
            unit_signals.extend(arch_signals)

            units[unit_key] = unit_signals

        # If entities exist without architecture in this file, still provide them
        for ent_name, ent_info in entities.items():
            if not any(k.lower().startswith(f"{ent_name}.") for k in units):
                units[ent_name] = ent_info.get("ports", [])

        return units

    def _parse_packages(self, text: str) -> None:
        """Extract packages, types, and constants."""
        pkg_pattern = re.compile(
            r"\bpackage\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bend\s+(?:package\b|\1\b)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pkg_pattern.finditer(text):
            pkg_name = match.group(1).lower()
            body = match.group(2)
            types, consts = self._parse_declarative_region(body, self.constants)
            self.packages[pkg_name] = types
            self.package_constants[pkg_name] = consts
            self.types.update(types)
            self.constants.update(consts)

    def _extract_paren_block(self, text: str, keyword: str) -> Optional[str]:
        """Extract balanced parentheses block following a keyword, e.g. generic(...) or port(...)."""
        m = re.search(rf"\b{keyword}\s*\(", text, re.IGNORECASE)
        if not m:
            return None
        start = m.end() - 1
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    return text[start + 1 : i]
        return None

    def _parse_entities(self, text: str) -> Dict[str, dict]:
        """Extract entities, their generics, and ports."""
        ent_pattern = re.compile(
            r"\bentity\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bend\s+(?:entity\b|\1\b)",
            re.IGNORECASE | re.DOTALL,
        )
        entities = {}

        for match in ent_pattern.finditer(text):
            ent_name = match.group(1).lower()
            body = match.group(2)

            # Extract generics using balanced parentheses
            generics: Dict[str, int] = dict(self.constants)
            gen_block = self._extract_paren_block(body, "generic")
            if gen_block:
                gen_decls = split_declarations(gen_block)
                for g_decl in gen_decls:
                    # name : type := default;
                    m_g = re.search(
                        r"([a-zA-Z0-9_,\s]+)\s*:\s*([^:=]+)(?::=\s*([^;]+))?",
                        g_decl,
                    )
                    if m_g:
                        names = [n.strip() for n in m_g.group(1).split(",") if n.strip()]
                        def_expr = m_g.group(3)
                        val = (
                            evaluate_expression(def_expr, generics)
                            if def_expr
                            else None
                        )
                        for name in names:
                            if val is not None:
                                generics[name.lower()] = val

            # Extract ports using balanced parentheses
            ports: List[Signal] = []
            port_block = self._extract_paren_block(body, "port")
            if port_block:
                port_decls = split_declarations(port_block)
                for p_decl in port_decls:
                    # name : [in|out|inout|buffer] type
                    m_p = re.search(
                        r"([a-zA-Z0-9_,\s]+)\s*:\s*(inout|in|out|buffer)\s+(.+)",
                        p_decl,
                        re.IGNORECASE,
                    )
                    if m_p:
                        names = [n.strip() for n in m_p.group(1).split(",") if n.strip()]
                        mode = m_p.group(2).lower()
                        type_str = m_p.group(3).strip()

                        kind = "port_inout" if mode == "inout" else (f"port_{mode}" if mode in ("in", "out") else "port_out")
                        type_node = self._parse_type(type_str, self.types, generics)

                        for name in names:
                            ports.append(
                                Signal(
                                    name=name,
                                    kind=kind,
                                    type=type_node,
                                    line=1,
                                    file=self.filename,
                                )
                            )

            entities[ent_name] = {"generics": generics, "ports": ports}

        return entities

    def _extract_architectures(
        self, text: str
    ) -> List[Tuple[str, str, str, int]]:
        """Extract architectures: (entity_name, arch_name, decl_block, start_line)."""
        arch_pattern = re.compile(
            r"\barchitecture\s+([a-zA-Z0-9_]+)\s+of\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bbegin\b",
            re.IGNORECASE | re.DOTALL,
        )
        results = []
        for match in arch_pattern.finditer(text):
            arch_name = match.group(1)
            ent_name = match.group(2)
            decl_block = match.group(3)
            # Calculate line number
            start_line = text[: match.start()].count("\n") + 1
            results.append((ent_name, arch_name, decl_block, start_line))
        return results

    def _parse_declarative_region(
        self, block: str, constants: Dict[str, int]
    ) -> Tuple[Dict[str, TypeNode], Dict[str, int]]:
        """Parse constants and custom type definitions from declarative region."""
        local_types: Dict[str, TypeNode] = {}
        local_consts: Dict[str, int] = dict(constants)

        # 1. Parse constants: constant <name> : <type> := <expr>;
        const_pattern = re.compile(
            r"\bconstant\s+([a-zA-Z0-9_]+)\s*:\s*([^:=]+):=(.*?);",
            re.IGNORECASE,
        )
        for m in const_pattern.finditer(block):
            c_name = m.group(1).lower()
            c_expr = m.group(3).strip()
            val = evaluate_expression(c_expr, local_consts)
            if val is not None:
                local_consts[c_name] = val

        # 2. Parse record types: type <name> is record ... end record;
        rec_pattern = re.compile(
            r"\btype\s+([a-zA-Z0-9_]+)\s+is\s+record\b(.*?)\bend\s+record\b",
            re.IGNORECASE | re.DOTALL,
        )
        for m in rec_pattern.finditer(block):
            rec_name = m.group(1).lower()
            fields_block = m.group(2)
            fields: Dict[str, TypeNode] = {}
            for f_stmt in split_declarations(fields_block):
                m_f = re.search(r"([a-zA-Z0-9_,\s]+)\s*:\s*(.+)", f_stmt)
                if m_f:
                    f_names = [n.strip() for n in m_f.group(1).split(",") if n.strip()]
                    f_type_str = m_f.group(2).strip()
                    f_type_node = self._parse_type(f_type_str, local_types, local_consts)
                    for fn in f_names:
                        fields[fn] = f_type_node
            local_types[rec_name] = TypeNode(
                kind="record", fields=fields, base=m.group(1)
            )

        # 3. Parse array types: type <name> is array (<range>) of <elem_type>;
        arr_pattern = re.compile(
            r"\btype\s+([a-zA-Z0-9_]+)\s+is\s+array\s*\((.*?)\)\s+of\s+([a-zA-Z0-9_]+(?:\s*\(.*?\))?)\s*;",
            re.IGNORECASE,
        )
        for m in arr_pattern.finditer(block):
            arr_name = m.group(1).lower()
            range_str = m.group(2).strip()
            elem_str = m.group(3).strip()

            elem_type = self._parse_type(elem_str, local_types, local_consts)

            # Check if 2D array e.g. (0 to 3, 7 downto 0)
            dims = [d.strip() for d in range_str.split(",")]
            if len(dims) == 1:
                left, right, asc, _ = self._parse_range(dims[0], local_consts)
                local_types[arr_name] = TypeNode(
                    kind="array",
                    left=left,
                    right=right,
                    ascending=asc,
                    element=elem_type,
                    base=m.group(1),
                )
            elif len(dims) == 2:
                # Treat 2D array as array of array
                d0_l, d0_r, d0_asc, _ = self._parse_range(dims[0], local_consts)
                d1_l, d1_r, d1_asc, _ = self._parse_range(dims[1], local_consts)
                inner_node = TypeNode(
                    kind="vector",
                    left=d1_l,
                    right=d1_r,
                    ascending=d1_asc,
                    base=elem_type.base or "vector",
                )
                local_types[arr_name] = TypeNode(
                    kind="array",
                    left=d0_l,
                    right=d0_r,
                    ascending=d0_asc,
                    element=inner_node,
                    base=m.group(1),
                )

        # 4. Parse enum types: type <name> is (LIT1, LIT2, ...);
        enum_pattern = re.compile(
            r"\btype\s+([a-zA-Z0-9_]+)\s+is\s*\((.*?)\)\s*;",
            re.IGNORECASE,
        )
        for m in enum_pattern.finditer(block):
            e_name = m.group(1).lower()
            if e_name not in local_types:
                lits = [
                    lit.strip()
                    for lit in m.group(2).split(",")
                    if lit.strip() and not lit.strip().lower().startswith("downto")
                ]
                if lits and not any(" " in x for x in lits):
                    local_types[e_name] = TypeNode(
                        kind="enum", enum_literals=lits, base=m.group(1)
                    )

        return local_types, local_consts

    def _parse_signals(
        self,
        block: str,
        types: Dict[str, TypeNode],
        constants: Dict[str, int],
        base_line: int,
    ) -> List[Signal]:
        """Extract local signal declarations."""
        signals: List[Signal] = []
        sig_pattern = re.compile(
            r"\bsignal\s+([a-zA-Z0-9_,\s]+)\s*:\s*([^;:=]+)(?::=[^;]+)?;",
            re.IGNORECASE,
        )

        for match in sig_pattern.finditer(block):
            names_raw = match.group(1)
            type_raw = match.group(2).strip()
            names = [n.strip() for n in names_raw.split(",") if n.strip()]

            # Determine line number
            line_no = base_line + block[: match.start()].count("\n")

            type_node = self._parse_type(type_raw, types, constants)
            for name in names:
                signals.append(
                    Signal(
                        name=name,
                        kind="signal",
                        type=type_node,
                        line=line_no,
                        file=self.filename,
                    )
                )

        return signals

    def _parse_range(
        self, range_str: str, constants: Dict[str, int]
    ) -> Tuple[Optional[int], Optional[int], bool, Optional[str]]:
        """Parse VHDL range expression: '<left> downto <right>' or '<left> to <right>'."""
        m_downto = re.search(r"(.+?)\s+downto\s+(.+)", range_str, re.IGNORECASE)
        if m_downto:
            l_expr = m_downto.group(1).strip()
            r_expr = m_downto.group(2).strip()
            left = evaluate_expression(l_expr, constants)
            right = evaluate_expression(r_expr, constants)
            return left, right, False, range_str

        m_to = re.search(r"(.+?)\s+to\s+(.+)", range_str, re.IGNORECASE)
        if m_to:
            l_expr = m_to.group(1).strip()
            r_expr = m_to.group(2).strip()
            left = evaluate_expression(l_expr, constants)
            right = evaluate_expression(r_expr, constants)
            return left, right, True, range_str

        return None, None, False, range_str

    def _parse_type(
        self,
        type_str: str,
        types: Dict[str, TypeNode],
        constants: Dict[str, int],
    ) -> TypeNode:
        """Parse a VHDL type expression into a TypeNode."""
        clean = type_str.strip()
        clean_lower = clean.lower()

        # 1. 1-bit primitives
        if clean_lower in ("std_logic", "std_ulogic", "bit"):
            return TypeNode(kind="bit", base=clean)

        if clean_lower == "boolean":
            return TypeNode(kind="boolean", base="boolean")

        # 2. Integer with range: integer range 0 to 255
        m_int_range = re.match(
            r"(?:integer|natural|positive)\s+range\s+(.+)", clean, re.IGNORECASE
        )
        if m_int_range:
            left, right, asc, _ = self._parse_range(
                m_int_range.group(1), constants
            )
            return TypeNode(
                kind="integer", left=left, right=right, ascending=asc, base=clean
            )

        if clean_lower in ("integer", "natural", "positive"):
            return TypeNode(kind="integer", left=0, right=2147483647, base=clean)

        # 3. Vector primitives with range: std_logic_vector(N downto 0), unsigned(7 downto 0)
        m_vec = re.match(r"([a-zA-Z0-9_]+)\s*\((.*?)\)", clean, re.IGNORECASE)
        if m_vec:
            base_id = m_vec.group(1)
            range_content = m_vec.group(2).strip()
            base_lower = base_id.lower()

            if base_lower in (
                "std_logic_vector",
                "std_ulogic_vector",
                "unsigned",
                "signed",
                "bit_vector",
            ):
                left, right, asc, raw_range = self._parse_range(
                    range_content, constants
                )
                return TypeNode(
                    kind="vector",
                    left=left,
                    right=right,
                    ascending=asc,
                    base=base_id,
                    width_expr=raw_range,
                )

            # Check if this is an instantiated custom array type
            custom_t = types.get(base_lower)
            if custom_t and custom_t.kind == "array":
                left, right, asc, raw_range = self._parse_range(
                    range_content, constants
                )
                return TypeNode(
                    kind="array",
                    left=left,
                    right=right,
                    ascending=asc,
                    element=custom_t.element,
                    base=base_id,
                    width_expr=raw_range,
                )

        # 4. Lookup in custom types table
        custom_t = types.get(clean_lower)
        if custom_t:
            return custom_t

        return TypeNode(kind="unknown", base=clean)


def parse_vhdl(text: str, filename: str = "") -> Dict[str, List[Signal]]:
    """Convenience helper to parse VHDL source text."""
    parser = VhdlParser(filename=filename)
    return parser.parse(text)
