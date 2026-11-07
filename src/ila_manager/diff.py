"""Diff detection between saved project probes and current HDL signals."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from ila_manager.models import Ila, RangeStep, Signal
from ila_manager.selection import resolve_selection

DiffKind = Literal[
    "ok",
    "signal_missing",
    "width_changed",
    "slice_out_of_range",
    "type_changed",
]


@dataclass
class DiffItem:
    """A discrepancy detected for a specific probe."""

    probe_index: int
    probe_name: str
    kind: DiffKind
    message: str
    old_width: int
    new_width: Optional[int] = None
    old_signal: str = ""
    suggested_signal: Optional[str] = None
    similarity_score: float = 0.0
    allowed_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "probe_index": self.probe_index,
            "probe_name": self.probe_name,
            "kind": self.kind,
            "message": self.message,
            "old_width": self.old_width,
            "new_width": self.new_width,
            "old_signal": self.old_signal,
            "suggested_signal": self.suggested_signal,
            "similarity_score": round(self.similarity_score, 2),
            "allowed_actions": list(self.allowed_actions),
        }


def compute_diff(ila: Ila, current_signals: List[Signal]) -> List[DiffItem]:
    """Compare an ILA's probes against currently available HDL signals."""
    signal_map: Dict[str, Signal] = {s.name: s for s in current_signals}
    diffs: List[DiffItem] = []

    for probe in ila.probes:
        if not probe.mapping:
            continue

        sig_name = probe.mapping.signal
        probe_name = f"probe{probe.index}"
        curr_sig = signal_map.get(sig_name)

        if curr_sig is None:
            # Signal was deleted or renamed
            # Find best match among unmapped or existing signals with same width
            best_match: Optional[str] = None
            best_score = 0.0
            for cand_name, cand_sig in signal_map.items():
                cand_w = cand_sig.type.computed_width()
                if cand_w == probe.width:
                    ratio = difflib.SequenceMatcher(
                        None, sig_name.lower(), cand_name.lower()
                    ).ratio()
                    if ratio > best_score and ratio >= 0.5:
                        best_score = ratio
                        best_match = cand_name

            msg = f"Signal '{sig_name}' was not found in the HDL files."
            actions = ["delete", "keep_unmapped"]
            if best_match:
                actions.insert(0, "remap")
                msg += f" Suggested match: '{best_match}' (similarity {int(best_score * 100)}%)."

            diffs.append(
                DiffItem(
                    probe_index=probe.index,
                    probe_name=probe_name,
                    kind="signal_missing",
                    message=msg,
                    old_width=probe.width,
                    old_signal=sig_name,
                    suggested_signal=best_match,
                    similarity_score=best_score,
                    allowed_actions=actions,
                )
            )
            continue

        # Signal exists, check slice validity and width
        resolved = resolve_selection(probe.mapping, curr_sig)
        new_w = resolved.width

        # Check for range step out of bounds
        slice_error = False
        for step in probe.mapping.path:
            if isinstance(step, RangeStep):
                max_bound = max(step.left, step.right)
                sig_w = curr_sig.type.computed_width()
                if sig_w is not None and max_bound >= sig_w:
                    slice_error = True
                    break

        if slice_error:
            diffs.append(
                DiffItem(
                    probe_index=probe.index,
                    probe_name=probe_name,
                    kind="slice_out_of_range",
                    message=(
                        f"Probe slice on '{sig_name}' is out of range for current signal bounds."
                    ),
                    old_width=probe.width,
                    new_width=new_w,
                    old_signal=sig_name,
                    allowed_actions=["follow_new_width", "delete"],
                )
            )
        elif new_w != probe.width:
            diffs.append(
                DiffItem(
                    probe_index=probe.index,
                    probe_name=probe_name,
                    kind="width_changed",
                    message=(
                        f"Signal '{sig_name}' width changed from {probe.width} to {new_w} bits."
                    ),
                    old_width=probe.width,
                    new_width=new_w,
                    old_signal=sig_name,
                    allowed_actions=["follow_new_width", "keep_old_width", "delete"],
                )
            )

    return diffs
