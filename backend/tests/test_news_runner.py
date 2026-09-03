import ast
from pathlib import Path


def test_runner_declares_google_news_thumbnail_method() -> None:
    runner_path = Path(__file__).parents[1] / "app" / "collectors" / "runner.py"
    tree = ast.parse(runner_path.read_text(encoding="utf-8"))
    runner_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "NewsCollectorRunner"
    )
    method_names = {
        node.name for node in runner_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_google_news_thumbnail" in method_names


def test_noataque_uses_portal_logo_instead_of_external_thumbnail() -> None:
    source = Path(__file__).parents[1] / "app" / "collectors" / "runner.py"
    code = source.read_text(encoding="utf-8")
    assert 'if rule.slug == "noataque-atletico":' in code
    assert "candidate.imagem_url = None" in code
