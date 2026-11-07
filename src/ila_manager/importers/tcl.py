"""Import ILA configurations from Vivado TCL scripts."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from ila_manager.models import Ila, Probe, ProbeType

TYPE_INT_TO_NAME: Dict[int, ProbeType] = {
    0: "DATA_AND_TRIGGER",
    1: "DATA",
    2: "TRIGGER",
}


def import_from_tcl(text: str) -> Optional[Ila]:
    """Parse a Vivado TCL script containing ILA IP properties and return an Ila object."""
    # 1. Module name from create_ip or get_ips
    module_name = "ila_0"
    m_create = re.search(r"\bcreate_ip\b.*?-module_name\s+([a-zA-Z0-9_]+)", text)
    if m_create:
        module_name = m_create.group(1)
    else:
        m_get = re.search(r"\[get_ips\s+([a-zA-Z0-9_]+)\]", text)
        if m_get:
            module_name = m_get.group(1)

    # 2. Extract CONFIG properties from set_property -dict [list ...] [get_ips ...]
    # Clean continuation backslashes
    clean_text = text.replace("\\\n", " ")

    props: Dict[str, str] = {}
    prop_matches = re.finditer(
        r"CONFIG\.([a-zA-Z0-9_]+)\s*\{([^}]*)\}", clean_text
    )
    for pm in prop_matches:
        k = pm.group(1).upper()
        v = pm.group(2).strip()
        props[k] = v

    if not props:
        return None

    # Global options
    num_probes = int(props.get("C_NUM_OF_PROBES", "1"))
    pipe_stages = int(props.get("C_INPUT_PIPE_STAGES", "4"))
    data_depth = int(props.get("C_DATA_DEPTH", "1024"))
    strg_qual = props.get("C_EN_STRG_QUAL", "0") in ("1", "true", "TRUE")
    same_mu_str = props.get("ALL_PROBE_SAME_MU", "true").lower()
    same_mu = same_mu_str in ("true", "1")
    same_mu_cnt = int(props.get("ALL_PROBE_SAME_MU_CNT", "1"))

    # Build probes list
    probes: List[Probe] = []
    for i in range(num_probes):
        width = int(props.get(f"C_PROBE{i}_WIDTH", "1"))
        type_code = int(props.get(f"C_PROBE{i}_TYPE", "0"))
        mu_cnt = int(props.get(f"C_PROBE{i}_MU_CNT", str(same_mu_cnt)))
        probe_type = TYPE_INT_TO_NAME.get(type_code, "DATA_AND_TRIGGER")

        probes.append(
            Probe(
                index=i,
                width=width,
                probe_type=probe_type,
                mu_cnt=mu_cnt,
            )
        )

    return Ila(
        name=module_name,
        pipe_stages=pipe_stages,
        data_depth=data_depth,
        same_mu=same_mu,
        same_mu_cnt=same_mu_cnt,
        strg_qual=strg_qual,
        probes=probes,
    )
