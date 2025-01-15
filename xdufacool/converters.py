import os
import subprocess
import logging
import jinja2
import shutil
import nbformat
from nbconvert import LatexExporter
from nbconvert.preprocessors import TagRemovePreprocessor
from traitlets.config import Config
# # from xdufacool.utils import truncate_long_outputs, ensure_figures_available
# from jupyter_core.paths import jupyter_config_dir, jupyter_data_dir

# def ensure_figures_available(assignment_dir, output_dir, figures):
#     """Ensure that all required figures are present in the output directory."""
#     for fig in figures:
#         source_path = os.path.join(assignment_dir, fig)
#         target_path = os.path.join(output_dir, fig)
#         if not os.path.exists(target_path):
#             if os.path.exists(source_path):
#                 shutil.copy2(source_path, target_path)
#             else:
#                 logging.warning(f"Figure '{fig}' not found in assignment directory.")

# def truncate_long_outputs(nb, max_output_lines=64):
#     """
#     Truncate long outputs in a notebook, handling different output types.

#     Args:
#         nb (nbformat.NotebookNode): The notebook object.
#         max_lines_per_output (int): The maximum number of lines for text-based outputs.
#     """
#     for cell in nb.cells:
#         if cell.cell_type == 'code' and 'outputs' in cell:
#             for output in cell.outputs:
#                 if output.output_type == 'stream':
#                     if 'text' in output:
#                         lines = output.text.splitlines()
#                         if len(lines) > max_output_lines:
#                             output.text = '\n'.join(lines[:max_output_lines] + ['... (output truncated) ...'])
#                 elif output.output_type in ('execute_result', 'display_data'):
#                     if 'text/plain' in output.data:
#                         lines = output.data['text/plain'].splitlines()
#                         if len(lines) > max_output_lines:
#                             output.data['text/plain'] = '\n'.join(lines[:max_output_lines] + ['... (output truncated) ...'])
#                 elif output.output_type == 'error':
#                     pass

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

    def __init__(self, template_file=None, exclude_input=False, exclude_output=False, max_output_lines=64):
        """
        Initializes the NotebookConverter.

        Args:
            template_file (str, optional): Path to a custom LaTeX template file.
            exclude_input (bool, optional): Whether to exclude input cells from the output. Defaults to False.
            exclude_output (bool, optional): Whether to exclude output cells from the output. Defaults to False.
            max_output_lines (int, optional): The maximum number of lines for text-based outputs. Defaults to 64.
        """

        # Configure nbconvert
        config = Config()

        # Configure TagRemovePreprocessor to remove cells with specific tags
        config.TagRemovePreprocessor.remove_cell_tags = ("remove_cell",)
        config.TagRemovePreprocessor.remove_all_outputs_tags = ("remove_output",)
        config.TagRemovePreprocessor.remove_input_tags = ("remove_input",)
        config.TagRemovePreprocessor.enabled = True

        # Configure the LaTeX exporter
        self.exporter = LatexExporter(config=config)
        self.exporter.exclude_input = exclude_input
        self.exporter.exclude_output = exclude_output

        if template_file:
            self.exporter.template_file = template_file
        
        self.max_output_lines = max_output_lines

    def convert_notebook(self, ipynb_file, output_dir, figures):
        """
        Converts a Jupyter Notebook file to LaTeX format.

        Args:
            ipynb_file (str): Path to the input .ipynb file.
            output_dir (str): Directory to save the output LaTeX file and figures.
            figures (list): List of required figure filenames.

        Returns:
            str: Path to the generated LaTeX file, or None if an error occurred.
        """
        try:
            # Read the notebook
            with open(ipynb_file, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)

            # Truncate long outputs for better readability
            self._truncate_long_outputs(nb)

            # Convert to LaTeX
            (body, resources) = self.exporter.from_notebook_node(nb)

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Ensure required figures are available
            self._ensure_figures_available(os.path.dirname(ipynb_file), output_dir, figures)

            # Create figures directory if it doesn't exist
            figures_dir = os.path.join(output_dir, 'figures')
            os.makedirs(figures_dir, exist_ok=True)

            # Save figures if they exist in resources
            if 'outputs' in resources:
                for filename, data in resources['outputs'].items():
                    figure_path = os.path.join(figures_dir, filename)
                    with open(figure_path, 'wb') as f:
                        f.write(data)

                    # Update the figure path in LaTeX content to use relative path
                    body = body.replace(filename, os.path.join('figures', filename))

            # Save LaTeX file
            tex_file = ipynb_file.replace('.ipynb', '.tex')
            tex_file_base = os.path.basename(tex_file)
            tex_file_path = os.path.join(output_dir, tex_file_base)
            with open(tex_file_path, 'w', encoding='utf-8') as f:
                f.write(body)
            print(tex_file_path)
            return tex_file_path

        except Exception as e:
            logging.error(f"Error converting {ipynb_file}: {str(e)}")
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
