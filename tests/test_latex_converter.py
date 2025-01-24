import os
import shutil
import pytest
from pathlib import Path
from xdufacool.converters import LaTeXConverter

# Test fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path

@pytest.fixture
def latex_converter(temp_dir):
    """Create a LaTeXConverter instance with test templates."""
    # Create test template directory
    template_dir = temp_dir / "templates"
    template_dir.mkdir()
    
    # Create a test template
    test_template = template_dir / "test.tex"
    test_template.write_text(r"""
\documentclass{article}
\begin{document}
\VAR{content}
\end{document}
""")
    
    return LaTeXConverter(str(template_dir))

# Test cases
def test_init_default_template_dir():
    """Test initialization with default template directory."""
    converter = LaTeXConverter()
    assert converter.template_loader is not None
    assert converter.template_env is not None

def test_init_custom_template_dir(temp_dir):
    """Test initialization with custom template directory."""
    template_dir = temp_dir / "custom_templates"
    template_dir.mkdir()
    converter = LaTeXConverter(str(template_dir))
    assert str(template_dir) in converter.template_loader.searchpath

def test_render_template(latex_converter):
    """Test template rendering."""
    content = "Hello, World!"
    rendered = latex_converter.render_template(
        "test.tex",
        content=content
    )
    assert content in rendered
    assert r"\documentclass{article}" in rendered

def test_render_template_missing(latex_converter):
    """Test rendering with non-existent template."""
    with pytest.raises(Exception):  # Should raise a template not found error
        latex_converter.render_template("nonexistent.tex")

@pytest.mark.skipif(not shutil.which('xelatex'), reason="XeLaTeX not installed")
def test_compile_pdf(latex_converter, temp_dir):
    """Test PDF compilation."""
    # Prepare test content
    tex_content = r"""
\documentclass{article}
\begin{document}
Test content
\end{document}
"""
    
    # Compile PDF
    output_name = "test_output"
    pdf_path = latex_converter.compile_pdf(
        tex_content,
        str(temp_dir),
        output_name
    )
    
    # Check results
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert pdf_path.endswith(".pdf")

@pytest.mark.skipif(not shutil.which('xelatex'), reason="XeLaTeX not installed")
def test_compile_pdf_with_errors(latex_converter, temp_dir):
    """Test PDF compilation with LaTeX errors."""
    # Invalid LaTeX content
    tex_content = r"""
\documentclass{article}
\begin{document}
\invalidcommand
\end{document}
"""
    
    # Attempt compilation
    pdf_path = latex_converter.compile_pdf(
        tex_content,
        str(temp_dir),
        "error_test"
    )
    
    # Should return None on compilation error
    assert pdf_path is None

def test_end_to_end(latex_converter, temp_dir):
    """Test complete template rendering and PDF compilation process."""
    # Skip if XeLaTeX is not installed
    if not shutil.which('xelatex'):
        pytest.skip("XeLaTeX not installed")
    
    # Render template
    rendered = latex_converter.render_template(
        "test.tex",
        content="End-to-end test content"
    )
    
    # Compile to PDF
    pdf_path = latex_converter.compile_pdf(
        rendered,
        str(temp_dir),
        "end_to_end_test"
    )
    
    # Verify results
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert not any(
        os.path.exists(os.path.join(temp_dir, f"end_to_end_test{ext}"))
        for ext in ['.aux', '.log', '.toc']
    ) 

def test_article_template(temp_dir):
    """Test the article template rendering and compilation with CJK support."""
    if not shutil.which('xelatex'):
        pytest.skip("XeLaTeX not installed")

    # Create LaTeXConverter with default template directory
    converter = LaTeXConverter()

    # Test data with Chinese content
    context = {
        "title": "测试文档",
        "author": "张三",
        "date": "2024年2月",
        "abstract": "这是摘要部分。",
        "content": "这是一个测试文档的内容。\n\n这是第二段。",
        "toc": False,  # Make sure all optional parameters are defined
        "bibliography": None
    }

    # Render template and save for inspection
    rendered = converter.render_template("article.tex.j2", **context)
    tex_file = os.path.join(temp_dir, "debug_test_article.tex")
    with open(tex_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"\nDebug: LaTeX file written to {tex_file}")

    # Compile to PDF
    pdf_path = converter.compile_pdf(
        rendered,
        str(temp_dir),
        "test_article",
        clean_up=True
    )

    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert pdf_path == os.path.join(temp_dir, "test_article.pdf")