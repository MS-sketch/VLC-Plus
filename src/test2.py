from PyQt6.QtCore import QThread, pyqtSignal


class PlaybackTimeThread(QThread):
    """Thread to fetch the current playback time periodically."""
    playback_time_signal = pyqtSignal(int)  # Signal to emit the playback time in seconds

    def __init__(self, media_player, interval=1000):
        """
        Initialize the thread.
        :param media_player: VLC media player instance
        :param interval: Time interval (in ms) to fetch the playback time
        """
        super().__init__()
        self.media_player = media_player
        self.interval = interval
        self.running = False

    def run(self):
        """Fetch the current playback time in a loop."""
        self.running = True
        while self.running:
            try:
                # Get the current playback time in milliseconds and convert to seconds
                current_time = self.media_player.get_time() // 1000
                if current_time >= 0:
                    self.playback_time_signal.emit(current_time)  # Emit the playback time
            except Exception as e:
                print(f"Error in PlaybackTimeThread: {e}")
            self.msleep(self.interval)

    def stop(self):
        """Stop the thread gracefully."""
        self.running = False
        self.quit()
        self.wait()


# Example Usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    import vlc

    class MainApp(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("VLC Playback Time Example")

            # Create a VLC instance and media player
            self.vlc_instance = vlc.Instance()
            self.media_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new("path/to/your/media/file.mp4")
            self.media_player.set_media(media)

            # Start playback
            self.media_player.play()

            # Create a label to display playback time
            self.time_label = QLabel("Playback Time: 0:00")
            layout = QVBoxLayout()
            layout.addWidget(self.time_label)
            self.setLayout(layout)

            # Start the playback time thread
            self.playback_time_thread = PlaybackTimeThread(self.media_player)
            self.playback_time_thread.playback_time_signal.connect(self.update_time_label)
            self.playback_time_thread.start()

        def update_time_label(self, seconds):
            """Update the label with the current playback time."""
            minutes, seconds = divmod(seconds, 60)
            self.time_label.setText(f"Playback Time: {minutes}:{seconds:02}")

        def closeEvent(self, event):
            """Clean up resources on close."""
            self.playback_time_thread.stop()
            self.media_player.stop()
            self.vlc_instance.release()
            event.accept()

    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
