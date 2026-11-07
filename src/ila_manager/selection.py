"""Selection resolver for signals, array indexing, record fields, and bit slicing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from ila_manager.models import (
    BitStep,
    FieldStep,
    IndexStep,
    ProbeMapping,
    RangeStep,
    Signal,
    TypeNode,
)


@dataclass
class ResolvedSelection:
    """Outcome of resolving a probe mapping against a signal's type."""

    signal_name: str
    width: int
    vhdl_expr: str
    verilog_expr: str
    is_single_bit: bool
    needs_intermediate: bool  # True for VHDL types that cannot appear in port maps (integer, enum, etc.)
    intermediate_type: str = ""  # e.g. "std_logic_vector(7 downto 0)"
    intermediate_assign: str = ""  # e.g. "std_logic_vector(to_unsigned(cnt, 8))"
    final_type: Optional[TypeNode] = None
    error: Optional[str] = None


def resolve_selection(
    mapping: ProbeMapping,
    signal: Signal,
    target_lang: Literal["vhdl", "verilog"] = "vhdl",
) -> ResolvedSelection:
    """Resolve a ProbeMapping against a Signal and produce expressions and width."""
    curr_type: Optional[TypeNode] = signal.type
    vhdl_parts = [signal.name]
    verilog_parts = [signal.name]

    if not mapping.path:
        # Full signal mapping
        width = curr_type.computed_width() if curr_type else None
        if width is None:
            width = 1

        is_bit = (curr_type.kind == "bit") if curr_type else (width == 1)
        base = (curr_type.base or "").lower() if curr_type else ""

        # VHDL conversions for standard types
        needs_intermediate = False
        intermediate_type = ""
        intermediate_assign = ""

        if curr_type and curr_type.kind in ("integer", "enum", "boolean"):
            needs_intermediate = True
            intermediate_type = f"std_logic_vector({width - 1} downto 0)"
            if curr_type.kind == "integer":
                intermediate_assign = f"std_logic_vector(to_unsigned({signal.name}, {width}))"
            elif curr_type.kind == "boolean":
                intermediate_assign = f"\"1\" when {signal.name} else \"0\""
            elif curr_type.kind == "enum":
                intermediate_assign = f"std_logic_vector(to_unsigned({curr_type.base}'pos({signal.name}), {width}))"
            vhdl_expr = signal.name  # generator will replace with intermediate signal name
        elif base in ("unsigned", "signed"):
            vhdl_expr = f"std_logic_vector({signal.name})"
        else:
            vhdl_expr = signal.name

        verilog_expr = signal.name

        return ResolvedSelection(
            signal_name=signal.name,
            width=width,
            vhdl_expr=vhdl_expr,
            verilog_expr=verilog_expr,
            is_single_bit=is_bit,
            needs_intermediate=needs_intermediate,
            intermediate_type=intermediate_type,
            intermediate_assign=intermediate_assign,
            final_type=curr_type,
        )

    # Walk the path steps
    for step in mapping.path:
        if curr_type is None:
            break

        if isinstance(step, IndexStep):
            vhdl_parts.append(f"({step.index})")
            verilog_parts.append(f"[{step.index}]")
            curr_type = curr_type.element

        elif isinstance(step, FieldStep):
            vhdl_parts.append(f".{step.field}")
            verilog_parts.append(f".{step.field}")
            curr_type = curr_type.fields.get(step.field)

        elif isinstance(step, RangeStep):
            dir_str = "to" if step.ascending else "downto"
            vhdl_parts.append(f"({step.left} {dir_str} {step.right})")
            verilog_parts.append(f"[{step.left}:{step.right}]")
            curr_type = TypeNode(
                kind="vector",
                left=step.left,
                right=step.right,
                ascending=step.ascending,
                base=curr_type.base,
            )

        elif isinstance(step, BitStep):
            vhdl_parts.append(f"({step.bit})")
            verilog_parts.append(f"[{step.bit}]")
            curr_type = TypeNode(kind="bit", base="std_logic")

    width = curr_type.computed_width() if curr_type else 1
    if width is None:
        width = 1

    is_bit = (curr_type.kind == "bit") if curr_type else (width == 1)
    base = (curr_type.base or "").lower() if curr_type else ""

    vhdl_str = "".join(vhdl_parts)
    if base in ("unsigned", "signed"):
        vhdl_str = f"std_logic_vector({vhdl_str})"

    verilog_str = "".join(verilog_parts)

    return ResolvedSelection(
        signal_name=signal.name,
        width=width,
        vhdl_expr=vhdl_str,
        verilog_expr=verilog_str,
        is_single_bit=is_bit,
        needs_intermediate=False,
        final_type=curr_type,
    )
