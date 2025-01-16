import os
import subprocess
import logging
import jinja2
import shutil
import nbformat
import nbconvert
from nbconvert import LatexExporter
from nbconvert.preprocessors import TagRemovePreprocessor
from traitlets.config import Config
from pathlib import Path


class LaTeXConverter:
    """
    Manages LaTeX templates and PDF compilation processes.
    Handles template loading, rendering, and PDF generation with proper CJK support.
    """

    def __init__(self, template_dir=None):
        """
        Initialize LaTeX template manager.

        Args:
            template_dir (str, optional): Custom template directory path.
                                        Defaults to package's templates directory.
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
            
        self.template_loader = jinja2.FileSystemLoader(searchpath=template_dir)
        self.template_env = jinja2.Environment(
            loader=self.template_loader,
            block_start_string=r'\BLOCK{',
            block_end_string='}',
            variable_start_string=r'\VAR{',
            variable_end_string='}',
            comment_start_string=r'\#{',
            comment_end_string='}',
            line_statement_prefix='%%',
            line_comment_prefix='%#',
            trim_blocks=True,
            autoescape=False,
        )

    def render_template(self, template_name, **context):
        """
        Render a LaTeX template with given context.

        Args:
            template_name (str): Name of the template file
            **context: Template variables

        Returns:
            str: Rendered LaTeX content
        """
        template = self.template_env.get_template(template_name)
        return template.render(**context)

    def compile_pdf(self, tex_content, output_dir, output_name, clean_up=True):
        """
        Compile LaTeX content to PDF using xelatex.

        Args:
            tex_content (str): LaTeX content to compile
            output_dir (str): Directory for output files
            output_name (str): Name for output files (without extension)
            clean_up (bool): Whether to remove auxiliary files after compilation

        Returns:
            str: Path to generated PDF file or None if compilation failed
        """
        original_cwd = os.getcwd()
        try:
            os.makedirs(output_dir, exist_ok=True)
            os.chdir(output_dir)
            # Write LaTeX content to file
            tex_file = f"{output_name}.tex"
            with open(tex_file, 'w', encoding='utf-8') as f:
                f.write(tex_content)

            # Compile twice for TOC
            for i in range(2):
                result = subprocess.run(
                    ['xelatex', '-interaction=nonstopmode', '-halt-on-error', tex_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode != 0:
                    # Log only on error
                    logging.error(f"LaTeX compilation failed ({output_name} attempt {i+1}) with return code: {result.returncode}")
                    logging.error(f"{result.stderr.strip()}")
                    
                    # Keep log file for debugging if compilation fails
                    clean_up = False
                    continue

            pdf_path = os.path.join(output_dir, f"{output_name}.pdf")
            
            if os.path.exists(pdf_path):
                if clean_up:
                    self._clean_auxiliary_files(output_dir, output_name)
                return pdf_path
            else:
                logging.error(f"PDF file not generated at {pdf_path}")
                return None

        except Exception as e:
            logging.error(f"Error in PDF compilation: {e}")
            return None
            
        finally:
            os.chdir(original_cwd)

    def _clean_auxiliary_files(self, directory, basename):
        """
        Remove LaTeX auxiliary files.

        Args:
            directory (str): Directory containing the files
            basename (str): Base name of the files (without extension)
        """
        aux_extensions = ['.aux', '.log', '.toc', '.out', '.nav', '.snm']
        for ext in aux_extensions:
            aux_file = os.path.join(directory, basename + ext)
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
            except OSError as e:
                logging.error(f"Error removing auxiliary file {aux_file}: {e}")

class NotebookConverter:
    """
    Converts Jupyter Notebook files (.ipynb) to LaTeX format without re-executing cells.
    """

    def __init__(self, exclude_input=False, exclude_output=False, max_output_lines=64):
        """
        Initializes the NotebookConverter.

        Args:
            template_file (str, optional): Path to a custom LaTeX template file.
            exclude_input (bool, optional): Whether to exclude input cells from the output. Defaults to False.
            exclude_output (bool, optional): Whether to exclude output cells from the output. Defaults to False.
            max_output_lines (int, optional): The maximum number of lines for text-based outputs. Defaults to 64.
        """
        config = Config()
        config.LatexExporter.exclude_input = exclude_input
        config.LatexExporter.exclude_output = exclude_output
        config.LatexExporter.template_file = "notebook.tex.j2"
        config.LatexExporter.extra_template_paths = [os.path.join(os.path.dirname(__file__), 'templates')]
        self.exporter = LatexExporter(config=config)
        self.max_output_lines = max_output_lines

    def convert_notebook(self, ipynb_file, figures):
        """
        Convert a Jupyter notebook to a LaTeX file, ensuring figures are available.

        Parameters:
        - ipynb_file: str or Path, path to the input notebook file.
        - figures: list, list of figure files to ensure availability.

        Returns:
        - Path to the generated LaTeX file.
        """
        ipynb_file = Path(ipynb_file)
        base_name = ipynb_file.stem
        output_dir = ipynb_file.parent

        try:
            with open(ipynb_file, 'r') as f:
                notebook_content = nbformat.read(f, as_version=4)
                self._truncate_long_outputs(notebook_content)
                body, resources = self.exporter.from_notebook_node(notebook_content)

            figures_dir = output_dir / 'figures'
            figures_dir.mkdir(exist_ok=True)
            self._ensure_figures_available(ipynb_file.parent, output_dir, figures)

            if 'outputs' in resources:
                for filename, data in resources['outputs'].items():
                    with open(figures_dir / filename, 'wb') as f:
                        f.write(data)
                    body = body.replace(filename, f'figures/{filename}')

            latex_file = output_dir / f"{base_name}.tex"
            with open(latex_file, 'w') as f:
                f.write(body)

            return latex_file

        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def _ensure_figures_available(self, assignment_dir, output_dir, figures):
        """Ensure that all required figures are present in the output directory."""
        for fig in figures:
            source_path = os.path.join(assignment_dir, fig)
            target_path = os.path.join(output_dir, fig)
            if not os.path.exists(target_path):
                if os.path.exists(source_path):
                    shutil.copy2(source_path, target_path)
                else:
                    logging.warning(f"Figure '{fig}' not found in assignment directory.")

    def _truncate_long_outputs(self, nb):
        """
        Truncate long outputs in a notebook, handling different output types.
        Keeps the first max_output_lines/2 and the last max_output_lines/2 lines.

        Args:
            nb (nbformat.NotebookNode): The notebook object.
        """
        for cell in nb.cells:
            if cell.cell_type == 'code' and 'outputs' in cell:
                for output in cell.outputs:
                    if output.output_type == 'stream':
                        if 'text' in output:
                            lines = output.text.splitlines()
                            if len(lines) > self.max_output_lines:
                                half_lines = self.max_output_lines // 2
                                output.text = '\n'.join(
                                    lines[:half_lines] +
                                    ['... (output truncated) ...'] +
                                    lines[-half_lines:]
                                )
                    elif output.output_type in ('execute_result', 'display_data'):
                        if 'text/plain' in output.data:
                            lines = output.data['text/plain'].splitlines()
                            if len(lines) > self.max_output_lines:
                                half_lines = self.max_output_lines // 2
                                output.data['text/plain'] = '\n'.join(
                                    lines[:half_lines] +
                                    ['... (output truncated) ...'] +
                                    lines[-half_lines:]
                                )
                    elif output.output_type == 'error':
                        # You might want to handle errors differently
                        pass

# if __name__ == "__main__":
#     # notebook_file = "/home/fred/lectures/PRML/eval/2024-Autumn/PRML-HW24A02/22012100021/logistic-regression.ipynb"
#     notebook_file = "/home/fred/lectures/PRML/eval/2024-Autumn/PRML-HW24A02/22009200070/linear-regression.ipynb"
#     converter = NotebookConverter(exclude_input=False, exclude_output=False)
#     converter.convert_notebook(notebook_file, [])
