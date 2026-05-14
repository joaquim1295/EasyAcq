"""Usado por git filter-branch --msg-filter: remove trailer Co-authored-by do Cursor."""
import sys

_DROP = "Co-authored-by: Cursor <cursoragent@cursor.com>"


def main() -> None:
    raw = sys.stdin.read()
    out: list[str] = []
    for line in raw.splitlines(keepends=True):
        if line.rstrip("\r\n").strip() == _DROP:
            continue
        out.append(line)
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
