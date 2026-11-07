"""Tests for FastAPI backend REST endpoints."""

from fastapi.testclient import TestClient

from ila_manager.server import app

client = TestClient(app)


def test_api_parse_hdl_content():
    vhdl_sample = """
    library ieee;
    use ieee.std_logic_1164.all;
    entity top is
        port (
            clk   : in  std_logic;
            data  : out std_logic_vector(7 downto 0)
        );
    end entity top;
    """
    res = client.post(
        "/api/hdl/parse",
        json={"files": [{"filename": "top.vhd", "content": vhdl_sample}]},
    )
    assert res.status_code == 200
    data = res.json()
    assert "top" in data["units"]
    signals = data["units"]["top"]
    assert len(signals) == 2
    assert signals[0]["name"] == "clk"
    assert signals[1]["name"] == "data"


def test_api_generate_code():
    req_body = {
        "ila": {
            "name": "ila_test",
            "pipe_stages": 4,
            "data_depth": 1024,
            "same_mu": True,
            "same_mu_cnt": 1,
            "probes": [
                {"index": 0, "width": 1, "probe_type": "DATA_AND_TRIGGER"},
                {"index": 1, "width": 8, "probe_type": "DATA"},
            ],
        },
        "signals": [
            {"name": "clk", "kind": "port_in", "type": {"kind": "bit", "base": "std_logic"}, "line": 1},
        ],
    }

    res = client.post("/api/generate", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert "create_ip -name ila" in data["tcl"]
    assert "CONFIG.C_INPUT_PIPE_STAGES  {4}" in data["tcl"]
    assert "u_ila_test : entity work.ila_test" in data["vhdl"]
    assert "ila_test u_ila_test (" in data["verilog"]


def test_api_i18n():
    res_en = client.get("/api/i18n/en")
    assert res_en.status_code == 200
    assert "app_title" in res_en.json()

    res_th = client.get("/api/i18n/th")
    assert res_th.status_code == 200
    assert "app_title" in res_th.json()
