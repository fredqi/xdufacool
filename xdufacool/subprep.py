"""
Helper script to prepare LaTeX papers for submission to publishers like IEEE, Elsevier, Springer.
Extends arxiv-latex-cleaner functionality by adding:
1. Figure flattening and renaming based on Figure numbers.
2. Compilation validation.
3. Magic comments for TeX engines.
4. Submission archive creation.
"""
import os
import re
import shutil
import zipfile
import subprocess
import logging
import argparse
import yaml
from pathlib import Path
from typing import Dict, Optional, List

from xdufacool.converters import PDFCompiler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("submission_helper")

def check_dependencies():
    """Check if necessary tools are installed."""
    if shutil.which('arxiv_latex_cleaner') is None:
        logger.warning("arxiv-latex-cleaner is not found in PATH. Ensure it is installed via 'pip install arxiv-latex-cleaner'.")
    if shutil.which('pdflatex') is None:
        logger.warning("pdflatex is not found in PATH. Compilation validation will likely fail.")

class FigureScanner:
    """Scans TeX source to map figure labels to sequential numbers."""
    def __init__(self):
        self.mapping = {}
        self.counter = 0
        self.seen = set()

    def scan(self, root_file: Path) -> Dict[str, str]:
        self._parse_file(root_file)
        return self.mapping

    def _scan_content_for_labels(self, content: str, current_fig_num: int, base_path: Path):
        token_re = re.compile(r'(\\label\{(?P<lbl>.*?)\})|(\\(?:input|include)\{(?P<path>.*?)\})')
        for match in token_re.finditer(content):
            if match.group('lbl'):
                self.mapping[match.group('lbl')] = str(current_fig_num)
            elif match.group('path'):
                self._process_included_file(match.group('path'), base_path, current_fig_num)

    def _process_included_file(self, rel_path: str, base_path: Path, current_fig_num: int):
        sub = base_path / rel_path.strip()
        if not sub.exists() and not sub.suffix: sub = sub.with_suffix('.tex')
        if sub.exists():
            try:
                sub_content = sub.read_text(encoding='utf-8', errors='ignore')
                self._scan_content_for_labels(sub_content, current_fig_num, sub.parent)
            except Exception as e:
                logger.warning(f"Could not read included file {sub}: {e}")

    def _parse_file(self, file_path: Path):
        file_path = file_path.resolve()
        if file_path in self.seen or not file_path.exists(): return
        self.seen.add(file_path)
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        structure_re = re.compile(
            r'\\(?:input|include)\{(?P<path>.*?)\}|'
            r'\\begin\{figure\*?\}(?P<fig_body>.*?)\\end\{figure\*?\}',
            re.DOTALL
        )
        
        pos = 0
        while True:
            match = structure_re.search(content, pos)
            if not match: break
            
            if match.group('path'):
                rel = match.group('path').strip()
                sub = file_path.parent / rel
                if not sub.exists() and not sub.suffix: sub = sub.with_suffix('.tex')
                self._parse_file(sub)
            elif match.group('fig_body'):
                self.counter += 1
                self._scan_content_for_labels(match.group('fig_body'), self.counter, file_path.parent)
            
            pos = match.end()

def get_figure_number_map_from_source(root_file: Path) -> Dict[str, str]:
    """Wrapper for FigureScanner."""
    return FigureScanner().scan(root_file)

def find_image_file(base_path: Path, filename: str) -> Optional[Path]:
    """
    Finds an image file given a base path and a filename (potentially without extension).
    """
    if (base_path / filename).exists():
        return base_path / filename
    
    # Try common extensions
    for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.eps', '.tif', '.tiff']:
        p = base_path / (filename + ext)
        if p.exists():
            return p
    return None

def is_main_tex(file_path: Path) -> bool:
    """Check if the tex file contains a document environment."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        return r'\begin{document}' in content
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return False

def rewrite_bibliography(content: str, current_file: Path, intermediate_dir: Path, is_main: bool) -> str:
    """Rewrites bibliography includes and copies .bib/.bbl files."""
    def bib_repl(match):
        bib_refs = match.group(1).split(',')
        new_refs = []
        for ref in bib_refs:
            ref = ref.strip()
            # find .bib file
            bib_file = find_image_file(current_file.parent, ref)
            if not bib_file and not ref.endswith('.bib'):
                 bib_file = find_image_file(current_file.parent, ref + '.bib')
            
            if bib_file:
                dest_bib = intermediate_dir / bib_file.name
                if not dest_bib.exists():
                    shutil.copy2(bib_file, dest_bib)
                new_refs.append(bib_file.stem)
            else:
                 new_refs.append(ref)
        return f"\\bibliography{{{','.join(new_refs)}}}"

    content = re.sub(r'\\bibliography\{(.*?)\}', bib_repl, content)
    content = re.sub(r'\\addbibresource\{(.*?)\}', bib_repl, content)

    if is_main:
         bbl_file = current_file.with_suffix('.bbl')
         if bbl_file.exists():
             shutil.copy2(bbl_file, intermediate_dir / bbl_file.name)
    return content

def rewrite_inputs(content: str, current_file: Path, processing_queue: list) -> str:
    """Rewrites input commands and adds dependencies to queue."""
    def input_repl(match):
        inc_path_str = match.group(1).strip()
        target = current_file.parent / inc_path_str
        if not target.exists() and not target.suffix:
            target = target.with_suffix('.tex')
        
        if target.exists() and target.is_file():
            processing_queue.append(target)
            return f"\\input{{{target.name}}}"
        return match.group(0)
        
    content = re.sub(r'\\input\{(.*?)\}', input_repl, content)
    content = re.sub(r'\\include\{(.*?)\}', input_repl, content)
    return content

def rewrite_figures(content: str, current_file: Path, intermediate_dir: Path, global_label_map: Dict[str, str]) -> str:
    """Rewrites figure environments: updates options, renames images, copies images."""
    figure_pattern = re.compile(r'(\\begin\{figure\*?\}.*?\\end\{figure\*?\})', re.DOTALL)
    
    def figure_block_repl(match):
        full_block = match.group(1)
        
        label_match = re.search(r'\\label\{(.*?)\}', full_block)
        fig_num = None
        if label_match:
            fig_num = global_label_map.get(label_match.group(1))
        
        img_pattern = re.compile(r'\\includegraphics(?:\[(.*?)\])?\{(.*?)\}')
        
        def img_replacer(img_m):
            original_options = img_m.group(1)
            original_path_str = img_m.group(2).strip()
            
            img_path = find_image_file(current_file.parent, original_path_str)
            
            if not img_path:
                logger.warning(f"Could not find image {original_path_str} in {current_file.name}")
                return img_m.group(0)
            
            if fig_num:
                new_filename = f"Fig{fig_num}-{img_path.stem}{img_path.suffix}"
            else:
                new_filename = img_path.name
            
            dest_path = intermediate_dir / new_filename
            
            if not dest_path.exists():
                 try:
                    shutil.copy2(img_path, dest_path)
                 except Exception as e:
                    logger.error(f"Failed to copy {img_path}: {e}")

            opts_str = f"[{original_options}]" if original_options is not None else ""
            return f"\\includegraphics{opts_str}{{{new_filename}}}"

        return img_pattern.sub(img_replacer, full_block)

    return figure_pattern.sub(figure_block_repl, content)

def cleanup_tex_content(content: str) -> str:
    """
    Cleans up TeX content:
    1. Ensures magic comment is present at the top.
    2. Removes excessive blank lines (often left by comment removal).
    """
    magic_comment = "% !TeX program = pdflatex"
    lines = content.splitlines()
    if lines and lines[0].strip().startswith("% !TeX"):
        lines = lines[1:]
    content = '\n'.join(lines)
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return f"{magic_comment}\n{content.strip()}\n"

def validate_compilation(work_dir: Path, main_tex_file: str) -> bool:
    """Runs pdflatex to validate."""
    logger.info(f"Validating compilation for {main_tex_file}...")
    compiler = PDFCompiler(compiler='latexmk')
    pdf_path = compiler.compile(main_tex_file, str(work_dir), clean_up=False)
    
    if pdf_path:
        logger.info(f"Compilation successful: {main_tex_file}")
        return True
    else:
        logger.error(f"Compilation failed for {main_tex_file}.")
        return False

def create_zip_archive(source_dir: Path, output_filename: str):
    """Zips the directory."""
    output_path = Path(output_filename)
    if output_path.suffix != '.zip':
        output_path = output_path.with_suffix('.zip')
        
    logger.info(f"Creating archive: {output_path}")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                if file_path.suffix in ['.log', '.aux', '.out', '.spl', '.synctex.gz']:
                    continue
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
    
    logger.info(f"Archive created: {output_path}")

def setup_intermediate_dir(input_path: Path) -> Path:
    intermediate_dir = input_path.parent / (input_path.name + "_inter")
    if intermediate_dir.exists():
        shutil.rmtree(intermediate_dir)
    intermediate_dir.mkdir(parents=True)
    logger.info(f"Processing project into intermediate directory: {intermediate_dir}")
    return intermediate_dir

def get_target_files(input_path: Path, tex_filenames: List[str]) -> List[Path]:
    target_files = []
    for filename in tex_filenames:
        orig_file = input_path / filename
        if not orig_file.exists():
            logger.warning(f"Specified tex file not found: {orig_file}")
            continue
        if not is_main_tex(orig_file):
            logger.warning(f"Skipping {filename}: Does not appear to contain \\begin{{document}}")
            continue
        target_files.append(orig_file)
    return target_files

def process_file_queue(target_orig_files: List[Path], input_path: Path, intermediate_dir: Path):
    processing_queue = list(target_orig_files) 
    processed_files = set()
    
    # Pre-load label maps for main files
    global_label_map = {}
    for main_file in target_orig_files:
        logger.info(f"Scanning {main_file.name} for figure labels...")
        global_label_map.update(get_figure_number_map_from_source(main_file))

    while processing_queue:
        current_file = processing_queue.pop(0)
        
        try:
            rel_path = current_file.relative_to(input_path)
        except ValueError:
            logger.warning(f"File {current_file} is outside input folder {input_path}. Skipping.")
            continue
            
        if rel_path in processed_files:
            continue
        processed_files.add(rel_path)
        
        try:
            content = current_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read {current_file}: {e}")
            continue

        is_main = current_file in target_orig_files
        content = rewrite_bibliography(content, current_file, intermediate_dir, is_main)
        content = rewrite_inputs(content, current_file, processing_queue)
        content = rewrite_figures(content, current_file, intermediate_dir, global_label_map)
        
        dest_tex = intermediate_dir / current_file.name
        dest_tex.write_text(content, encoding='utf-8')

def run_cleaner(intermediate_dir: Path) -> Path:
    logger.info("Running arxiv-latex-cleaner on intermediate directory...")
    cleaner_cmd_args = [str(intermediate_dir), "--keep_bib"]
    cmd = ["arxiv_latex_cleaner"] + cleaner_cmd_args
    subprocess.run(cmd, check=True)
    cleaned_dir = intermediate_dir.parent / (intermediate_dir.name + "_arXiv")
    return cleaned_dir

def post_process_cleaned_dir(cleaned_dir: Path,
                             intermediate_dir: Path,
                             main_tex_names: List[str]):
    for main_name in main_tex_names:
        # Cleanup and Add magic comment
        tex_name = Path(main_name).name
        cleaned_tex = cleaned_dir / tex_name
        if cleaned_tex.exists():
            content = cleaned_tex.read_text(encoding='utf-8')
            content = cleanup_tex_content(content)
            cleaned_tex.write_text(content, encoding='utf-8')
            logger.info(f"Cleaned up and added magic comment to {tex_name}")
            
        # Restore .bbl files           
        bbl_name = Path(main_name).with_suffix('.bbl').name
        src_bbl = intermediate_dir / bbl_name
        dst_bbl = cleaned_dir / bbl_name
        if src_bbl.exists():
            shutil.copy2(src_bbl, dst_bbl)
            logger.info(f"Restored {bbl_name} to cleaned directory.")
        # Remove .spl files
        spl_name = Path(main_name).with_suffix('.spl').name
        dst_spl = cleaned_dir / spl_name
        if dst_spl.exists():
            dst_spl.unlink()
            logger.info(f"Removed {spl_name} from cleaned directory.")

def main():
    parser = argparse.ArgumentParser(description="Clean and prepare LaTeX project for submission.")
    parser.add_argument("input_folder", type=str, help="Path to the original LaTeX folder")
    parser.add_argument("--tex_files", nargs='+', required=True, help="List of main .tex files to process (space separated)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_folder).resolve()
    if not input_path.exists():
        logger.error(f"Input folder does not exist: {input_path}")
        return

    check_dependencies()

    intermediate_dir = setup_intermediate_dir(input_path)
    
    target_files = get_target_files(input_path, args.tex_files)
    if not target_files:
        logger.error("No valid main tex files found to process.")
        return

    process_file_queue(target_files, input_path, intermediate_dir)
    
    processed_main_tex_names = [f.name for f in target_files]

    for tex_name in processed_main_tex_names:
        if not validate_compilation(intermediate_dir, tex_name):
            logger.warning(f"Validation failed for {tex_name}. Proceeding anyway...")

    cleaned_dir = run_cleaner(intermediate_dir)
    post_process_cleaned_dir(cleaned_dir, intermediate_dir, processed_main_tex_names)

    final_output_dir = input_path.parent / (input_path.name + "_submission")
    if final_output_dir.exists():
        shutil.rmtree(final_output_dir)
    
    shutil.move(str(cleaned_dir), str(final_output_dir))
    # add_magic_comment(intermediate_dir / main_name)
    
    if intermediate_dir.exists():
        shutil.rmtree(intermediate_dir)

    create_zip_archive(final_output_dir, str(input_path) + ".zip")
    
    logger.info(f"Done! Cleaned submission is in {final_output_dir}")