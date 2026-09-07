import json
from pathlib import Path

import pytest

from project_continuity_kit.cli import main
from project_continuity_kit.core import analyze


@pytest.mark.parametrize("value", [None, [], [{}], "text", 42, True])
def test_invalid_json_roots_are_actionable(value: object, tmp_path: Path, capsys) -> None:
    with pytest.raises((ValueError, TypeError), match="JSON object"):
        analyze(value)  # type: ignore[arg-type]
    source = tmp_path / "input.json"
    source.write_text(json.dumps(value), encoding="utf-8")
    assert main([str(source)]) == 2
    error = capsys.readouterr().err
    assert "JSON object" in error and "Traceback" not in error
