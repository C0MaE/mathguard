from mathguard import cli, mcp_server


def test_mcp_subcommand_starts_server(monkeypatch):
    called = []
    monkeypatch.setattr(mcp_server, "main", lambda: called.append(True))
    assert cli.main(["mcp"]) == 0
    assert called == [True]
