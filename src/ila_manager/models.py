"""Core data models for ILA Manager."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

KindType = Literal[
    "bit", "vector", "array", "record", "integer", "boolean", "enum", "unknown"
]
SignalKind = Literal["port_in", "port_out", "port_inout", "signal"]
ProbeType = Literal["DATA_AND_TRIGGER", "DATA", "TRIGGER"]


@dataclass
class TypeNode:
    """Recursive type description for HDL signals and ports."""

    kind: KindType
    left: Optional[int] = None
    right: Optional[int] = None
    ascending: bool = False  # True for VHDL 'to' or Verilog [0:N]; False for 'downto'
    element: Optional[TypeNode] = None  # Array element type
    fields: Dict[str, TypeNode] = field(default_factory=dict)  # Record fields
    base: str = ""  # Raw base name: std_logic_vector, unsigned, signed, logic, etc.
    width_expr: Optional[str] = None  # Text of unresolved expression if any
    enum_literals: List[str] = field(default_factory=list)
    package: Optional[str] = None
    is_unconstrained: bool = False

    def computed_width(self) -> Optional[int]:
        """Compute the bit width of this type if bounds are known."""
        if self.kind == "bit":
            return 1
        if self.kind == "vector":
            if self.left is not None and self.right is not None:
                return abs(self.left - self.right) + 1
            return None
        if self.kind == "array":
            if self.left is not None and self.right is not None and self.element is not None:
                elem_w = self.element.computed_width()
                if elem_w is not None:
                    count = abs(self.left - self.right) + 1
                    return count * elem_w
            return None
        if self.kind == "record":
            total = 0
            for f in self.fields.values():
                w = f.computed_width()
                if w is None:
                    return None
                total += w
            return total if self.fields else None
        if self.kind == "integer":
            if self.left is not None and self.right is not None:
                max_val = max(abs(self.left), abs(self.right))
                if max_val == 0:
                    return 1
                return max_val.bit_length()
            return 32  # standard default integer width
        if self.kind == "boolean":
            return 1
        if self.kind == "enum":
            n = len(self.enum_literals)
            if n <= 1:
                return 1
            return math.ceil(math.log2(n))
        return None

    def summary(self) -> str:
        """Return a compact human-readable representation."""
        if self.kind == "bit":
            return self.base or "bit"
        if self.kind == "vector":
            dir_str = "to" if self.ascending else "downto"
            if self.left is not None and self.right is not None:
                return f"{self.base or 'vector'}({self.left} {dir_str} {self.right})"
            if self.width_expr:
                return f"{self.base or 'vector'}({self.width_expr})"
            return self.base or "vector"
        if self.kind == "array":
            dir_str = "to" if self.ascending else "downto"
            elem_summary = self.element.summary() if self.element else "element"
            if self.left is not None and self.right is not None:
                return f"array ({self.left} {dir_str} {self.right}) of {elem_summary}"
            return f"array of {elem_summary}"
        if self.kind == "record":
            fields_str = ", ".join(f"{k}: {v.summary()}" for k, v in list(self.fields.items())[:3])
            if len(self.fields) > 3:
                fields_str += ", ..."
            return f"record ({fields_str})"
        if self.kind == "integer":
            if self.left is not None and self.right is not None:
                return f"integer range {self.left} to {self.right}"
            return "integer"
        if self.kind == "boolean":
            return "boolean"
        if self.kind == "enum":
            return f"enum ({', '.join(self.enum_literals[:4])}{'...' if len(self.enum_literals) > 4 else ''})"
        return self.base or "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "left": self.left,
            "right": self.right,
            "ascending": self.ascending,
            "element": self.element.to_dict() if self.element else None,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "base": self.base,
            "width_expr": self.width_expr,
            "enum_literals": list(self.enum_literals),
            "package": self.package,
            "is_unconstrained": self.is_unconstrained,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional[TypeNode]:
        if not data:
            return None
        elem = cls.from_dict(data.get("element")) if data.get("element") else None
        fields_map = {}
        for k, v in data.get("fields", {}).items():
            fields_map[k] = cls.from_dict(v)
        return cls(
            kind=data["kind"],
            left=data.get("left"),
            right=data.get("right"),
            ascending=data.get("ascending", False),
            element=elem,
            fields=fields_map,
            base=data.get("base", ""),
            width_expr=data.get("width_expr"),
            enum_literals=data.get("enum_literals", []),
            package=data.get("package"),
            is_unconstrained=bool(data.get("is_unconstrained", False)),
        )


@dataclass
class PackageDefinition:
    """Definition of an HDL package extracted in Pass 1."""

    name: str  # Lowercase normalized package name
    file: str = ""  # Source file path
    line: int = 1  # Line number of declaration
    constants: Dict[str, int] = field(default_factory=dict)  # Name -> integer value
    types: Dict[str, TypeNode] = field(default_factory=dict)  # Name -> TypeNode
    use_clauses: List[str] = field(default_factory=list)  # ['work.common_pkg.all', ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "constants": dict(self.constants),
            "types": {k: v.to_dict() for k, v in self.types.items()},
            "use_clauses": list(self.use_clauses),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PackageDefinition:
        types_map: Dict[str, TypeNode] = {}
        for k, v in data.get("types", {}).items():
            node = TypeNode.from_dict(v)
            if node is not None:
                types_map[k] = node
        return cls(
            name=data["name"],
            file=data.get("file", ""),
            line=data.get("line", 1),
            constants=dict(data.get("constants", {})),
            types=types_map,
            use_clauses=list(data.get("use_clauses", [])),
        )


@dataclass
class PackageRegistry:
    """Aggregated registry of all packages, types, and constants across the project."""

    packages: Dict[str, PackageDefinition] = field(default_factory=dict)

    def add_package(self, pkg: PackageDefinition) -> None:
        self.packages[pkg.name.lower()] = pkg

    def get_package(self, name: str) -> Optional[PackageDefinition]:
        return self.packages.get(name.lower())

    def resolve_type(
        self,
        type_name: str,
        imported_packages: Optional[List[str]] = None,
    ) -> Optional[TypeNode]:
        clean = type_name.strip().lower()
        # 1. Check if qualified: work.pkg.type or pkg.type
        if "." in clean:
            parts = clean.split(".")
            if parts[0] == "work" and len(parts) >= 3:
                pkg = self.packages.get(parts[1])
                if pkg and parts[2] in pkg.types:
                    return pkg.types[parts[2]]
            elif len(parts) == 2:
                pkg = self.packages.get(parts[0])
                if pkg and parts[1] in pkg.types:
                    return pkg.types[parts[1]]

        # 2. Check active imported packages
        if imported_packages:
            for pkg_name in imported_packages:
                pkg = self.packages.get(pkg_name.lower())
                if pkg and clean in pkg.types:
                    return pkg.types[clean]

        # 3. Global project lookup (unambiguous)
        matches = [pkg.types[clean] for pkg in self.packages.values() if clean in pkg.types]
        if len(matches) == 1:
            return matches[0]

        return None

    def resolve_constant(
        self,
        const_name: str,
        imported_packages: Optional[List[str]] = None,
    ) -> Optional[int]:
        clean = const_name.strip().lower()
        if "." in clean:
            parts = clean.split(".")
            if parts[0] == "work" and len(parts) >= 3:
                pkg = self.packages.get(parts[1])
                if pkg and parts[2] in pkg.constants:
                    return pkg.constants[parts[2]]
            elif len(parts) == 2:
                pkg = self.packages.get(parts[0])
                if pkg and parts[1] in pkg.constants:
                    return pkg.constants[parts[1]]

        if imported_packages:
            for pkg_name in imported_packages:
                pkg = self.packages.get(pkg_name.lower())
                if pkg and clean in pkg.constants:
                    return pkg.constants[clean]

        for pkg in self.packages.values():
            if clean in pkg.constants:
                return pkg.constants[clean]
        return None

    def all_types(self) -> Dict[str, TypeNode]:
        merged: Dict[str, TypeNode] = {}
        for pkg in self.packages.values():
            merged.update(pkg.types)
        return merged

    def all_constants(self) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for pkg in self.packages.values():
            merged.update(pkg.constants)
        return merged

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self.packages.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PackageRegistry:
        reg = cls()
        if data and isinstance(data, dict):
            for k, v in data.items():
                reg.packages[k.lower()] = PackageDefinition.from_dict(v)
        return reg


@dataclass
class Signal:
    """An extracted port or internal signal from HDL."""

    name: str
    kind: SignalKind
    type: TypeNode
    line: int
    file: str = ""

    @property
    def is_unknown(self) -> bool:
        if not self.type:
            return True
        if self.type.kind == "unknown":
            return True
        if self.type.computed_width() is None and not getattr(self.type, "is_unconstrained", False):
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "type": self.type.to_dict(),
            "line": self.line,
            "file": self.file,
            "width": self.type.computed_width(),
            "summary": self.type.summary(),
            "is_unknown": self.is_unknown,
            "package": self.type.package if self.type else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Signal:
        return cls(
            name=data["name"],
            kind=data["kind"],
            type=TypeNode.from_dict(data["type"]) or TypeNode(kind="unknown"),
            line=data.get("line", 1),
            file=data.get("file", ""),
        )


@dataclass
class IndexStep:
    """Array indexing step, e.g. (2) or [2]."""

    index: int

    def to_dict(self) -> Dict[str, Any]:
        return {"step": "index", "index": self.index}


@dataclass
class FieldStep:
    """Record field step, e.g. .tdata."""

    field: str

    def to_dict(self) -> Dict[str, Any]:
        return {"step": "field", "field": self.field}


@dataclass
class RangeStep:
    """Bit slice range step, e.g. (15 downto 8) or [15:8]."""

    left: int
    right: int
    ascending: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": "range",
            "left": self.left,
            "right": self.right,
            "ascending": self.ascending,
        }


@dataclass
class BitStep:
    """Single bit index step from a vector, e.g. (3) or [3]."""

    bit: int

    def to_dict(self) -> Dict[str, Any]:
        return {"step": "bit", "bit": self.bit}


PathStep = Union[IndexStep, FieldStep, RangeStep, BitStep]


def step_from_dict(d: Dict[str, Any]) -> PathStep:
    st = d.get("step")
    if st == "index":
        return IndexStep(index=int(d["index"]))
    if st == "field":
        return FieldStep(field=str(d["field"]))
    if st == "range":
        return RangeStep(
            left=int(d["left"]),
            right=int(d["right"]),
            ascending=bool(d.get("ascending", False)),
        )
    if st == "bit":
        return BitStep(bit=int(d["bit"]))
    raise ValueError(f"Unknown path step: {st}")


@dataclass
class ProbeMapping:
    """Mapping of an ILA probe to a specific signal and drill-down path."""

    signal: str
    path: List[PathStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "path": [p.to_dict() for p in self.path],
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional[ProbeMapping]:
        if not data:
            return None
        return cls(
            signal=data["signal"],
            path=[step_from_dict(p) for p in data.get("path", [])],
        )


@dataclass
class SignalSnapshot:
    """Saved snapshot of a signal for diff checking on project reload."""

    name: str
    width: int
    kind: str = ""
    type_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional[SignalSnapshot]:
        if not data:
            return None
        return cls(
            name=data["name"],
            width=int(data["width"]),
            kind=data.get("kind", ""),
            type_summary=data.get("type_summary", ""),
        )


@dataclass
class Probe:
    """An individual probe in an ILA core."""

    index: int
    mapping: Optional[ProbeMapping] = None
    width: int = 1
    probe_type: ProbeType = "DATA_AND_TRIGGER"
    mu_cnt: int = 1
    label: str = ""
    snapshot: Optional[SignalSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "mapping": self.mapping.to_dict() if self.mapping else None,
            "width": self.width,
            "probe_type": self.probe_type,
            "mu_cnt": self.mu_cnt,
            "label": self.label,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Probe:
        mapping = ProbeMapping.from_dict(data.get("mapping"))
        snapshot = SignalSnapshot.from_dict(data.get("snapshot"))
        return cls(
            index=int(data["index"]),
            mapping=mapping,
            width=int(data.get("width", 1)),
            probe_type=data.get("probe_type", "DATA_AND_TRIGGER"),
            mu_cnt=int(data.get("mu_cnt", 1)),
            label=data.get("label", ""),
            snapshot=snapshot,
        )


@dataclass
class Ila:
    """An ILA IP core configuration."""

    name: str = "ila_0"
    target_file: str = ""
    target_unit: str = ""
    clock: str = "clk"
    pipe_stages: int = 4  # Default: 4 stages
    data_depth: int = 1024
    same_mu: bool = True
    same_mu_cnt: int = 1
    strg_qual: bool = False
    ip_dir: Optional[str] = None
    run_ooc_synth: bool = True
    probes: List[Probe] = field(default_factory=list)

    def renumber_probes(self) -> None:
        """Ensure probe indices are consecutive 0..N-1."""
        for idx, p in enumerate(self.probes):
            p.index = idx

    def swap_probes(self, idx_a: int, idx_b: int) -> bool:
        """Swap probe positions between index a and index b."""
        if 0 <= idx_a < len(self.probes) and 0 <= idx_b < len(self.probes):
            self.probes[idx_a], self.probes[idx_b] = self.probes[idx_b], self.probes[idx_a]
            self.renumber_probes()
            return True
        return False

    def move_probe(self, from_idx: int, to_idx: int) -> bool:
        """Move probe from one position to another, shifting intermediate probes."""
        if 0 <= from_idx < len(self.probes) and 0 <= to_idx < len(self.probes):
            item = self.probes.pop(from_idx)
            self.probes.insert(to_idx, item)
            self.renumber_probes()
            return True
        return False

    def insert_probe(self, at_idx: int, probe: Probe) -> None:
        """Insert a probe at a specific index."""
        clamped_idx = max(0, min(at_idx, len(self.probes)))
        self.probes.insert(clamped_idx, probe)
        self.renumber_probes()

    def delete_probe(self, idx: int) -> bool:
        """Delete a probe by index."""
        if 0 <= idx < len(self.probes):
            self.probes.pop(idx)
            self.renumber_probes()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "target_file": self.target_file,
            "target_unit": self.target_unit,
            "clock": self.clock,
            "pipe_stages": self.pipe_stages,
            "data_depth": self.data_depth,
            "same_mu": self.same_mu,
            "same_mu_cnt": self.same_mu_cnt,
            "strg_qual": self.strg_qual,
            "ip_dir": self.ip_dir,
            "run_ooc_synth": self.run_ooc_synth,
            "probes": [p.to_dict() for p in self.probes],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Ila:
        probes = [Probe.from_dict(p) for p in data.get("probes", [])]
        ila = cls(
            name=data.get("name", "ila_0"),
            target_file=data.get("target_file", ""),
            target_unit=data.get("target_unit", ""),
            clock=data.get("clock", "clk"),
            pipe_stages=int(data.get("pipe_stages", 4)),
            data_depth=int(data.get("data_depth", 1024)),
            same_mu=bool(data.get("same_mu", True)),
            same_mu_cnt=int(data.get("same_mu_cnt", 1)),
            strg_qual=bool(data.get("strg_qual", False)),
            ip_dir=data.get("ip_dir"),
            run_ooc_synth=bool(data.get("run_ooc_synth", True)),
            probes=probes,
        )
        ila.renumber_probes()
        return ila


@dataclass
class Project:
    """An ILA Manager project holding multiple ILAs and referenced HDL files."""

    version: int = 1
    source_files: List[str] = field(default_factory=list)
    ilas: List[Ila] = field(default_factory=list)
    package_registry: PackageRegistry = field(default_factory=PackageRegistry)

    def get_ila(self, name: str) -> Optional[Ila]:
        for ila in self.ilas:
            if ila.name == name:
                return ila
        return None

    def add_ila(self, ila: Ila) -> None:
        if not self.get_ila(ila.name):
            self.ilas.append(ila)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "source_files": list(self.source_files),
            "ilas": [ila.to_dict() for ila in self.ilas],
            "package_registry": self.package_registry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        pkg_reg_data = data.get("package_registry", {})
        return cls(
            version=int(data.get("version", 1)),
            source_files=list(data.get("source_files", [])),
            ilas=[Ila.from_dict(d) for d in data.get("ilas", [])],
            package_registry=PackageRegistry.from_dict(pkg_reg_data),
        )
