import os
import subprocess
import logging
import jinja2
import shutil
import nbformat
from nbconvert import LatexExporter
from traitlets.config import Config
from pathlib import Path


class PDFCompiler:
    """
    Handles PDF compilation process using XeLaTeX with detailed error handling and configuration.
    """
    
    def __init__(self, compiler='xelatex', max_runs=2):
        """
        Initialize PDF compiler.

        Args:
            compiler (str): LaTeX compiler to use ('xelatex', 'pdflatex', etc.)
            max_runs (int): Maximum number of compilation runs for TOC/references
        """
        self.compiler = compiler
        self.max_runs = max_runs

    def compile(self, tex_file, output_dir, clean_up=True):
        """
        Compile LaTeX file to PDF.

        Args:
            tex_file (str): Path to .tex file
            output_dir (str): Directory for output files
            clean_up (bool): Whether to remove auxiliary files after compilation

        Returns:
            str: Path to generated PDF file or None if compilation failed
        """
        original_cwd = os.getcwd()
        try:
            os.makedirs(output_dir, exist_ok=True)
            os.chdir(output_dir)
            
            basename = Path(tex_file).stem
            success = True
            logging.debug(f"Current working directory: {original_cwd}=>{output_dir}")
            logging.debug(f"Compiling {basename} with {self.compiler}")

            # Compile multiple times for TOC/references
            for i in range(self.max_runs):
                result = subprocess.run(
                    [self.compiler, '-interaction=nonstopmode', '-halt-on-error', tex_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode != 0:
                    success = False
                    logging.error(f"LaTeX compilation failed ({basename}, attempt {i+1})")
                    logging.error(f"Command output:\n{result.stdout}")
                    # logging.error(f"Command error:\n{result.stderr}")
                    clean_up = False
                    break

            pdf_path = os.path.join(output_dir, f"{basename}.pdf")
            
            if success and os.path.exists(pdf_path):
                if clean_up:
                    self._clean_auxiliary_files(output_dir, basename)
                return pdf_path
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
        aux_extensions = ['.aux', '.log', '.toc', '.out', '.nav', '.snm', '.vrb']
        for ext in aux_extensions:
            aux_file = os.path.join(directory, basename + ext)
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
            except OSError as e:
                logging.error(f"Error removing auxiliary file {aux_file}: {e}")

class LaTeXConverter:
    """
    Manages LaTeX templates and rendering processes.
    """

    def __init__(self, template_dir=None):
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
        self.compiler = PDFCompiler('lualatex')

    def render_template(self, template_name, **context):
        """
        Render a LaTeX template with given context.

        Args:
            template_name (str): Name of the template file
            **context: Template variables

        Returns:
            str: Rendered LaTeX content
        """
        if 'language' not in context:
            context['language'] = 'zh'
            
        template = self.template_env.get_template(template_name)
        return template.render(**context)

    def compile_pdf(self, tex_content, output_dir, output_name, clean_up=True):
        """
        Render and compile LaTeX content to PDF.

        Args:
            tex_content (str): LaTeX content to compile
            output_dir (str): Directory for output files
            output_name (str): Name for output files (without extension)
            clean_up (bool): Whether to remove auxiliary files after compilation

        Returns:
            str: Path to generated PDF file or None if compilation failed
        """
        os.makedirs(output_dir, exist_ok=True)
        tex_file = os.path.join(output_dir, f"{output_name}.tex")
        
        # Write LaTeX content to file
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)

        return self.compiler.compile(tex_file, output_dir, clean_up)

class EmailTemplateRenderer:
    """
    Renders email templates using Jinja2.
    """
    
    def __init__(self, template_dir=None):
        """
        Initialize email template renderer.
        
        Args:
            template_dir (str, optional): Directory containing templates.
                                         If None, uses default templates directory.
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
            
        self.template_loader = jinja2.FileSystemLoader(searchpath=template_dir)
        self.template_env = jinja2.Environment(
            loader=self.template_loader,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
    
    def render_template(self, template_name, **context):
        """
        Render an email template with given context.
        
        Args:
            template_name (str): Name of the template file
            **context: Template variables
            
        Returns:
            str: Rendered email content
        """
        if 'language' not in context:
            context['language'] = 'zh'
            
        template = self.template_env.get_template(template_name)
        return template.render(**context)

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

    def convert_notebook(self, ipynb_file, assignment_folder=None, figures=[], metadata={}):
        """
        Convert a Jupyter notebook to a LaTeX file, ensuring figures are available.

        Parameters:
        - ipynb_file: str or Path, path to the input notebook file.
        - figures: list, list of figure files to ensure availability.

        Returns:
        - Path to the generated LaTeX file.
        """
        ipynb_file = Path(ipynb_file)
        output_dir = ipynb_file.parent        

        try:
            with open(ipynb_file, 'r') as f:
                notebook_content = nbformat.read(f, as_version=4)
                if hasattr(notebook_content, 'metadata'):
                    notebook_content.metadata.update(metadata)
                self._truncate_long_outputs(notebook_content)
                self._patch_math_split(notebook_content)
                body, resources = self.exporter.from_notebook_node(notebook_content)
            if assignment_folder and figures:
                self._copy_missing_figures(assignment_folder, output_dir, figures)

            if 'outputs' in resources:
                figures_dir = output_dir / 'figures'
                figures_dir.mkdir(exist_ok=True)
                for filename, data in resources['outputs'].items():
                    with open(figures_dir / filename, 'wb') as f:
                        f.write(data)
                    body = body.replace(filename, f'figures/{filename}')

            latex_file = output_dir / f"{ipynb_file.stem}.tex"
            with open(latex_file, 'w') as f:
                f.write(body)
            return latex_file

        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def _copy_missing_figures(self, assignment_dir, output_dir, figures):
        """Ensure that all required figures are present in the output directory."""
        for fig in figures:
            source_path = Path(assignment_dir) / fig
            target_path = Path(output_dir) / fig
            if not target_path.exists():
                logging.debug(f"    Copying figure {fig} to {output_dir}")
                if source_path.exists():
                    shutil.copy2(source_path, target_path)
                else:
                    logging.warning(f"  ! Figure '{fig}' not found in {assignment_dir}.")

    def _truncate_long_outputs(self, nb):
        """
        Truncate long outputs in a notebook, handling different output types.
        Keeps the first max_output_lines/2 and the last max_output_lines/2 lines.

        Args:
            nb (nbformat.NotebookNode): The notebook object.
        """
        def truncate_text(text):
            """Helper function to truncate text content."""
            lines = text.splitlines()
            if len(lines) > self.max_output_lines:
                half_lines = self.max_output_lines // 2
                return '\n'.join(
                    lines[:half_lines] +
                    ['... (output truncated) ...'] +
                    lines[-half_lines:]
                )
            return text

        for cell in nb.cells:
            if cell.cell_type == 'code' and 'outputs' in cell:
                for output in cell.outputs:
                    if output.output_type == 'stream' and 'text' in output:
                        output.text = truncate_text(output.text)
                    elif output.output_type in ('execute_result', 'display_data'):
                        if 'text/plain' in output.data:
                            output.data['text/plain'] = truncate_text(output.data['text/plain'])
                    elif output.output_type == 'error':
                        pass

    def _patch_math_split(self, nb):
        """
        Patches 'split' environments in Markdown cells to be enclosed in display math mode.

        This function iterates through all Markdown cells in the notebook and replaces
        '\\begin{split}' with '$$\\begin{split}' and '\\end{split}' with '\\end{split}$$'.

        Args:
            nb (nbformat.NotebookNode): The notebook object.
        """
        for cell in nb.cells:
            if cell.cell_type == 'markdown':
                cell.source = cell.source.replace(r'\begin{split}', r'$$\begin{split}')
                cell.source = cell.source.replace(r'\end{split}', r'\end{split}$$')

def docx_to_pdf(docx_filepath, pdf_filepath):
    """Converts a DOCX file to PDF."""
    pass

def doc_to_pdf(doc_filepath, pdf_filepath):
    """Converts a DOC file to PDF."""
    pass

def rar_to_zip(rar_filepath, zip_filepath):
    """Converts a RAR file to ZIP."""
    pass

def sevenzip_to_zip(sevenzip_filepath, zip_filepath):
    """Converts a 7z file to ZIP."""
    pass
