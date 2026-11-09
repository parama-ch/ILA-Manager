"""VHDL parser for packages, entities, architectures, signals, types, and ports."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple, Union

from ila_manager.models import PackageDefinition, PackageRegistry, Signal, TypeNode
from ila_manager.parser.expr import evaluate_expression
from ila_manager.parser.lexer import split_declarations, strip_comments_vhdl


class MultiFileParseResult(tuple):
    """A tuple of (units, package_names) supporting dict access for units and tuple unpacking."""

    def __new__(cls, units: Dict[str, List[Signal]], package_names: List[str]):
        return super().__new__(cls, (units, package_names))

    @property
    def units(self) -> Dict[str, List[Signal]]:
        return self[0]

    @property
    def package_names(self) -> List[str]:
        return self[1]

    @property
    def packages(self) -> List[str]:
        return self[1]

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, (int, slice)):
            return super().__getitem__(item)
        return self[0][item]

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return item in self[0]
        return super().__contains__(item)

    def get(self, key: str, default: Any = None) -> Any:
        return self[0].get(key, default)

    def items(self) -> Any:
        return self[0].items()

    def keys(self) -> Any:
        return self[0].keys()

    def values(self) -> Any:
        return self[0].values()

    def __iter__(self) -> Any:
        return super().__iter__()


@dataclass
class _RawPackage:
    name: str
    body: str
    filename: str
    line: int
    use_clauses: List[str]


def extract_use_clauses(text: str) -> List[str]:
    """Extract imported package names from VHDL 'use' clauses."""
    matches = re.findall(
        r"\buse\s+(?:work\.)?([a-zA-Z0-9_]+)\.(?:all|[a-zA-Z0-9_]+)\s*;",
        text,
        re.IGNORECASE,
    )
    result = []
    for m in matches:
        ml = m.lower()
        if ml not in ("ieee", "std") and ml not in result:
            result.append(ml)
    return result


def extract_preceding_use_clauses(text: str, pos: int) -> List[str]:
    """Extract use clauses from the context clause immediately preceding position pos.

    In VHDL (IEEE 1076), a context clause precedes a library unit (entity, architecture, package).
    Only 'library', 'use', and 'context' statements can appear in a context clause.
    Scanning backward from pos, we collect 'use' clauses until we encounter a statement
    that is not part of a context clause (such as 'end ...;' of a preceding unit)
    or reach the start of text.
    """
    prefix = text[:pos].rstrip()
    stmts = prefix.split(";")
    context_text_chunks: List[str] = []
    for stmt in reversed(stmts[:-1]):
        trimmed = stmt.strip()
        if not trimmed:
            continue
        first_word = trimmed.split()[0].lower() if trimmed.split() else ""
        if first_word in ("use", "library", "context"):
            context_text_chunks.append(trimmed + ";")
        else:
            break

    if not context_text_chunks:
        return []

    context_text = "\n".join(reversed(context_text_chunks))
    return extract_use_clauses(context_text)


class VhdlParser:
    """Parser for VHDL source files supporting single-file and multi-file two-pass parsing."""

    def __init__(self, filename: str = ""):
        self.filename = filename
        self.package_registry = PackageRegistry()
        self.packages: Dict[str, Dict[str, TypeNode]] = {}
        self.package_constants: Dict[str, Dict[str, int]] = {}
        self.types: Dict[str, TypeNode] = {}
        self.constants: Dict[str, int] = {}

    def parse(self, text: str) -> Dict[str, List[Signal]]:
        """Parse single VHDL text and return signals grouped by unit '<entity>.<architecture>'."""
        res = self.parse_multi([(self.filename or "<string>", text)])
        return res.units

    def parse_multi(
        self, sources: List[Tuple[str, str]]
    ) -> MultiFileParseResult:
        """Two-pass parsing of multi-file VHDL sources.

        Pass 1: Parse all package declarations into self.package_registry with fixpoint resolution.
        Pass 2: Parse all entities and architectures across all files using the registry.
        """
        clean_sources: List[Tuple[str, str]] = [
            (fname, strip_comments_vhdl(text)) for fname, text in sources
        ]

        # ------------------------------------------------------------------
        # PASS 1: Extract packages across all sources
        # ------------------------------------------------------------------
        raw_packages: List[_RawPackage] = []
        pkg_pattern = re.compile(
            r"\bpackage\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bend\s+(?:package\b|\1\b)",
            re.IGNORECASE | re.DOTALL,
        )

        for fname, clean_text in clean_sources:
            for match in pkg_pattern.finditer(clean_text):
                pkg_name = match.group(1).lower()
                body = match.group(2)
                line = clean_text[: match.start()].count("\n") + 1
                use_clauses = extract_preceding_use_clauses(
                    clean_text, match.start()
                )
                raw_packages.append(
                    _RawPackage(
                        name=pkg_name,
                        body=body,
                        filename=fname,
                        line=line,
                        use_clauses=use_clauses,
                    )
                )

        # Initialize package definitions in registry
        for raw in raw_packages:
            if not self.package_registry.get_package(raw.name):
                self.package_registry.add_package(
                    PackageDefinition(
                        name=raw.name,
                        file=raw.filename,
                        line=raw.line,
                        use_clauses=raw.use_clauses,
                    )
                )

        # Fixpoint iteration loop for cross-package dependencies
        max_passes = len(raw_packages) + 3
        for _ in range(max_passes):
            changed = False
            for raw in raw_packages:
                current_pkg = self.package_registry.packages[raw.name]

                # Assemble active constants and types for this package
                active_consts: Dict[str, int] = dict(self.constants)
                active_consts.update(self.package_registry.all_constants())
                active_types: Dict[str, TypeNode] = dict(self.types)
                active_types.update(self.package_registry.all_types())

                # Imported packages take priority
                for u in raw.use_clauses:
                    imp_pkg = self.package_registry.get_package(u)
                    if imp_pkg:
                        active_consts.update(imp_pkg.constants)
                        active_types.update(imp_pkg.types)

                # Local constants and types take highest priority
                active_consts.update(current_pkg.constants)
                active_types.update(current_pkg.types)

                new_types, new_consts = self._parse_declarative_region(
                    raw.body,
                    active_consts,
                    active_types,
                    package_registry=self.package_registry,
                    current_package=raw.name,
                    imported_packages=raw.use_clauses,
                )

                if new_consts != current_pkg.constants:
                    current_pkg.constants.update(new_consts)
                    changed = True

                if new_types != current_pkg.types:
                    current_pkg.types.update(new_types)
                    changed = True

            if not changed:
                break

        # Sync legacy parser dictionaries
        for pkg_name, pkg in self.package_registry.packages.items():
            self.packages[pkg_name] = pkg.types
            self.package_constants[pkg_name] = pkg.constants
        self.constants.update(self.package_registry.all_constants())

        # ------------------------------------------------------------------
        # PASS 2: Parse entities and architectures across all sources
        # ------------------------------------------------------------------
        # Pass 2A: Collect all entities across all files
        all_entities: Dict[str, dict] = {}
        for fname, clean_text in clean_sources:
            file_entities = self._parse_entities(
                clean_text,
                filename=fname,
                package_registry=self.package_registry,
            )
            all_entities.update(file_entities)

        # Pass 2B: Collect architectures across all files and attach entity ports
        units: Dict[str, List[Signal]] = {}
        for fname, clean_text in clean_sources:
            for (
                ent_name,
                arch_name,
                decl_block,
                start_line,
                preceding_uses,
            ) in self._extract_architectures(clean_text):
                unit_key = f"{ent_name}.{arch_name}"
                unit_signals: List[Signal] = []

                # Combine entity context clauses, architecture preceding context clauses,
                # and architecture-level declarative use clauses
                ent_info = all_entities.get(ent_name.lower())
                ent_uses = ent_info.get("use_clauses", []) if ent_info else []
                arch_uses = list(
                    dict.fromkeys(
                        ent_uses
                        + preceding_uses
                        + extract_use_clauses(decl_block)
                    )
                )

                # Entity ports and generics
                unit_constants: Dict[str, int] = dict(self.constants)
                unit_constants.update(self.package_registry.all_constants())
                for u in arch_uses:
                    pkg = self.package_registry.get_package(u)
                    if pkg:
                        unit_constants.update(pkg.constants)

                if ent_info:
                    unit_constants.update(ent_info.get("generics", {}))
                    unit_signals.extend(ent_info.get("ports", []))

                # Architecture local types and constants: populate only from imported packages
                visible_types: Dict[str, TypeNode] = dict(self.types)
                for u in arch_uses:
                    pkg = self.package_registry.get_package(u)
                    if pkg:
                        visible_types.update(pkg.types)

                # Fixpoint loop for architecture declarative region (up to 3 passes)
                local_types = dict(visible_types)
                local_consts = dict(unit_constants)
                for _ in range(3):
                    new_types, new_consts = self._parse_declarative_region(
                        decl_block,
                        local_consts,
                        local_types,
                        package_registry=self.package_registry,
                        imported_packages=arch_uses,
                    )
                    if new_types == local_types and new_consts == local_consts:
                        break
                    local_types = new_types
                    local_consts = new_consts

                unit_constants.update(local_consts)
                merged_types = local_types

                # Parse architecture signals
                arch_signals = self._parse_signals(
                    decl_block,
                    merged_types,
                    unit_constants,
                    start_line,
                    filename=fname,
                    package_registry=self.package_registry,
                    imported_packages=arch_uses,
                )
                unit_signals.extend(arch_signals)

                units[unit_key] = unit_signals

        # Pass 2C: Entities without architectures
        for ent_name, ent_info in all_entities.items():
            if not any(k.lower().startswith(f"{ent_name}.") for k in units):
                units[ent_name] = ent_info.get("ports", [])

        pkg_names = list(self.package_registry.packages.keys())
        return MultiFileParseResult(units, pkg_names)

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

    def _parse_entities(
        self,
        text: str,
        filename: str = "",
        package_registry: Optional[PackageRegistry] = None,
        imported_packages: Optional[List[str]] = None,
    ) -> Dict[str, dict]:
        """Extract entities, their generics, and ports."""
        ent_pattern = re.compile(
            r"\bentity\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bend\s+(?:entity\b|\1\b)",
            re.IGNORECASE | re.DOTALL,
        )
        entities = {}
        reg = package_registry or self.package_registry

        for match in ent_pattern.finditer(text):
            ent_name = match.group(1).lower()
            body = match.group(2)

            preceding_uses = extract_preceding_use_clauses(text, match.start())
            local_uses = list(
                dict.fromkeys(
                    (imported_packages or [])
                    + preceding_uses
                    + extract_use_clauses(body)
                )
            )

            generics: Dict[str, int] = dict(self.constants)
            if reg:
                generics.update(reg.all_constants())
                for u in local_uses:
                    pkg = reg.get_package(u)
                    if pkg:
                        generics.update(pkg.constants)

            gen_block = self._extract_paren_block(body, "generic")
            if gen_block:
                gen_decls = split_declarations(gen_block)
                for g_decl in gen_decls:
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

            visible_types: Dict[str, TypeNode] = dict(self.types)
            if reg:
                for u in local_uses:
                    pkg = reg.get_package(u)
                    if pkg:
                        visible_types.update(pkg.types)

            ports: List[Signal] = []
            port_block = self._extract_paren_block(body, "port")
            if port_block:
                port_decls = split_declarations(port_block)
                for p_decl in port_decls:
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
                        type_node = self._parse_type(
                            type_str,
                            visible_types,
                            generics,
                            package_registry=reg,
                            imported_packages=local_uses,
                        )

                        for name in names:
                            ports.append(
                                Signal(
                                    name=name,
                                    kind=kind,
                                    type=type_node,
                                    line=1,
                                    file=filename or self.filename,
                                )
                            )

            entities[ent_name] = {
                "generics": generics,
                "ports": ports,
                "use_clauses": local_uses,
            }

        return entities

    def _extract_architectures(
        self, text: str
    ) -> List[Tuple[str, str, str, int, List[str]]]:
        """Extract architectures: (entity_name, arch_name, decl_block, start_line, preceding_uses)."""
        arch_pattern = re.compile(
            r"\barchitecture\s+([a-zA-Z0-9_]+)\s+of\s+([a-zA-Z0-9_]+)\s+is\b(.*?)\bbegin\b",
            re.IGNORECASE | re.DOTALL,
        )
        results = []
        for match in arch_pattern.finditer(text):
            arch_name = match.group(1)
            ent_name = match.group(2)
            decl_block = match.group(3)
            start_line = text[: match.start()].count("\n") + 1
            preceding_uses = extract_preceding_use_clauses(text, match.start())
            results.append(
                (ent_name, arch_name, decl_block, start_line, preceding_uses)
            )
        return results

    def _parse_declarative_region(
        self,
        block: str,
        constants: Dict[str, int],
        types: Optional[Dict[str, TypeNode]] = None,
        package_registry: Optional[PackageRegistry] = None,
        current_package: Optional[str] = None,
        imported_packages: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, TypeNode], Dict[str, int]]:
        """Parse constants, subtypes, and custom type definitions from a declarative region."""
        local_types: Dict[str, TypeNode] = dict(types or {})
        local_consts: Dict[str, int] = dict(constants)
        reg = package_registry or self.package_registry

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

        # 2. Parse subtypes: subtype <name> is <type_expr>;
        subtype_pattern = re.compile(
            r"\bsubtype\s+([a-zA-Z0-9_]+)\s+is\s+([^;]+);",
            re.IGNORECASE,
        )
        for m in subtype_pattern.finditer(block):
            sub_name = m.group(1).lower()
            sub_expr = m.group(2).strip()
            sub_node = self._parse_type(
                sub_expr,
                local_types,
                local_consts,
                package_registry=reg,
                imported_packages=imported_packages,
            )
            if current_package and not sub_node.package:
                sub_node = replace(sub_node, package=current_package)
            local_types[sub_name] = sub_node

        # 3. Parse record types: type <name> is record ... end record;
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
                    f_type_node = self._parse_type(
                        f_type_str,
                        local_types,
                        local_consts,
                        package_registry=reg,
                        imported_packages=imported_packages,
                    )
                    for fn in f_names:
                        fields[fn] = f_type_node
            local_types[rec_name] = TypeNode(
                kind="record",
                fields=fields,
                base=m.group(1),
                package=current_package,
            )

        # 4. Parse array types: type <name> is array (<range>) of <elem_type>;
        arr_pattern = re.compile(
            r"\btype\s+([a-zA-Z0-9_]+)\s+is\s+array\s*\((.*?)\)\s+of\s+([^;]+);",
            re.IGNORECASE,
        )
        for m in arr_pattern.finditer(block):
            arr_name = m.group(1).lower()
            range_str = m.group(2).strip()
            elem_str = m.group(3).strip()

            elem_type = self._parse_type(
                elem_str,
                local_types,
                local_consts,
                package_registry=reg,
                imported_packages=imported_packages,
            )

            # Check if unconstrained array
            if "<>" in range_str:
                local_types[arr_name] = TypeNode(
                    kind="array",
                    left=None,
                    right=None,
                    ascending=False,
                    element=elem_type,
                    base=m.group(1),
                    is_unconstrained=True,
                    package=current_package,
                )
                continue

            dims = [d.strip() for d in range_str.split(",")]
            if len(dims) == 1:
                left, right, asc, raw_range = self._parse_range(dims[0], local_consts)
                local_types[arr_name] = TypeNode(
                    kind="array",
                    left=left,
                    right=right,
                    ascending=asc,
                    element=elem_type,
                    base=m.group(1),
                    width_expr=raw_range,
                    package=current_package,
                )
            elif len(dims) == 2:
                # 2D array: Dim 0 (outer), Dim 1 (inner)
                d0_l, d0_r, d0_asc, d0_raw = self._parse_range(dims[0], local_consts)
                d1_l, d1_r, d1_asc, d1_raw = self._parse_range(dims[1], local_consts)

                if elem_type.kind == "bit":
                    inner_node = TypeNode(
                        kind="vector",
                        left=d1_l,
                        right=d1_r,
                        ascending=d1_asc,
                        base="vector",
                        width_expr=d1_raw,
                        package=current_package,
                    )
                else:
                    inner_node = TypeNode(
                        kind="array",
                        left=d1_l,
                        right=d1_r,
                        ascending=d1_asc,
                        element=elem_type,
                        base=f"{m.group(1)}_dim1",
                        width_expr=d1_raw,
                        package=current_package,
                    )

                local_types[arr_name] = TypeNode(
                    kind="array",
                    left=d0_l,
                    right=d0_r,
                    ascending=d0_asc,
                    element=inner_node,
                    base=m.group(1),
                    width_expr=d0_raw,
                    package=current_package,
                )

        # 5. Parse enum types: type <name> is (LIT1, LIT2, ...);
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
                        kind="enum",
                        enum_literals=lits,
                        base=m.group(1),
                        package=current_package,
                    )

        return local_types, local_consts

    def _parse_signals(
        self,
        block: str,
        types: Dict[str, TypeNode],
        constants: Dict[str, int],
        base_line: int,
        filename: str = "",
        package_registry: Optional[PackageRegistry] = None,
        imported_packages: Optional[List[str]] = None,
    ) -> List[Signal]:
        """Extract local signal declarations."""
        signals: List[Signal] = []
        sig_pattern = re.compile(
            r"\bsignal\s+([a-zA-Z0-9_,\s]+)\s*:\s*([^;:=]+)(?::=[^;]+)?;",
            re.IGNORECASE,
        )
        reg = package_registry or self.package_registry

        for match in sig_pattern.finditer(block):
            names_raw = match.group(1)
            type_raw = match.group(2).strip()
            names = [n.strip() for n in names_raw.split(",") if n.strip()]

            line_no = base_line + block[: match.start()].count("\n")

            type_node = self._parse_type(
                type_raw,
                types,
                constants,
                package_registry=reg,
                imported_packages=imported_packages,
            )
            for name in names:
                signals.append(
                    Signal(
                        name=name,
                        kind="signal",
                        type=type_node,
                        line=line_no,
                        file=filename or self.filename,
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
        package_registry: Optional[PackageRegistry] = None,
        imported_packages: Optional[List[str]] = None,
    ) -> TypeNode:
        """Parse a VHDL type expression into a TypeNode."""
        clean = type_str.strip()
        clean_lower = clean.lower()
        reg = package_registry or self.package_registry

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
        m_vec = re.match(r"^([a-zA-Z0-9_\.]+)\s*\((.*)\)$", clean, re.IGNORECASE)
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

            # Check if this is an instantiated custom array type (from types dict or package_registry)
            custom_t = types.get(base_lower)
            if not custom_t and reg:
                custom_t = reg.resolve_type(base_id, imported_packages)

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
                    package=custom_t.package,
                    is_unconstrained=False,
                )

        # 4. Lookup in local types dictionary
        custom_t = types.get(clean_lower)
        if custom_t:
            return custom_t

        # 5. Lookup in PackageRegistry (qualified, imported, or global fallback)
        if reg:
            pkg_type = reg.resolve_type(clean, imported_packages)
            if pkg_type:
                return pkg_type

        return TypeNode(kind="unknown", base=clean)


def parse_vhdl(text: str, filename: str = "<string>") -> Dict[str, List[Signal]]:
    """Convenience helper to parse a single VHDL source text."""
    parser = VhdlParser(filename=filename)
    return parser.parse(text)


def parse_vhdl_multi(
    sources: Union[List[Tuple[str, str]], Dict[str, str]],
) -> MultiFileParseResult:
    """Parse multiple VHDL source files in two passes, returning (units, package_names)."""
    if isinstance(sources, dict):
        sources = list(sources.items())
    parser = VhdlParser()
    return parser.parse_multi(sources)
