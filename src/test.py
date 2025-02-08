import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import QThread, pyqtSignal


class RcloneThread(QThread):
    output_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        """Run the rclone configuration using subprocess."""
        try:
            # Command to configure OneDrive
            command = [
                "rclone",
                "config",
                "create",
                "onedrive",
                "onedrive",
            ]

            # Execute the command
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if process.returncode == 0:
                self.output_signal.emit("OneDrive configuration created successfully:\n" + process.stdout)
            else:
                self.output_signal.emit(f"Configuration failed:\n{process.stderr}")
        except Exception as e:
            self.output_signal.emit(f"Unexpected Error: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OneDrive Login")
        self.setGeometry(200, 200, 400, 200)

        # UI Components
        self.label = QLabel("Click the button to configure OneDrive", self)
        self.label.setWordWrap(True)

        self.button = QPushButton("OneDrive", self)
        self.button.clicked.connect(self.start_rclone)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_rclone(self):
        """Start the rclone configuration process in a separate thread."""
        self.label.setText("Starting OneDrive configuration...")
        self.button.setEnabled(False)

        self.thread = RcloneThread()
        self.thread.output_signal.connect(self.update_label)
        self.thread.finished.connect(self.thread_finished)
        self.thread.start()

    def update_label(self, message):
        """Update the label with messages from the rclone thread."""
        self.label.setText(message)

    def thread_finished(self):
        """Re-enable the button when the thread finishes."""
        self.button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
