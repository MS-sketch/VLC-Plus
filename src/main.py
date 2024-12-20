import sys
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QIcon, QMouseEvent
import vlc
from mainwin import Ui_MainWindow


class VideoPlayerThread(QThread):
    """Handle video playback and information retrieval in a background thread."""
    update_time_signal = pyqtSignal(int)  # Signal to update current playback time
    update_length_signal = pyqtSignal(int)  # Signal to update total length

    def __init__(self, media_player):
        super().__init__()
        self.media_player = media_player
        self.running = False

    def run(self):
        """Main thread loop to periodically fetch playback info."""
        self.running = True
        try:
            while self.running:
                # Fetch current playback time (in seconds)
                current_time = self.media_player.get_time() // 1000
                if current_time >= 0:
                    self.update_time_signal.emit(current_time)

                # Fetch total length (in seconds)
                total_length = self.media_player.get_length() // 1000
                if total_length > 0:
                    self.update_length_signal.emit(total_length)

                self.msleep(1000)  # Update once per second for reduced CPU usage
        except Exception as e:
            print(f"Error in VideoPlayerThread: {e}")

    def stop(self):
        """Gracefully stop the thread."""
        self.running = False
        self.quit()
        self.wait(500)  # Wait for thread cleanup


class FileLoaderThread(QThread):
    """Handle media loading in a separate thread."""
    file_loaded_signal = pyqtSignal(str)

    def __init__(self, file_name, media_player, instance):
        super().__init__()
        self.file_name = file_name
        self.media_player = media_player
        self.instance = instance

    def run(self):
        """Load the file into VLC."""
        try:
            media = self.instance.media_new(self.file_name)
            self.media_player.set_media(media)
            self.file_loaded_signal.emit(self.file_name)
        except Exception as e:
            print(f"Error in FileLoaderThread: {e}")


class CleanupThread(QThread):
    """Handles cleanup tasks in the background when closing the app."""
    def __init__(self, media_player, instance):
        super().__init__()
        self.media_player = media_player
        self.instance = instance

    def run(self):
        """Cleanup VLC and other resources in the background."""
        try:
            # Stop the media player
            self.media_player.stop()
            # Release the VLC instance
            self.instance.release()
        except Exception as e:
            print(f"Error in CleanupThread: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize the UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.instance = vlc.Instance('--avcodec-hw=any')  # Enable hardware acceleration
        self.media_player = self.instance.media_player_new()

        # Video playback thread
        self.video_thread = VideoPlayerThread(self.media_player)
        self.video_thread.update_time_signal.connect(self.update_time)
        self.video_thread.update_length_signal.connect(self.update_total_length)

        # File loading thread
        self.file_loader_thread = None

        # Connect buttons
        self.ui.previous_btn.clicked.connect(self.open_file)
        self.ui.play_btn.clicked.connect(self.playORpause)
        self.ui.sound_btn.clicked.connect(self.clickedSoundbtn)

        # Connect sliders
        self.ui.horizontalSlider_2.valueChanged.connect(self.update_volume)

        # Set initial volume
        self.ui.horizontalSlider_2.setValue(75)
        self.media_player.audio_set_volume(75)

        # Playback state
        self.is_playing = True

        # Set icons
        self.setIcons()

        # Disable buttons initially
        self.ui.play_btn.setDisabled(True)

        # Start the video thread right away
        self.video_thread.start()

        # Relations
        self.slider = self.ui.horizontalSlider

        # Install the event filter for the horizontal slider
        self.ui.horizontalSlider.installEventFilter(self)

        # Slider dragging state
        self.slider_dragging = False

        # Global Variables
        self.storedVolume = 0

        # Connect VLC events
        # 1. When Media Ended.
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.on_video_end)

    def on_video_end(self, event):
        """Restart the video when it ends."""
        print("Video ended. Restarting...")
        # self.media_player.stop()  # Stop the current playback
        self.media_player.set_time(0)  # Reset playback position to the beginning
        self.media_player.play()  # Restart the video

    def open_file(self):
        """Open a file dialog to choose a media file."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Media File")
        if file_name:
            # Start the file loading thread to load the media
            self.file_loader_thread = FileLoaderThread(file_name, self.media_player, self.instance)
            self.file_loader_thread.file_loaded_signal.connect(self.on_file_loaded)
            self.file_loader_thread.start()
            self.ui.play_btn.setEnabled(True)
            self.ui.play_btn.setIcon(QIcon("icons/ui_files/pause.png"))

    def playORpause(self):
        """Toggles play/pause state of the video."""
        if self.is_playing:
            self.pause_video()
            self.ui.play_btn.setIcon(QIcon("icons/ui_files/play.png"))
        else:
            self.play_video()
            self.ui.play_btn.setIcon(QIcon("icons/ui_files/pause.png"))
        self.is_playing = not self.is_playing

    def on_file_loaded(self, file_name):
        """Called once the media file is loaded."""
        self.media_player.set_hwnd(self.ui.widget_2.winId())
        self.ui.horizontalSlider.setValue(0)
        self.ui.horizontalSlider.setMaximum(0)
        self.ui.label_4.setText("00:00")
        self.ui.label_7.setText("00:00")
        self.play_video()
        QTimer.singleShot(1000, self.force_update)

    def force_update(self):
        """Forces an update to the slider and labels after opening a file."""
        total_length = self.media_player.get_length() // 1000
        current_time = self.media_player.get_time() // 1000
        if total_length > 0:
            self.update_total_length(total_length)
        if current_time >= 0:
            self.update_time(current_time)

    def update_total_length(self, total_length):
        """Update the total length label and slider maximum."""
        self.ui.label_7.setText(self.format_time(total_length))
        self.ui.horizontalSlider.setMaximum(total_length)

    def update_time(self, current_time):
        """Update the current playback time label and slider."""
        if not self.slider_dragging and self.is_playing:
            self.ui.label_4.setText(self.format_time(current_time))
            self.ui.horizontalSlider.setValue(current_time)

    def play_video(self):
        """Play the video."""
        self.media_player.play()

    def pause_video(self):
        """Pause the video."""
        self.media_player.pause()

    # Slider Logic.

    # # Event Filter
    def eventFilter(self, obj, event):
        """Override eventFilter to handle mouse interaction with the slider."""
        if obj == self.ui.horizontalSlider:
            slider = self.ui.horizontalSlider

            # Create a QStyleOptionSlider object to get the handle geometry
            style_option = QStyleOptionSlider()
            slider.initStyleOption(style_option)
            handle_rect = slider.style().subControlRect(
                QStyle.ComplexControl.CC_Slider,
                style_option,
                QStyle.SubControl.SC_SliderHandle,
                slider
            )
            handle_center = handle_rect.center()
            handle_radius = 10  # Radius around the handle to detect

            if event.type() == QMouseEvent.Type.MouseButtonPress:
                mouse_pos = event.pos()

                # Check if the click is within the radius of the slider handle
                if (handle_center - QPoint(mouse_pos.x(), mouse_pos.y())).manhattanLength() <= handle_radius:
                    self.slider_dragging = True  # Register dragging
                    self.handle_slider_drag(event)  # Start drag
                    return True
                else:
                    # Otherwise, jump to the clicked position on the slider
                    self.handle_slider_click(event)
                    return True

            elif event.type() == QMouseEvent.Type.MouseButtonRelease:
                self.slider_dragging = False
                return True

            elif event.type() == QMouseEvent.Type.MouseMove and self.slider_dragging:
                # Handle dragging while mouse is pressed
                self.handle_slider_drag(event)
                return True

        return super().eventFilter(obj, event)

    # # Mouse Click Logic
    def handle_slider_click(self, event):
        """Handle a click on the slider area."""
        slider = self.ui.horizontalSlider

        # Get the position of the slider handle
        slider_handle_position = slider.sliderPosition()

        # Get the width of the slider handle
        handle_width = slider.style().pixelMetric(QStyle.PixelMetric.PM_SliderLength)

        # Calculate the pixel position of the slider handle
        slider_width = slider.width()
        slider_left = int(slider_handle_position * slider_width / (slider.maximum() - slider.minimum()))

        # Define the range of the handle
        handle_start = slider_left - (handle_width // 2)
        handle_end = slider_left + (handle_width // 2)

        # Check if the click is on the handle
        if handle_start <= event.pos().x() <= handle_end:
            self.slider_dragging = True
        else:
            # If the click is not on the handle, jump to the clicked position
            click_position = event.pos().x()
            new_value = int(click_position * (slider.maximum() - slider.minimum()) / slider_width)
            slider.setValue(new_value)
            self.media_player.set_time(new_value * 1000)

    # # Drag Logic
    def handle_slider_drag(self, event):
        """Handle dragging of the slider handle."""
        slider = self.ui.horizontalSlider
        drag_pos = event.position().x()
        slider_rect = slider.geometry()

        # Calculate new slider value
        new_value = (
            (drag_pos / slider_rect.width()) * (slider.maximum() - slider.minimum())
            + slider.minimum()
        )
        slider.setValue(int(new_value))
        self.media_player.set_time(int(new_value) * 1000)

    # Volume Logic.
    # 1. Slider
    def update_volume(self):
        """Update the volume based on the slider value."""
        volume = self.ui.horizontalSlider_2.value()

        if 50 > volume > 0:
            self.ui.sound_btn.setIcon(QIcon("icons/ui_files/low-volume.png"))
            self.ui.sound_btn.setIconSize(QSize(20, 20))

        elif volume == 0:
            self.ui.sound_btn.setIcon(QIcon("icons/ui_files/silent.png"))
            self.ui.sound_btn.setIconSize(QSize(20, 20))

        else:
            self.ui.sound_btn.setIcon(QIcon("icons/ui_files/high-volume.png"))
            self.ui.sound_btn.setIconSize(QSize(20, 20))

        self.media_player.audio_set_volume(volume)

    # 2. Button
    def clickedSoundbtn(self):
        currentVolume = self.ui.horizontalSlider_2.value()

        # Store the current volume if it's greater than 0
        if currentVolume > 0:
            self.storedVolume = currentVolume

        if currentVolume > 0:
            # Mute the sound
            self.media_player.audio_set_volume(0)
            self.ui.horizontalSlider_2.setValue(0)
            self.ui.sound_btn.setIcon(QIcon("icons/ui_files/silent.png"))

        elif currentVolume == 0:
            # Unmute the sound and restore the stored volume
            if self.storedVolume > 0:
                self.media_player.audio_set_volume(self.storedVolume)
                self.ui.horizontalSlider_2.setValue(self.storedVolume)

                # Set the icon based on the restored volume
                if 0 < self.storedVolume < 50:
                    self.ui.sound_btn.setIcon(QIcon("icons/ui_files/low-volume.png"))
                else:
                    self.ui.sound_btn.setIcon(QIcon("icons/ui_files/high-volume.png"))

    def closeEvent(self, event):
        """Override closeEvent to ensure proper cleanup before closing."""
        print("Closing the application...")

        # Start a separate thread to handle cleanup
        self.cleanup_thread = CleanupThread(self.media_player, self.instance)
        self.cleanup_thread.start()

        # Close the window immediately
        event.accept()

    def setIcons(self):
        """Set icons for various buttons."""
        self.ui.sound_btn.setIcon(QIcon("icons/ui_files/high-volume.png"))
        self.ui.play_btn.setIcon(QIcon("icons/ui_files/play.png"))
        self.ui.previous_btn.setIcon(QIcon("icons/ui_files/back.png"))
        self.ui.stop_btn.setIcon(QIcon("icons/ui_files/stop-button.png"))
        self.ui.next_btn.setIcon(QIcon("icons/ui_files/next.png"))
        self.ui.home_btn.setIcon(QIcon("icons/ui_files/video.png"))
        self.ui.eq_btn.setIcon(QIcon("icons/ui_files/eq.png"))
        self.ui.logo.setIcon(QIcon("icons/ui_files/player.png"))
        self.ui.scan_btn_2.setIcon(QIcon("icons/Cloud_Providers/onedrive.ico"))
        self.ui.ai_btn_2.setIcon(QIcon("icons/ui_files/playlist.png"))
        self.ui.ai_btn_4.setIcon(QIcon("icons/ui_files/video-player.png"))
        self.ui.ai_btn_5.setIcon(QIcon("icons/ui_files/list-symbol-of-three-items-with-dots_icon-icons.com_72994.ico"))
        self.ui.onedrive.setIcon(QIcon("icons/Cloud_Providers/onedrive.ico"))
        self.ui.gdrive.setIcon(QIcon("icons/Cloud_Providers/gdrive.ico"))
        self.ui.box.setIcon(QIcon("icons/Cloud_Providers/box.ico"))
        self.ui.dropbox.setIcon(QIcon("icons/Cloud_Providers/dropbox.ico"))
        self.ui.youtube.setIcon(QIcon("icons/Cloud_Providers/yt.ico"))
        self.ui.localhost.setIcon(QIcon("icons/Cloud_Providers/976598-appliances-case-computer-computer-tower-desktop-pc_106551.ico"))
        self.ui.settings.setIcon(QIcon("icons/ui_files/settingscog_87317.ico"))
        self.ui.about.setIcon(QIcon("icons/ui_files/4213426-about-description-help-info-information-notification_115427.ico"))
        self.ui.help.setIcon(QIcon("icons/ui_files/Help_icon-icons.com_55891.ico"))

    @staticmethod
    def format_time(seconds):
        """Formats time in seconds to DD:HH:MM:SS or HH:MM:SS or MM:SS format."""
        if seconds >= 86400:  # 86400 seconds = 1 day
            days, remainder = divmod(seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days:02}:{hours:02}:{minutes:02}:{seconds:02}"
        elif seconds >= 3600:  # 3600 seconds = 1 hour
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        else:  # Less than 1 hour
            minutes, seconds = divmod(seconds, 60)
            return f"{minutes:02}:{seconds:02}"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
