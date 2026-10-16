from app.analyzer.ast_analyzer import StaticASTAnalyzer


def test_catches_dangerous_mutable_defaults():
    analyzer = StaticASTAnalyzer()
    bad_code = """
def append_item(val, items=[]):
    items.append(val)
    return items
"""
    violations = analyzer.analyze_source(bad_code)
    assert any(v.category == "SECURITY_BUG" for v in violations)


def test_catches_bare_except():
    analyzer = StaticASTAnalyzer()
    bad_code = """
def fetch_data():
    try:
        x = 1 / 0
    except:
        pass
"""
    violations = analyzer.analyze_source(bad_code)
    assert any(v.category == "ANTI_PATTERN" for v in violations)