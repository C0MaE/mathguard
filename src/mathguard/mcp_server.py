"""MCP server so AI assistants (Claude Desktop, Claude Code, …) can call mathguard.

Install with ``pip install "mathguard[mcp]"`` and register the command
``mathguard-mcp`` as a stdio server in your client.
"""

from __future__ import annotations

from typing import Any

from .api import LLM_INSTRUCTIONS, verify
from .checks import check_chain, check_equal
from .units import check_dimensions
from .verdict import Report


def _server_class():
    try:  # MCP Python SDK 2.x
        from mcp.server.mcpserver import MCPServer
        return MCPServer
    except ImportError:
        pass
    try:  # MCP Python SDK 1.x
        from mcp.server.fastmcp import FastMCP
        return FastMCP
    except ImportError as exc:
        raise SystemExit(
            "The MCP server needs the 'mcp' package: pip install \"mathguard[mcp]\""
        ) from exc


def build_server():
    Server = _server_class()
    server = Server(name="mathguard", instructions=LLM_INSTRUCTIONS)

    @server.tool()
    def verify_math(checks: list[dict[str, Any]]) -> dict[str, Any]:
        """Verify mathematical claims. `checks` is a list of check objects such as
        {"check": "equal", "lhs": "(a+b)^2", "rhs": "a^2 + 2a b + b^2"},
        {"check": "chain", "steps": [...]}, {"check": "derivative", ...},
        {"check": "antiderivative", ...}, {"check": "definite_integral", ...},
        {"check": "solutions", ...}, {"check": "value", ...}, {"check": "limit", ...}
        or {"check": "dimensions", "equation": "E = m c^2", "units": {...}}.
        See the server instructions for all fields."""
        return verify(checks).to_dict()

    @server.tool()
    def check_identity(lhs: str, rhs: str,
                       assumptions: dict[str, str] | None = None) -> dict[str, Any]:
        """Check that lhs == rhs for all values of the variables.
        assumptions example: {"x": "positive"}."""
        return Report([check_equal(lhs, rhs, assumptions)]).to_dict()

    @server.tool()
    def check_derivation(steps: list[str],
                         assumptions: dict[str, str] | None = None) -> dict[str, Any]:
        """Check a derivation step by step; reports which step is wrong."""
        return check_chain(steps, assumptions).to_dict()

    @server.tool()
    def check_units(equation: str, units: dict[str, str]) -> dict[str, Any]:
        """Check an equation for dimensional consistency.
        units example: {"E": "J", "m": "kg", "c": "m/s"}."""
        return Report([check_dimensions(units, equation=equation)]).to_dict()

    @server.tool()
    def check_solution(text: str, units: dict[str, str] | None = None,
                       assumptions: dict[str, str] | None = None) -> dict[str, Any]:
        """Check a whole worked solution written in Markdown with LaTeX formulas
        ($...$, $$...$$, align). Every chain a = b = c is checked step by step,
        numbers like \\approx 35{,}3\\,\\mathrm{m} are recomputed, later equations
        are compared with earlier ones. Give units (e.g. {"v0": "m/s"}) to also
        check the dimensions of every step. Variables count as positive.
        Use this on your own answer before presenting it; fix every refuted line."""
        from .document import check_document
        return check_document(text, units=units, assumptions=assumptions).to_dict()

    @server.tool()
    def check_answer(answer: str, reference: dict[str, Any],
                     given: dict[str, str] | None = None,
                     units: dict[str, str] | None = None) -> dict[str, Any]:
        """Grade the final results of an answer against a reference solution.
        reference maps each wanted quantity to a formula or a value with unit,
        e.g. {"v": "sqrt(10 g h / 7)"} or {"v": {"formula": "sqrt(10 g h / 7)",
        "unit": "m/s"}} or {"t": "2.04 s"}. given holds known values
        ({"h": "1.2 m", "g": "9.81 m/s^2"}) so formulas can be turned into numbers;
        units gives units of other variables ({"m": "kg"}). Formulas are compared
        symbolically, numbers with unit conversion and a 1 % tolerance (or the
        rounding of the written digits). Use this when a reference solution
        exists; without one, use check_solution on the working."""
        from .answer import check_answer as _check_answer
        return _check_answer(answer, reference, given=given, units=units).to_dict()

    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
