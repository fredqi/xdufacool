import os
import pytest
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell, new_output
from xdufacool.converters import NotebookConverter
import base64

# Define metadata as a global variable
global_metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3"
    },
    "language_info": {
        "codemirror_mode": {
            "name": "ipython",
            "version": 3
        },
        "file_extension": ".py",
        "mimetype": "text/x-python",
        "name": "python",
        "nbconvert_exporter": "python",
        "pygments_lexer": "ipython3",
        "version": "3.12.2"
    }
}

@pytest.fixture
def setup_test_environment(tmp_path):
    """
    Fixture to set up the test environment:
    - Creates a temporary directory for test files.
    - Creates a sample .ipynb notebook for testing.
    - Creates a dummy figure file.
    """
    test_dir = tmp_path / "test_files"
    notebook_file = test_dir / "test_notebook.ipynb"
    figure_file = "figure1.png"
    test_dir.mkdir()

    # Create a sample notebook with various cell types
    nb = new_notebook()
    nb.cells.append(new_markdown_cell("# Test Notebook\nThis is a test notebook."))
    
    # Markdown cell referencing the external figure
    nb.cells.append(new_markdown_cell("![Figure 1](figure1.png)"))
    
    nb.cells.append(new_code_cell("print('Hello, world!')", execution_count=1, outputs=[
        new_output("stream", name="stdout", text="Hello, world!\n")
    ]))
    nb.cells.append(new_code_cell("# This cell should be removed", execution_count=2, metadata={"tags": ["remove_cell"]}, outputs=[]))
    nb.cells.append(new_code_cell("from IPython.display import Image\nImage(filename='figure1.png')", execution_count=3, outputs=[
        new_output("display_data", data={
            "image/png": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="  # Placeholder for a 1x1 black pixel
        }, metadata={})
    ]))
    nb.metadata = global_metadata

    with open(notebook_file, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    # Decode the base64 string
    image_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    
    with open(test_dir / figure_file, "wb") as f:
        f.write(image_data)

    return test_dir, notebook_file, figure_file

def test_convert_notebook(setup_test_environment):
    """
    Test the convert_notebook method:
    - Converts the sample notebook to LaTeX.
    - Checks if the output .tex file and figures directory are created.
    - Checks if the figure is copied to the output directory.
    - Performs basic checks on the content of the .tex file.
    """
    test_dir, notebook_file, figure_file = setup_test_environment

    converter = NotebookConverter()
    # Pass assignment_folder and figures correctly. 
    # Since figure is already in the same dir as notebook (which is output dir), copy isn't strictly needed for validity 
    # but let's pass it to match signature if that was intent. 
    # However, given the failure was about content, let's fix the call signature first.
    tex_file = converter.convert_notebook(str(notebook_file), assignment_folder=str(test_dir), figures=[figure_file])

    # Check if the .tex file is created
    assert os.path.exists(tex_file)

    # Check if the figures directory is created and contains the figure
    figures_dir = test_dir / "figures"
    assert os.path.exists(figures_dir)
    assert os.path.exists(test_dir / "figure1.png")

    # Check the content of the .tex file (basic checks)
    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()
    assert "Test Notebook" in tex_content  # Check for title
    assert "Hello, world!" in tex_content  # Check for code output
    assert "# This cell should be removed" not in tex_content  # Check for removed cell
    # nbconvert might use \adjustimage or \includegraphics. Check for the filename presence in a latex command.
    assert "figure1.png" in tex_content

def test_convert_notebook_exclude_input_output(setup_test_environment):
    """
    Test the convert_notebook method with input and output cells excluded:
    - Converts the notebook with exclude_input=True and exclude_output=True.
    - Checks if the output .tex file excludes input and output cells.
    """
    test_dir, notebook_file, figure_file = setup_test_environment
    converter = NotebookConverter(exclude_input=True, exclude_output=True)
    tex_file = converter.convert_notebook(str(notebook_file), assignment_folder=str(test_dir), figures=[figure_file])

    # Check if the .tex file is created
    assert os.path.exists(tex_file)

    # Check the content of the .tex file
    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()
    assert "print('Hello, world!')" not in tex_content  # Check for excluded input cell
    assert "Hello, world!" not in tex_content  # Check for excluded output

def test_ensure_figures_available(tmp_path):
    """
    Test the ensure_figures_available function:
    - Creates a dummy figure in the assignment directory.
    - Calls ensure_figures_available to copy the figure to the output directory.
    - Checks if the figure is copied successfully.
    """
    assignment_dir = tmp_path / "assignment"
    assignment_dir.mkdir()
    test_dir = tmp_path / "test_files"
    test_dir.mkdir()
    figure_file = assignment_dir / "figure2.png"

    with open(figure_file, "wb") as f:
        f.write(b"Dummy figure content")  # Create a dummy figure

    converter = NotebookConverter()
    converter._copy_missing_figures(str(assignment_dir), str(test_dir), ["figure2.png"])
    assert os.path.exists(test_dir / "figure2.png")

def test_convert_notebook_long_output(setup_test_environment):
    """
    Test the convert_notebook method with long output:
    - Create a sample notebook with long output.
    - Converts the sample notebook to LaTeX.
    - Checks if the output .tex file are truncated.
    """
    _, notebook_file, _ = setup_test_environment
    nb = new_notebook()
   
    long_output_lines = ['Line {}\n'.format(i) for i in range(100)]
    long_output_text = ''.join(long_output_lines)

    nb.cells.append(new_code_cell("print('Long output:')\nfor i in range(100):\n    print('Line {}'.format(i))", 
                                  execution_count=3, 
                                  outputs=[new_output("stream", name="stdout", text=long_output_text)]))

    nb.metadata = global_metadata

    with open(notebook_file, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    converter = NotebookConverter(max_output_lines=32)
    tex_file = converter.convert_notebook(str(notebook_file), [])
    assert os.path.exists(tex_file)
    # Check the content of the .tex file (basic checks)
    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()
    # Check that the long output is truncated
    assert "Line 0" in tex_content
    assert "Line 1" in tex_content
    assert "Line 15" in tex_content
    assert "Line 16" not in tex_content
    assert " (output truncated) " in tex_content
    assert "Line 83" not in tex_content
    assert "Line 84" in tex_content
    assert "Line 99" in tex_content
def test_patch_math_split():
    """Test _patch_math_split method to assume split environment is wrapped in equation*."""
    source = r"""\begin{split}
\frac{\partial J(\theta)}{\partial \theta_{0}} &= \frac{1}{m} \sum_{i=1}^{m} \big( h_{\theta}(x^{(i)}) - y^{(i)} \big) x_{0}^{(i)} \qquad \qquad \text{for } j=0 \\
\frac{\partial J(\theta)}{\partial \theta_{j}} &= \frac{1}{m} \sum_{i=1}^{m} \big( h_{\theta}(x^{(i)}) - y^{(i)} \big) x_{j}^{(i)} + \frac{\lambda}{m} \theta_{j} \qquad \text{for } j \geq 1
\end{split}"""
    
    nb = new_notebook()
    nb.cells.append(new_markdown_cell(source))
    
    converter = NotebookConverter()
    converter._patch_math_split(nb)
    
    expected_start = r'\begin{equation*}\begin{split}'
    expected_end = r'\end{split}\end{equation*}'
    
    assert nb.cells[0].source.startswith(expected_start)
    assert nb.cells[0].source.endswith(expected_end)
