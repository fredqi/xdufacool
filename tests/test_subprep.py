from pathlib import Path

from xdufacool.subprep import rewrite_figures


def test_rewrite_figures_keeps_figure_behavior(tmp_path: Path):
    current_file = tmp_path / "main.tex"
    current_file.write_text("", encoding="utf-8")

    (tmp_path / "plot.png").write_bytes(b"png")
    intermediate_dir = tmp_path / "inter"
    intermediate_dir.mkdir()

    content = (
        "\\begin{figure}\n"
        "\\centering\n"
        "\\includegraphics[width=0.8\\linewidth]{plot}\n"
        "\\caption{Demo}\n"
        "\\label{fig:demo}\n"
        "\\end{figure}\n"
    )

    rewritten = rewrite_figures(
        content,
        current_file=current_file,
        intermediate_dir=intermediate_dir,
        global_label_map={"fig:demo": "1"},
    )

    assert "\\includegraphics[width=0.8\\linewidth]{Fig1-plot.png}" in rewritten
    assert (intermediate_dir / "Fig1-plot.png").exists()


def test_rewrite_figures_processes_ieeebiography_images(tmp_path: Path):
    current_file = tmp_path / "main.tex"
    current_file.write_text("", encoding="utf-8")

    (tmp_path / "author_photo.jpg").write_bytes(b"jpg")
    intermediate_dir = tmp_path / "inter"
    intermediate_dir.mkdir()

    content = (
        "\\begin{IEEEbiography}[{\\includegraphics[width=1in,height=1.25in]{author_photo}}]{Author Name}\n"
        "Biography text.\n"
        "\\end{IEEEbiography}\n"
    )

    rewritten = rewrite_figures(
        content,
        current_file=current_file,
        intermediate_dir=intermediate_dir,
        global_label_map={},
    )

    assert "\\includegraphics[width=1in,height=1.25in]{author_photo.jpg}" in rewritten
    assert (intermediate_dir / "author_photo.jpg").exists()
