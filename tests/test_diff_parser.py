from app.analyzer.diff_parser import GitDiffParser


SAMPLE = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,4 +1,7 @@
 def process(orders):
-    return 0
+    total = 0
+    for o in orders:
+        total += o.price
+    return total
 create_report()
@@ -20,3 +23,4 @@ def other():
     x = 1
+    y = 2
     return x
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # Title
+new line here
"""


def test_indexes_by_new_filename():
    files = GitDiffParser.parse_patch(SAMPLE)
    assert set(files) == {"service.py", "README.md"}


def test_added_line_numbers_match_new_file_positions():
    files = GitDiffParser.parse_patch(SAMPLE)
    fd = files["service.py"]

    # Hunk 1 starts at new-file line 1: context occupies line 1,
    # the removed line consumes no new-file number, additions land on 2-5.
    assert fd.added_lines[2] == "    total = 0"
    assert fd.added_lines[3] == "    for o in orders:"
    assert fd.added_lines[4] == "        total += o.price"
    assert fd.added_lines[5] == "    return total"

    # Hunk 2 header @@ +23: context takes 23, then the addition lands on 24.
    assert fd.added_lines[24] == "    y = 2"

    # Context lines are never recorded as review targets.
    assert 1 not in fd.added_lines
    assert 6 not in fd.added_lines
    assert 23 not in fd.added_lines


def test_valid_lines_only_contain_added_lines():
    files = GitDiffParser.parse_patch(SAMPLE)
    fd = files["service.py"]
    assert fd.valid_lines == {2, 3, 4, 5, 24}
    # Old-file line numbers are never valid targets either.
    assert 20 not in fd.valid_lines


def test_removed_lines_are_not_review_targets():
    files = GitDiffParser.parse_patch(SAMPLE)
    for content in files["service.py"].added_lines.values():
        assert content != "    return 0"


def test_second_file_parsed_independently():
    files = GitDiffParser.parse_patch(SAMPLE)
    assert files["README.md"].added_lines == {2: "new line here"}