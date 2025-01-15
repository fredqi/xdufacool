import os
import logging
import subprocess
from pathlib import Path
import jinja2

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
                logging.warning(f"Could not remove {aux_file}: {e}") 