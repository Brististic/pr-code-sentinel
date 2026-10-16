import re
from typing import Dict, List, Optional


class DiffHunk:
    def __init__(self, old_start: int, new_start: int, lines: List[str]):
        self.old_start = old_start
        self.new_start = new_start
        self.lines = lines


class FileDiff:
    def __init__(self, filename: str):
        self.filename = filename
        self.added_lines: Dict[int, str] = {}  # new_line_number -> code_content
        self.valid_lines: set[int] = set()

    def add_line(self, line_num: int, content: str):
        self.added_lines[line_num] = content
        self.valid_lines.add(line_num)


class GitDiffParser:
    """Parses standard Unified Diff format (git diff)."""

    HUNK_HEADER_REGEX = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    @classmethod
    def parse_patch(cls, patch_text: str) -> Dict[str, FileDiff]:
        """Parses a multi-file unified diff into file-mapped structures."""
        files: Dict[str, FileDiff] = {}
        current_file: Optional[FileDiff] = None
        current_line_no = 0

        for raw_line in patch_text.splitlines():
            # Check new file header
            if raw_line.startswith("+++ b/"):
                filename = raw_line[6:].strip()
                current_file = FileDiff(filename)
                files[filename] = current_file
                continue

            # Detect hunk header
            if raw_line.startswith("@@ "):
                match = cls.HUNK_HEADER_REGEX.match(raw_line)
                if match and current_file:
                    current_line_no = int(match.group(3))
                continue

            if not current_file:
                continue

            # Process diff line markers
            if raw_line.startswith("+"):
                line_content = raw_line[1:]
                current_file.add_line(current_line_no, line_content)
                current_line_no += 1
            elif raw_line.startswith(" "):
                # Unchanged context line
                current_line_no += 1
            elif raw_line.startswith("-"):
                # Removed line; doesn't increment new file counter
                continue

        return files