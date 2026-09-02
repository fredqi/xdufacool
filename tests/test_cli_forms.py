import argparse
import sys

import pytest

from xdufacool import cli
from xdufacool import form_automa


def test_cli_forms_auto_merge_dispatch(monkeypatch, tmp_path):
    captured = {}

    def fake_handler(args):
        captured["args"] = args

    monkeypatch.setattr(form_automa, "run_form_auto_merge", fake_handler)
    monkeypatch.setattr(cli, "setup_logging", lambda level: None)
    monkeypatch.setattr(cli, "load_dotenv", lambda dotenv_path=None: None)

    data_file = tmp_path / "data.xlsx"
    data_file.write_text("", encoding="utf-8")
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    output_dir = tmp_path / "output"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "xdufacool",
            "forms",
            "auto-merge",
            "--sheets",
            "日常考核",
            "指导教师评分表",
            "--data-file",
            str(data_file),
            "--template-dir",
            str(template_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    cli.main()

    args = captured["args"]
    assert args.subcommand == "forms"
    assert args.forms_subcommand == "auto-merge"
    assert args.sheets == ["日常考核", "指导教师评分表"]
    assert args.data_file == str(data_file)
    assert args.template_dir == str(template_dir)
    assert args.output_dir == str(output_dir)


def test_run_form_auto_merge_validates_data_file(tmp_path):
    args = argparse.Namespace(
        sheets=["日常考核"],
        data_file=str(tmp_path / "missing.xlsx"),
        template_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
    )

    with pytest.raises(SystemExit, match="data file not found"):
        form_automa.run_form_auto_merge(args)


def test_run_form_auto_merge_calls_form_auto_merge(monkeypatch, tmp_path):
    called = {}

    def fake_form_auto_merge(**kwargs):
        called.update(kwargs)

    data_file = tmp_path / "data.xlsx"
    data_file.write_text("", encoding="utf-8")
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    output_dir = tmp_path / "output"

    args = argparse.Namespace(
        sheets=["日常考核"],
        data_file=str(data_file),
        template_dir=str(template_dir),
        output_dir=str(output_dir),
    )

    monkeypatch.setattr(form_automa, "form_auto_merge", fake_form_auto_merge)

    form_automa.run_form_auto_merge(args)

    assert called["sheets"] == ["日常考核"]
    assert called["data_file"] == str(data_file)
    assert called["template_dir"] == str(template_dir)
    assert called["output_dir"] == str(output_dir)
