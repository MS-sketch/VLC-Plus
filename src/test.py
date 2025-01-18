import sys
import msal
import requests
import os
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import vlc
import webbrowser

class OneDriveApp(QWidget):
    def __init__(self):
        super().__init__()

        self.client_id = '015b9ac1-cf4f-436f-a649-613f5444f640'  # Replace with your actual client ID
        self.client_secret = '53136d52-c376-47c8-a596-6da62600bcdf'  # Optional, not needed for personal accounts
        self.authority = 'https://login.microsoftonline.com/common'  # Use 'common' for personal accounts
        self.redirect_uri = 'http://localhost:5000/callback'  # Redirect URI configured in Azure

        self.scope = ['Files.ReadWrite']
        self.access_token = None

        self.auth_app = msal.PublicClientApplication(self.client_id, authority=self.authority)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('OneDrive Login & Video Player')
        self.setWindowIcon(QIcon('app_icon.png'))

        self.layout = QVBoxLayout()

        self.login_button = QPushButton('Login to OneDrive', self)
        self.login_button.clicked.connect(self.login)
        self.layout.addWidget(self.login_button)

        self.play_button = QPushButton('Play Video', self)
        self.play_button.clicked.connect(self.play_video)
        self.layout.addWidget(self.play_button)

        self.label = QLabel("Please login to OneDrive first.", self)
        self.layout.addWidget(self.label)

        self.setLayout(self.layout)

    def login(self):
        # Redirect the user to Microsoft login page
        auth_url = self.auth_app.get_authorization_request_url(self.scope, redirect_uri=self.redirect_uri)
        self.label.setText(f"Go to: {auth_url}")

        # Automatically open the Microsoft login page in the browser
        webbrowser.open(auth_url)

        # Wait for the callback URL to capture the authorization code
        self.get_access_token()

    def get_access_token(self):
        # Mocking a simple local web server to listen for the callback
        # You could use Flask here for a more robust implementation
        import http.server
        import socketserver

        class MyHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                # This part handles the callback and retrieves the code
                if self.path.startswith('/callback'):
                    query = self.path.split('?')[1]
                    code = query.split('=')[1]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Login successful! You can close this window.')
                    self.server.code = code

        # Start a simple HTTP server to capture the redirect
        with socketserver.TCPServer(('127.0.0.1', 5000), MyHandler) as httpd:
            print("Server started at http://127.0.0.1:5000")
            httpd.handle_request()

        # Once the callback is received, exchange the code for a token
        code = httpd.code
        if code:
            result = self.auth_app.acquire_token_by_authorization_code(
                code,
                scopes=self.scope,
                redirect_uri=self.redirect_uri
            )

            if 'access_token' in result:
                self.access_token = result['access_token']
                self.label.setText("Login successful! You can now select a video.")
            else:
                self.label.setText("Login failed. Please try again.")
                print(result)

    def play_video(self):
        if not self.access_token:
            self.label.setText("You need to login first.")
            return

        # Call OneDrive API to get video files
        video_file = self.select_video_from_onedrive()
        if video_file:
            self.play_local_video(video_file)

    def select_video_from_onedrive(self):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        api_url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'  # Get files from OneDrive
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            files = response.json().get('value', [])
            video_files = [f for f in files if f['name'].lower().endswith(('.mp4', '.avi', '.mov'))]
            if video_files:
                # Allow the user to choose a video file from the list
                video_file = QFileDialog.getOpenFileName(self, 'Select a video file', '', 'Video Files (*.mp4 *.avi *.mov)')
                return video_file[0]
            else:
                self.label.setText("No video files found on OneDrive.")
                return None
        else:
            self.label.setText(f"Error retrieving files: {response.status_code}")
            return None

    def play_local_video(self, video_file):
        # Initialize VLC player
        Instance = vlc.Instance()
        player = Instance.media_player_new()
        media = Instance.media_new(video_file)
        player.set_media(media)

        player.play()

        self.label.setText(f"Playing video: {os.path.basename(video_file)}")

        # Keep the app running until the video is finished
        while player.is_playing():
            pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OneDriveApp()
    window.show()
    sys.exit(app.exec())
