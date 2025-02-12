import sys
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import vlc
from mainwin import Ui_MainWindow
import os

class SliderSyncThread(QThread):
    """Thread to sync media position with slider during dragging."""
    sync_signal = pyqtSignal(int)

    def __init__(self, media_player, slider, parent=None):
        super().__init__(parent)
        self.media_player = media_player
        self.slider = slider
        self.running = False

    def run(self):
        """Sync slider position with media playback."""
        self.running = True
        while self.running:
            if self.media_player:
                # Get current media time and update the slider
                current_time = self.media_player.get_time() / 1000  # Convert to seconds
                self.sync_signal.emit(int(current_time))
            self.msleep(50)  # Update every 50 ms

    def stop(self):
        """Stop the sync thread."""
        self.running = False
        self.wait()


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
                self.errorHandler(e)
            self.msleep(self.interval)

    def errorHandler(self, errorMsg):
        error = QMessageBox(self)

        error.setWindowTitle("An Error Occurred.")
        error.setText(errorMsg)
        error.setIcon(QMessageBox.Icon.Critical)

        # Add custom buttons
        quit_button = QPushButton("Quit")
        ignore_button = QPushButton("Ignore")

        # Add the custom buttons to the QMessageBox
        error.addButton(quit_button, QMessageBox.ButtonRole.RejectRole)
        error.addButton(ignore_button, QMessageBox.ButtonRole.ActionRole)

        # Execute the dialog
        errorDiag = error.exec()

        # Handle the button clicks
        if error.clickedButton() == quit_button:
            self.close()  # Close the application
        else:
            error.close()  # Close the dialog

    def stop(self):
        """Stop the thread gracefully."""
        self.running = False
        self.quit()
        self.wait()


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
            self.errorHandler(e)

    def errorHandler(self, errorMsg):
        error = QMessageBox(self)

        error.setWindowTitle("An Error Occurred.")
        error.setText(errorMsg)
        error.setIcon(QMessageBox.Icon.Critical)

        # Add custom buttons
        quit_button = QPushButton("Quit")
        ignore_button = QPushButton("Ignore")

        # Add the custom buttons to the QMessageBox
        error.addButton(quit_button, QMessageBox.ButtonRole.RejectRole)
        error.addButton(ignore_button, QMessageBox.ButtonRole.ActionRole)

        # Execute the dialog
        errorDiag = error.exec()

        # Handle the button clicks
        if error.clickedButton() == quit_button:
            self.close()  # Close the application
        else:
            error.close()  # Close the dialog

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

    def errorHandler(self, errorMsg):
        error = QMessageBox(self)

        error.setWindowTitle("An Error Occurred.")
        error.setText(errorMsg)
        error.setIcon(QMessageBox.Icon.Critical)

        # Add custom buttons
        quit_button = QPushButton("Quit")
        ignore_button = QPushButton("Ignore")

        # Add the custom buttons to the QMessageBox
        error.addButton(quit_button, QMessageBox.ButtonRole.RejectRole)
        error.addButton(ignore_button, QMessageBox.ButtonRole.ActionRole)

        # Execute the dialog
        errorDiag = error.exec()

        # Handle the button clicks
        if error.clickedButton() == quit_button:
            self.close()  # Close the application
        else:
            error.close()  # Close the dialog

    def run(self):
        """Load the file into VLC."""
        try:
            media = self.instance.media_new(self.file_name)
            self.media_player.set_media(media)
            self.file_loaded_signal.emit(self.file_name)
        except Exception as e:
            self.errorHandler(e)


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
            self.errorHandler(e)

    def errorHandler(self, errorMsg):
        error = QMessageBox(self)

        error.setWindowTitle("An Error Occurred.")
        error.setText(errorMsg)
        error.setIcon(QMessageBox.Icon.Critical)

        # Add custom buttons
        quit_button = QPushButton("Quit")
        ignore_button = QPushButton("Ignore")

        # Add the custom buttons to the QMessageBox
        error.addButton(quit_button, QMessageBox.ButtonRole.RejectRole)
        error.addButton(ignore_button, QMessageBox.ButtonRole.ActionRole)

        # Execute the dialog
        errorDiag = error.exec()

        # Handle the button clicks
        if error.clickedButton() == quit_button:
            self.close()  # Close the application
        else:
            error.close()  # Close the dialog


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
        self.ui.horizontalSlider.setDisabled(True)

        # Start the video thread right away
        self.video_thread.start()

        # Relations
        self.slider = self.ui.horizontalSlider

        # Install the event filter for the horizontal slider
        self.ui.horizontalSlider.installEventFilter(self)

        # Slider dragging state
        self.slider_dragging = False
        self.slider_sync_thread = None  # Thread for slider synchronization

        # Global Variables
        self.storedVolume = 0
        self.currentMediaLocation = None
        self.currentMediaLength = 0 # Length is in Milli Seconds

        # Start the playback time thread
        self.playback_time_thread = PlaybackTimeThread(self.media_player)
        self.playback_time_thread.playback_time_signal.connect(self.force_update)
        self.playback_time_thread.start()

        # Enable drag-and-drop for the stacked widget
        self.ui.stackedWidget.setAcceptDrops(True)

        # Connect VLC events
        # 1. When Media Ended.
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.on_video_end)


    # When the Video Ends
    def on_video_end(self, event):
        """Handle the event when the video ends."""
        if self.currentMediaLocation:
            self.replay_video()
        else:
            self.disablePlay()

    def replay_video(self):
        """Replay the current video."""
        if self.currentMediaLocation:
            self.load_media(self.currentMediaLocation)

    # Video Management
    def open_file(self):
        """Open a file dialog to choose a media file."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Media File")
        if file_name:
            self.load_media(file_name)
            self.currentMediaLocation = file_name

    def load_media(self, file_name):
        """Load the specified media file into the media player."""
        if file_name:
            # Start the file loading thread to load the media
            self.file_loader_thread = FileLoaderThread(file_name, self.media_player, self.instance)
            self.file_loader_thread.file_loaded_signal.connect(self.on_file_loaded)
            self.file_loader_thread.start()
            self.enablePlay()

    def playORpause(self):
        """Toggles play/pause state of the video."""
        if self.is_playing:
            self.pause_video()
            self.ui.play_btn.setIcon(QIcon("icons/ui_files/play.png"))
        else:
            self.play_video()
            self.ui.play_btn.setIcon(QIcon("icons/ui_files/pause.png"))
        self.is_playing = not self.is_playing

    def disablePlay(self):
        self.ui.play_btn.setIcon(QIcon("icons/ui_files/play.png"))
        self.ui.play_btn.setDisabled(True)
        self.ui.horizontalSlider.setDisabled(True)
        self.media_player.stop()

    def enablePlay(self):
        self.ui.play_btn.setEnabled(True)
        self.ui.horizontalSlider.setEnabled(True)
        self.ui.play_btn.setIcon(QIcon("icons/ui_files/pause.png"))

    def on_file_loaded(self, file_name):
        """Called once the media file is loaded."""
        self.media_player.set_hwnd(self.ui.widget_2.winId())
        self.ui.horizontalSlider.setValue(0)
        self.ui.horizontalSlider.setMaximum(0)
        self.ui.label_4.setText("00:00")
        self.ui.label_7.setText("00:00")
        self.play_video()


    def force_update(self, seconds):
        """Forces an update to the slider and labels after opening a file."""
        total_length = self.media_player.get_length() // 1000

        # Set The Media Time In Variable
        self.currentMediaLength = total_length * 1000

        current_time = seconds
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

    # Handling Dropping a video file
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag events to accept file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle the drop event to get the file and play it."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):  # Ensure it's a valid file
                self.load_media(file_path)
                self.currentMediaLocation = file_path
                break  # Handle only the first file for now
            else:
                event.ignore()

    # Slider Logic.

    # # Event Filter

    def eventFilter(self, obj, event):
        """Override eventFilter to handle mouse and scroll interaction with the slider."""
        if obj == self.ui.horizontalSlider:
            slider = self.ui.horizontalSlider

            # Handle mouse events
            if isinstance(event, QMouseEvent):
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

                        ##
                        if not self.slider_sync_thread:
                            self.slider_sync_thread = SliderSyncThread(self.media_player, slider)
                            self.slider_sync_thread.sync_signal.connect(self.update_slider_position)
                            self.slider_sync_thread.start()


                        ##

                        return True
                    else:
                        # Otherwise, jump to the clicked position on the slider
                        self.handle_slider_click(event)
                        self.slider_dragging = False
                        return True

                elif event.type() == QMouseEvent.Type.MouseButtonRelease:
                    self.slider_dragging = False

                    ##
                    # Stop the slider sync thread
                    if self.slider_sync_thread:
                        self.slider_sync_thread.stop()
                        self.slider_sync_thread = None

                    # Finalize the media time to the slider's current position
                    new_position = self.ui.horizontalSlider.value()
                    self.media_player.set_time(new_position * 1000)  # Convert to milliseconds
                    ##

                    return True

                elif event.type() == QMouseEvent.Type.MouseMove and self.slider_dragging:
                    # Handle dragging while mouse is pressed
                    self.handle_slider_drag(event)
                    return True

            # Handle scroll events
            elif isinstance(event, QWheelEvent):
                self.handle_slider_scroll(event)
                return True

        return super().eventFilter(obj, event)

    def update_slider_position(self, current_time):
        """Update the slider position based on the media time."""
        slider = self.ui.horizontalSlider
        # Update the slider's value to reflect the current media time
        if not self.slider_dragging:
            slider.setValue(int(current_time))

        # Update the label (label_4) to display the formatted time
        formatted_time = self.format_time(current_time)
        self.ui.label_4.setText(formatted_time)

    ## Slider Scroll
    # 1. Get Scroll
    def handle_slider_scroll(self, event):
        """Adjust media position based on scroll direction."""
        delta = event.angleDelta().y()  # Positive for up, negative for down
        if delta > 0:
            self.seek_media(10)  # Scroll up: Forward by 10 seconds
        elif delta < 0:
            self.seek_media(-10)  # Scroll down: Backward by 10 seconds

    # 2. Skip 'n' seconds
    def seek_media(self, seconds):
        """Adjust the media position by the given number of seconds."""
        if self.media_player:
            try:
                # Get the current position in milliseconds
                current_position = self.media_player.get_time()
                # Calculate the new position
                new_position = current_position + (seconds * 1000)  # Convert seconds to milliseconds
                # Ensure the new position is within valid bounds
                new_position = max(0, min(new_position, self.currentMediaLength))
                # Set the new position
                self.media_player.set_time(new_position)
            except Exception as e:
                self.errorHandler(e)

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
        drag_pos_x = event.position().x()
        drag_pos_y = event.position().y()
        slider_rect = slider.geometry()

        # Check vertical position of the cursor
        slider_center_y = slider_rect.center().y()  # Get the center y-coordinate of the slider
        if abs(drag_pos_y - slider_center_y) > 50:
            # Ignore if the mouse cursor is more than ±50px in the y-axis
            return

        # Calculate new slider value
        new_value = (
                (drag_pos_x / slider_rect.width()) * (slider.maximum() - slider.minimum())
                + slider.minimum()
        )

        # Check if the value is in range
        new_value = max(0, min(new_value, self.currentMediaLength))

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
        self.ui.rewind_btn.setIcon(QIcon("icons/ui_files/rewind.png"))
        self.ui.fastforward_btn.setIcon(QIcon("icons/ui_files/fast-forward.png"))
        self.ui.caption_btn.setIcon(QIcon("icons/ui_files/caption.png"))
        self.ui.expand_btn.setIcon(QIcon("icons/ui_files/expand.png"))
        self.ui.repeat_btn.setIcon(QIcon("icons/ui_files/repeat.png"))

    def errorHandler(self, errorMsg):
        error = QMessageBox(self)

        error.setWindowTitle("An Error Occurred.")
        error.setText(errorMsg)
        error.setIcon(QMessageBox.Icon.Critical)

        # Add custom buttons
        quit_button = QPushButton("Quit")
        ignore_button = QPushButton("Ignore")

        # Add the custom buttons to the QMessageBox
        error.addButton(quit_button, QMessageBox.ButtonRole.RejectRole)
        error.addButton(ignore_button, QMessageBox.ButtonRole.ActionRole)

        # Execute the dialog
        errorDiag = error.exec()

        # Handle the button clicks
        if error.clickedButton() == quit_button:
            self.close()  # Close the application
        else:
            error.close()  # Close the dialog

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
