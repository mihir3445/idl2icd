"""Associates /** ... */ and /// doc-comment blocks with the line of the
declaration that immediately follows them. IDL's own comment syntax isn't
part of the grammar (comments are %ignore'd for parsing), so we recover
doc-comments in a separate text pass and look them up by line number after
parsing, using Lark's token line metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DOC_BLOCK_RE = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)
DOC_LINE_RE = re.compile(r"^\s*///\s?(.*)$")


@dataclass
class DocCommentIndex:
    # maps the 1-indexed source line immediately AFTER a doc comment block
    # to the cleaned comment text
    by_next_line: dict[int, str]

    def for_line(self, line: int) -> str | None:
        return self.by_next_line.get(line)


def extract_doc_comments(source: str) -> DocCommentIndex:
    lines = source.splitlines()
    by_next_line: dict[int, str] = {}

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # /** ... */ possibly spanning multiple lines
        if "/**" in line:
            # naive: join lines until closing */
            joined = line
            j = i
            while "*/" not in joined:
                j += 1
                if j >= n:
                    break
                joined += "\n" + lines[j]
            match = DOC_BLOCK_RE.search(joined)
            if match:
                text = _clean_block(match.group(1))
                by_next_line[j + 2] = text  # line after the closing */ (1-indexed)
            i = j + 1
            continue

        # consecutive /// lines
        if DOC_LINE_RE.match(line):
            block = []
            j = i
            while j < n and DOC_LINE_RE.match(lines[j]):
                block.append(DOC_LINE_RE.match(lines[j]).group(1))
                j += 1
            by_next_line[j + 1] = "\n".join(block).strip()
            i = j
            continue

        i += 1

    return DocCommentIndex(by_next_line=by_next_line)


def _clean_block(raw: str) -> str:
    cleaned_lines = []
    for line in raw.splitlines():
        line = line.strip()
        line = re.sub(r"^\*\s?", "", line)
        cleaned_lines.append(line)
    return "\n".join(l for l in cleaned_lines if l).strip()
