def test_imports_smoke():
    # Minimal smoke test so pytest always runs at least one test.
    import app.cli  # noqa: F401
    import app.runner  # noqa: F401
