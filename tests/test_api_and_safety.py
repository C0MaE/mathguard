import json

import pytest

import mathguard as mg
from mathguard import ParseError, Status
from mathguard.cli import main


def test_verify_batch():
    report = mg.verify([
        {"id": 1, "check": "equal", "lhs": "(a+b)^2", "rhs": "a^2 + 2a*b + b^2"},
        {"id": 2, "check": "derivative", "function": "x^3", "claimed": "3x^2"},
        {"id": 3, "check": "dimensions", "equation": "E = m c^2",
         "units": {"E": "J", "m": "kg", "c": "m/s"}},
    ])
    assert report.ok
    assert [v.details["id"] for v in report.verdicts] == [1, 2, 3]


def test_verify_json_roundtrip_and_errors():
    out = json.loads(mg.verify_json('{"checks": [{"check": "equal", "lhs": "1", "rhs": "2"}]}'))
    assert out["status"] == "refuted" and out["ok"] is False
    out = json.loads(mg.verify_json("not json"))
    assert out["status"] == "error"
    out = json.loads(mg.verify_json('{"check": "nonsense"}'))
    assert "unknown check" in out["results"][0]["message"]
    out = json.loads(mg.verify_json('{"check": "equal", "lhs": "x"}'))
    assert out["status"] == "error" and "rhs" in out["results"][0]["message"]


@pytest.mark.parametrize("evil", [
    "__import__('os').system('echo hacked')",
    "x.__class__",
    "().__class__.__bases__",
    "open(1)",
    "eval(1)",
    "x; y",
    "a.b",
    "x" * 5000,
])
def test_parser_rejects_code(evil):
    with pytest.raises(ParseError):
        mg.parse(evil)


def test_bad_input_gives_error_status_not_exception():
    assert mg.check_equal("x +* ", "1").status == Status.ERROR
    assert mg.check_equal("__import__('os')", "1").status == Status.ERROR


def test_physics_names_are_plain_symbols():
    e = mg.parse("E + I + lambda + gamma")
    assert {s.name for s in e.free_symbols} == {"E", "I", "lambda", "gamma"}
    assert mg.parse("e^0") == 1          # e is Euler's number
    assert mg.parse("gamma(5)") == 24    # gamma( ) is the Gamma function


def test_cli_exit_codes(capsys, tmp_path):
    assert main(["equal", "sin(x)^2 + cos(x)^2", "1"]) == 0
    assert main(["equal", "sqrt(x^2)", "x"]) == 1
    assert main(["equal", "sqrt(x^2)", "x", "--assume", "x=positive"]) == 0
    assert main(["dims", "E = m c^2", "--unit", "E=J", "--unit", "m=kg",
                 "--unit", "c=speed_of_light"]) == 0
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"check": "chain", "steps": ["(x+1)^2", "x^2 + 2x + 1"]}))
    capsys.readouterr()  # discard earlier output
    assert main(["--json", "check", str(f)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


def test_merged_letters_hint():
    v = mg.check_equal("(a+b)^2", "a^2 + 2ab + b^2")
    assert v.status == Status.REFUTED and "'ab' was read as a single variable" in v.message


def test_mcp_server_registers_tools():
    pytest.importorskip("mcp")
    import asyncio
    from mathguard.mcp_server import build_server
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert {"verify_math", "check_identity", "check_derivation", "check_units"} <= names
