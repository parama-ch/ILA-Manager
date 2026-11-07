"""Tests for Vivado TCL generator."""

from ila_manager.generators.tcl import generate_tcl
from ila_manager.models import Ila, Probe


def test_tcl_generator_default_pipe_stages():
    ila = Ila(
        name="my_ila",
        clock="clk",
        pipe_stages=4,  # default is 4!
        data_depth=2048,
        same_mu=True,
        same_mu_cnt=2,
        probes=[
            Probe(index=0, width=1, probe_type="DATA_AND_TRIGGER"),
            Probe(index=1, width=16, probe_type="DATA"),
            Probe(index=2, width=32, probe_type="TRIGGER"),
        ],
    )

    tcl = generate_tcl(ila)

    # Check existence check
    assert 'if {[llength [get_ips -quiet $ila_name]] == 0}' in tcl
    assert 'create_ip -name ila -vendor xilinx.com -library ip -module_name $ila_name' in tcl

    # Check properties
    assert "CONFIG.C_NUM_OF_PROBES      {3}" in tcl
    assert "CONFIG.C_INPUT_PIPE_STAGES  {4}" in tcl
    assert "CONFIG.C_DATA_DEPTH         {2048}" in tcl
    assert "CONFIG.ALL_PROBE_SAME_MU    {true}" in tcl
    assert "CONFIG.ALL_PROBE_SAME_MU_CNT {2}" in tcl

    # Check probe types: 0 = DATA_AND_TRIGGER, 1 = DATA, 2 = TRIGGER
    assert "CONFIG.C_PROBE0_WIDTH {1}  CONFIG.C_PROBE0_TYPE {0}" in tcl
    assert "CONFIG.C_PROBE1_WIDTH {16}  CONFIG.C_PROBE1_TYPE {1}" in tcl
    assert "CONFIG.C_PROBE2_WIDTH {32}  CONFIG.C_PROBE2_TYPE {2}" in tcl

    # Check targets and synthesis run
    assert "generate_target all" in tcl
    assert "launch_runs ${ila_name}_synth_1" in tcl


def test_tcl_generator_individual_mu():
    ila = Ila(
        name="my_ila",
        same_mu=False,
        probes=[
            Probe(index=0, width=1, mu_cnt=1),
            Probe(index=1, width=8, mu_cnt=4),
        ],
    )

    tcl = generate_tcl(ila)
    assert "CONFIG.ALL_PROBE_SAME_MU    {false}" in tcl
    assert "CONFIG.C_PROBE0_MU_CNT {1}" in tcl
    assert "CONFIG.C_PROBE1_MU_CNT {4}" in tcl
