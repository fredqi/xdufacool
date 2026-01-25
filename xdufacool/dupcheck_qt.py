"""
PySide6 GUI for editing dupcheck duplicate reports.
Allows human-in-the-loop confirmation of files to delete.
"""
import sys
import yaml
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QScrollArea, QFileDialog, QCheckBox,
        QMessageBox, QGroupBox, QFrame, QProgressDialog
    )
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QFont
except ImportError:
    print("Error: PySide6 is not installed. Please install it with: pip install PySide6")
    sys.exit(1)

from xdufacool.dupcheck import load_report, find_duplicates

class ScanThread(QThread):
    finished = Signal(object)
    
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        
    def run(self):
        # Disable CLI progress bars since we don't have a way to pipe them to GUI easily yet
        duplicates = find_duplicates(self.folder, show_progress=False)
        self.finished.emit(duplicates)


class DuplicateGroupWidget(QGroupBox):
    """Widget to display and manage a single group of duplicate files."""
    
    def __init__(self, checksum, files, parent=None):
        super().__init__(parent)
        self.checksum = checksum
        self.files = files  # List of dicts: {'path': '...', 'delete': bool}
        self.checkboxes = []

        self.setTitle(f"Group: {checksum[:12]}...")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Toolbar for group actions
        btn_layout = QHBoxLayout()
        
        keep_first_btn = QPushButton("Keep First")
        keep_first_btn.clicked.connect(self.keep_first)
        
        keep_all_btn = QPushButton("Keep All")
        keep_all_btn.clicked.connect(self.keep_all)

        btn_layout.addWidget(keep_first_btn)
        btn_layout.addWidget(keep_all_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # File list
        for i, file_info in enumerate(self.files):
            path = file_info.get('path', 'Unknown')
            is_deleted = file_info.get('delete', False)
            
            cb = QCheckBox(path)
            cb.setChecked(is_deleted)
            # Initial style update based on state
            self.update_checkbox_style(cb, is_deleted)
            
            # Store index to update data later
            cb.stateChanged.connect(lambda state, idx=i, checkbox=cb: self.on_checkbox_change(idx, state, checkbox))
            
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        self.setLayout(layout)

    def update_checkbox_style(self, checkbox, is_checked):
        if is_checked:
            checkbox.setStyleSheet("color: red; text-decoration: line-through;")
        else:
            checkbox.setStyleSheet("color: black; text-decoration: none;")

    def on_checkbox_change(self, index, state, checkbox):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.files[index]['delete'] = is_checked
        self.update_checkbox_style(checkbox, is_checked)

    def keep_first(self):
        for i, cb in enumerate(self.checkboxes):
            should_delete = (i != 0)
            cb.setChecked(should_delete)
            # Style update is handled by signal connection

    def keep_all(self):
        for i, cb in enumerate(self.checkboxes):
            cb.setChecked(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Review Duplicates")
        self.resize(800, 600)
        
        self.current_report_path = None
        self.report_data = {}
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top Bar
        top_layout = QHBoxLayout()
        
        scan_btn = QPushButton("Scan Directory")
        scan_btn.clicked.connect(self.scan_directory)

        self.path_label = QLabel("No report loaded")
        load_btn = QPushButton("Open Report")
        load_btn.clicked.connect(self.load_report_dialog)
        
        save_btn = QPushButton("Save Report")
        save_btn.clicked.connect(self.save_report)
        
        clean_btn = QPushButton("Delete Selected")
        clean_btn.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold;")
        clean_btn.clicked.connect(self.execute_clean)

        top_layout.addWidget(scan_btn)
        top_layout.addWidget(load_btn)
        top_layout.addWidget(save_btn)
        top_layout.addWidget(clean_btn)
        top_layout.addWidget(self.path_label)
        top_layout.addStretch()
        
        main_layout.addLayout(top_layout)

        # Scroll Area for duplicates
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.scroll_content)
        main_layout.addWidget(scroll)

        # Status Bar
        self.statusBar().showMessage("Ready")

    def scan_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if not folder:
            return

        self.statusBar().showMessage(f"Scanning {folder}...")
        self.progress = QProgressDialog("Scanning for duplicates...", "Cancel", 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        self.scan_thread = ScanThread(folder)
        self.scan_thread.finished.connect(lambda dups: self.on_scan_finished(dups, folder))
        
        # Keep reference to avoid garbage collection
        # Note: If we wanted to support cancellation, we'd need to modify dupcheck logic to check a flag
        self.scan_thread.start()

    def on_scan_finished(self, duplicates, folder):
        self.progress.close()
        
        if not duplicates:
             QMessageBox.information(self, "Scan Complete", "No duplicates found.")
             self.report_data = {'base_dir': str(folder), 'duplicates': {}}
             self.render_duplicates()
             return

        # Convert list of tuples to report format
        from xdufacool.dupcheck import generate_report
        # We can simulate the report structure in memory
        from collections import defaultdict
        
        grouped = defaultdict(list)
        for checksum, rel_path in duplicates:
            grouped[checksum].append({
                'path': rel_path,
                'delete': False
            })
            
        self.report_data = {
            'base_dir': str(folder),
            'duplicates': dict(grouped)
        }
        
        self.current_report_path = str(Path(folder) / "duplicates.yaml")
        self.path_label.setText(f"Scanned: {folder}")
        self.render_duplicates()
        self.statusBar().showMessage(f"Found {len(grouped)} duplicate groups.")

    def execute_clean(self):
        if not self.report_data or 'duplicates' not in self.report_data:
            return

        count = 0
        base_dir = Path(self.report_data.get('base_dir', '.'))
        
        to_delete = []
        for checksum, files in self.report_data['duplicates'].items():
            for file_info in files:
                if file_info.get('delete'):
                    full_path = base_dir / file_info['path']
                    to_delete.append(full_path)

        if not to_delete:
            QMessageBox.information(self, "Clean", "No files marked for deletion.")
            return

        confirm = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to PERMANENTLY delete {len(to_delete)} files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm != QMessageBox.Yes:
            return

        deleted_count = 0
        errors = []
        
        for file_path in to_delete:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                errors.append(f"{file_path.name}: {e}")

        msg = f"Deleted {deleted_count} files."
        if errors:
            msg += f"\n\nErrors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += "\n..."
        
        QMessageBox.information(self, "Clean Complete", msg)
        
        # Remove deleted files from report data and refresh UI
        # Basic approach: just reload what's left or clear them visually
        # Ideally, we should re-scan or update data structure carefully.
        # For now, let's just save the report with deleted files marked (or removed?)
        # Better: remove entry from UI.
        self.remove_deleted_from_data()
        self.render_duplicates()

    def remove_deleted_from_data(self):
        """Remove files marked as deleted from the internal data structure."""
        new_dups = {}
        for checksum, files in self.report_data['duplicates'].items():
            remaining = [f for f in files if not f.get('delete')]
            # If only 1 file remains, it's no longer a duplicate group
            if len(remaining) > 1:
                new_dups[checksum] = remaining
        
        self.report_data['duplicates'] = new_dups

    def load_report_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Report File", "", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if file_name:
            self.load_report_file(file_name)

    def load_report_file(self, file_path):
        path = Path(file_path)
        if not path.exists():
            QMessageBox.critical(self, "Error", f"File not found: {path}")
            return

        try:
            self.report_data = load_report(path)
            self.current_report_path = file_path
            self.path_label.setText(file_path)
            self.render_duplicates()
            self.statusBar().showMessage(f"Loaded {len(self.report_data.get('duplicates', {}))} duplicate groups.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading report: {e}")

    def render_duplicates(self):
        # Clear existing items
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.report_data or 'duplicates' not in self.report_data:
            self.scroll_layout.addWidget(QLabel("No duplicates found in report."))
            return

        dups = self.report_data.get('duplicates', {})
        for i, (checksum, files) in enumerate(dups.items()):
            group_widget = DuplicateGroupWidget(checksum, files)
            
            # Alternating background colors
            bg_color = "#ffffff" if i % 2 == 0 else "#e6e6fa"  # White and Lavender
            
            # Apply stylesheet to QGroupBox. 
            # Note: We need to set flat to True or handle Paint events for some styles, 
            # but stylesheet usually works for background if configured right.
            # Using QGroupBox selector prevents internal widgets from inheriting the color if they have their own styles.
            group_widget.setStyleSheet(
                f"QGroupBox {{ background-color: {bg_color}; font-weight: bold; }}"
                f"QGroupBox::title {{ background-color: transparent; }}" 
            )
            
            self.scroll_layout.addWidget(group_widget)

    def save_report(self):
        if not self.current_report_path:
            QMessageBox.warning(self, "Warning", "No report loaded.")
            return

        try:
            with open(self.current_report_path, 'w') as f:
                yaml.dump(self.report_data, f, default_flow_style=False)
            QMessageBox.information(self, "Success", f"Report saved to {self.current_report_path}")
            self.statusBar().showMessage("Report saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving report: {e}")


def main():
    app = QApplication(sys.argv)
    # Change font size for better readability
    font = app.font()
    font.setPointSize(14)
    app.setFont(font)
    # Create and show main window
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
