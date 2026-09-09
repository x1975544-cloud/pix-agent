from __future__ import annotations

from pix.analysis.repository import RepositoryAnalyzer


def test_analyzer_python_fastapi(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies=['fastapi>=0.115']\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    analyzer = RepositoryAnalyzer()
    context = analyzer.analyze(tmp_path)
    assert context.language == "python"
    assert context.framework == "FastAPI"
    assert context.entrypoint == "app.py"
    assert context.test_command == "python -m pytest -q"
    assert "tests" in context.test_directories


def test_analyzer_node(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "pytest"}, "dependencies": {"next": "14"}}', encoding="utf-8"
    )
    context = RepositoryAnalyzer().analyze(tmp_path)
    assert context.language == "node"
    assert context.framework == "Next.js"
