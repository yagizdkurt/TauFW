# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Serialize ordinary values; optional YAML support is loaded on demand."""

import csv
import importlib
import io
import json
import re
from typing import Any, Iterable, Mapping, Sequence

_TEMPLATE_TOKEN = re.compile(r"\$\{(\w+)\}|\$(\w+)\b")


def read_json(text: str) -> Any:
    return json.loads(text)


def write_json(value: Any, indent: int, sort_keys: bool) -> str:
    return json.dumps(value, indent=indent, sort_keys=sort_keys, ensure_ascii=False) + "\n"


def yaml_module():
    try:
        return importlib.import_module("yaml")
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        raise ModuleNotFoundError("FileIO YAML operations require PyYAML.", name="yaml") from error


def read_yaml(text: str) -> Any:
    return yaml_module().safe_load(text)


def write_yaml(value: Any) -> str:
    return yaml_module().safe_dump(value, sort_keys=False, allow_unicode=True)


def read_csv(text: str, delimiter: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))


def write_csv(rows: Iterable[Sequence[object]], delimiter: str) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue()


def join_lines(lines: Iterable[str], description: str) -> str:
    """Terminate each line with a newline; description names the lines in the error message."""
    text_lines = list(lines)
    if any("\n" in line or "\r" in line for line in text_lines):
        raise ValueError(f"{description} cannot contain newline characters.")
    return "".join(line + "\n" for line in text_lines)


def render_template(template: str, substitutions: Mapping[str, str], excluded_lines: Sequence[str],
                    appended_lines: Iterable[str]) -> str:
    """Drop excluded lines, replace $NAME/${NAME} literally, keep unknown tokens, then append lines."""
    content = "".join(line for line in template.splitlines(keepends=True)
                      if not any(excluded in line for excluded in excluded_lines))
    content = _TEMPLATE_TOKEN.sub(
        lambda match: substitutions.get(match.group(1) or match.group(2), match.group(0)), content,
    )
    extra_text = join_lines(appended_lines, "Appended template lines")
    if extra_text and content and not content.endswith("\n"):
        content += "\n"
    return content + extra_text
