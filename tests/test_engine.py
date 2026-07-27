from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from image_editor_plugin.engine import ImageMagickEngine


def test_engine_uses_argument_array_shell_false(tmp_path: Path) -> None:
    engine = ImageMagickEngine("magick")
    version = subprocess.CompletedProcess(
        ["magick", "-version"],
        0,
        "Version: ImageMagick 7.1.1-47 Delegates: png jpeg lcms",
        "",
    )
    completed = subprocess.CompletedProcess(["magick"], 0, "", "")
    with patch(
        "image_editor_plugin.engine.subprocess.run", side_effect=[version, completed]
    ) as run:
        engine.run(["canvas:none", str(tmp_path / "name;$(bad).png")])
    command = run.call_args_list[1].args[0]
    assert isinstance(command, list)
    assert run.call_args_list[1].kwargs["shell"] is False
    assert "name;$(bad).png" in command[-1]


def test_identify_subcommand_precedes_resource_limits(tmp_path: Path) -> None:
    engine = ImageMagickEngine("magick")
    version = subprocess.CompletedProcess(
        ["magick", "-version"],
        0,
        "Version: ImageMagick 7.1.1-47 Delegates: png jpeg lcms",
        "",
    )
    completed = subprocess.CompletedProcess(["magick"], 0, "{}", "")
    arguments = ["identify", "-quiet", "-format", "{}", str(tmp_path / "input.jpg")]

    with patch(
        "image_editor_plugin.engine.subprocess.run", side_effect=[version, completed]
    ) as run:
        engine.run(arguments)

    command = run.call_args_list[1].args[0]
    assert command[:2] == ["magick", "identify"]
    assert command[2:5] == ["-limit", "memory", "1GiB"]
    assert arguments[0] == "identify"
