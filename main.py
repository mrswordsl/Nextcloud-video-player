import sys, requests, logging, json, os, vlc
from datetime import datetime
from urllib.parse import quote
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTreeWidget, QTreeWidgetItem, QLineEdit,
                             QDialog, QDialogButtonBox, QTextEdit, QAction, QDockWidget, QMessageBox, QPushButton, QFileDialog,
                             QSlider,QHBoxLayout, QComboBox)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = 'config.json'



class BasicAuthWithUnicode(requests.auth.AuthBase):


    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __call__(self, r):
        import base64
        auth_str = f'{self.username}:{self.password}'
        b64_auth_str = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        r.headers['Authorization'] = f'Basic {b64_auth_str}'
        return r



class LoginDialog(QDialog):


    def __init__(self, parent=None, server_url='', username='', password=''):
        super().__init__(parent)
        self.setWindowTitle('Войти')

        self.server_url_input = QLineEdit(self)
        self.server_url_input.setPlaceholderText('URL сервера')
        self.server_url_input.setText(server_url)
        
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText('Имя пользователя')
        self.username_input.setText(username)
        
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText('Пароль')
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText(password)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_credentials)
        button_box.rejected.connect(self.reject)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel('URL сервера:'))
        layout.addWidget(self.server_url_input)
        layout.addWidget(QLabel('Имя пользователя:'))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel('Пароль:'))
        layout.addWidget(self.password_input)
        layout.addWidget(button_box)
        
        self.setLayout(layout)


    def get_credentials(self):
        server_url = self.server_url_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        return server_url, username, password


    def validate_credentials(self):
        server_url, username, password = self.get_credentials()
        if self.check_credentials(server_url, username, password):
            self.accept()
        else:
            QMessageBox.critical(self, "Вход не выполнен!", "Ошибка входа. Пожалуйста, проверьте URL-адрес вашего сервера, имя пользователя и пароль.")
            self.username_input.clear()
            self.password_input.clear()


    def check_credentials(self, server_url, username, password):
        full_url = server_url + "remote.php/dav/files/" + quote(username, safe='') + "/"
        try:
            response = requests.request("PROPFIND", full_url, auth=BasicAuthWithUnicode(username, password), headers={"Depth": "1"})
            logging.debug(f"Статус ответа: {response.status_code}")
            logging.debug(f"Содержимое ответа: {response.content}")
            return response.status_code == 207
        except requests.exceptions.RequestException as e:
            logging.error(f"Запрос не выполнен: {e}")
            return False



class VideoPlayerWindow(QMainWindow):
    closed = pyqtSignal()


    def __init__(self, vlc_instance, media, parent=None):
        super().__init__(parent)
        self.vlc_instance = vlc_instance
        self.media_player = self.vlc_instance.media_player_new()
        self.media_player.set_media(media)

        self.setWindowTitle("Видео проигрыватель")
        self.setGeometry(100, 100, 800, 600)

        self.video_frame = QWidget(self)
        self.setCentralWidget(self.video_frame)

        self.control_bar = QWidget(self)
        self.control_bar.setFixedHeight(50)
        self.play_button = QPushButton('Воспроизвести')
        self.pause_button = QPushButton('Пауза')
        self.stop_button = QPushButton('Остановить')
        self.slider = QSlider(Qt.Horizontal, self)
        self.volume_icon = QLabel('🔊', self)
        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.audio_track_box = QComboBox(self)
        self.time_label = QLabel('00:00 / 00:00', self)

        self.play_button.setFixedSize(90, 30)
        self.pause_button.setFixedSize(50, 30)
        self.stop_button.setFixedSize(80, 30)
        self.slider.setFixedHeight(30)
        self.volume_slider.setFixedHeight(30)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.media_player.audio_set_volume(50)

        self.control_layout = QHBoxLayout()
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.pause_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.time_label)
        self.control_layout.addWidget(self.slider)
        self.control_layout.addWidget(self.volume_icon)
        self.control_layout.addWidget(self.volume_slider)
        self.control_layout.addWidget(self.audio_track_box)
        self.control_bar.setLayout(self.control_layout)

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.video_frame)
        self.main_layout.addWidget(self.control_bar)

        central_widget = QWidget(self)
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        self.play_button.clicked.connect(self.play_video)
        self.pause_button.clicked.connect(self.pause_video)
        self.stop_button.clicked.connect(self.stop_video)
        self.slider.sliderMoved.connect(self.set_position)
        self.volume_slider.sliderMoved.connect(self.set_volume)
        self.audio_track_box.currentIndexChanged.connect(self.change_audio_track)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        if sys.platform.startswith('linux'):
            self.media_player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.media_player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.media_player.set_nsobject(int(self.video_frame.winId()))

        self.media_player.play()


    def play_video(self):
        self.media_player.play()


    def pause_video(self):
        self.media_player.pause()


    def stop_video(self):
        self.media_player.stop()


    def set_position(self, position):
        self.media_player.set_position(position / 100.0)


    def set_volume(self, volume):
        self.media_player.audio_set_volume(volume)


    def update_ui(self):
        media_pos = self.media_player.get_position()
        self.slider.setValue(int(media_pos * 100))
        self.update_audio_tracks()
        self.update_time_label()


    def update_audio_tracks(self):
        audio_tracks = self.media_player.audio_get_track_description()
        current_track = self.media_player.audio_get_track()
        self.audio_track_box.blockSignals(True)
        self.audio_track_box.clear()
        for track in audio_tracks:
            track_name = track[1].decode('utf-8') if isinstance(track[1], bytes) else track[1]
            self.audio_track_box.addItem(track_name, track[0])  # track is a tuple (id, name)
        index = self.audio_track_box.findData(current_track)
        self.audio_track_box.setCurrentIndex(index)
        self.audio_track_box.blockSignals(False)


    def change_audio_track(self, index):
        track_id = self.audio_track_box.itemData(index)
        self.media_player.audio_set_track(track_id)


    def update_time_label(self):
        current_time = self.media_player.get_time() // 1000
        total_time = self.media_player.get_length() // 1000
        current_time_str = self.format_time(current_time)
        total_time_str = self.format_time(total_time)
        self.time_label.setText(f'{current_time_str} / {total_time_str}')


    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f'{minutes:02}:{seconds:02}'


    def closeEvent(self, event):
        self.media_player.stop()
        self.timer.stop()
        self.closed.emit()
        event.accept()



class NextcloudVideoPlayer(QMainWindow):
    loggedIn = pyqtSignal()


    def __init__(self):
        super().__init__()
        self.setWindowTitle('Nextcloud видео проигрыватель')
        self.setGeometry(100, 100, 800, 600)
        
        self.server_url = None
        self.username = None
        self.password = None

        self.tree_widget = QTreeWidget(self)
        self.tree_widget.setHeaderLabel('Файлы')
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout = QVBoxLayout()
        layout.addWidget(self.tree_widget)
        
        container = QWidget()
        container.setLayout(layout)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(container)
        
        main_container = QWidget()
        main_container.setLayout(main_layout)
        self.setCentralWidget(main_container)
        
        self.loggedIn.connect(self.browse_files)

        self.create_menu()

        self.log_window = QTextEdit(self)
        self.log_window.setReadOnly(True)
        self.log_window.setMinimumHeight(100)

        self.save_log_button = QPushButton("Сохранить лог")
        self.save_log_button.clicked.connect(self.save_log)

        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_window)
        log_layout.addWidget(self.save_log_button)
        
        log_container = QWidget()
        log_container.setLayout(log_layout)
        
        self.dock_widget = QDockWidget("Лог", self)
        self.dock_widget.setWidget(log_container)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()
        self.toggle_log_action = QAction("Открыть лог", self)
        self.toggle_log_action.triggered.connect(self.toggle_log_window)
        self.menuBar().addAction(self.toggle_log_action)
        
        self.vlc_instance = vlc.Instance()

        self.load_settings()
        self.show_login_dialog()
    

    def create_menu(self):
        self.menu = self.menuBar().addMenu('Настройки')

        self.theme_action = QAction('Тёмная тема', self)
        self.theme_action.setCheckable(True)
        self.theme_action.toggled.connect(self.toggle_theme)
        self.menu.addAction(self.theme_action)


    def show_login_dialog(self):
        dialog = LoginDialog(self, self.server_url, self.username, self.password)
        if dialog.exec_() == QDialog.Accepted:
            self.server_url, self.username, self.password = dialog.get_credentials()
            logging.info(f"Выполнен вход, имя пользователя: {self.username}")
            self.save_settings()
            self.loggedIn.emit()
        else:
            sys.exit()


    def toggle_theme(self, checked):
        if checked:
            self.set_dark_theme()
        else:
            self.set_light_theme()
        self.save_settings()


    def set_dark_theme(self):
        dark_stylesheet = """
        QMainWindow {
            background-color: #2e2e2e;
        }
        QTreeWidget, QDialog, QDockWidget, QTextEdit, QPushButton {
            background-color: #3e3e3e;
            color: #ffffff;
        }
        QMenuBar, QMenu, QMenu::item {
            background-color: #3e3e3e;
            color: #ffffff;
        }
        QMenu::item:selected {
            background-color: #5e5e5e;
        }
        QSlider::groove:horizontal {
            border: 1px solid #bbb;
            background: #3e3e3e;
            height: 10px;
            border-radius: 4px;
        }
        QSlider::sub-page:horizontal {
            background: #ffffff;
            border: 1px solid #777;
            height: 10px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #2e2e2e;
            border: 1px solid #5c5c5c;
            width: 20px;
            margin: -5px 0;
            border-radius: 4px;
        }
        """
        app.setStyleSheet(dark_stylesheet)


    def set_light_theme(self):
        app.setStyleSheet("")


    def browse_files(self):
        if not self.username or not self.password:
            self.show_login_error()
            return
        
        try:
            logging.debug("Получение списка файлов...")
            self.populate_file_tree()
        except Exception as e:
            logging.error(f"Ошибка получения списка файлов: {e}")
            print(f"Ошибка: {e}")
    

    def show_login_error(self):
        logging.warning("Пожалуйста, сначала войдите в систему.")
        QMessageBox.warning(self, "Ошибка входа в систему", "Пожалуйста, сначала войдите в систему.")
    

    def show_login_failed_error(self):
        logging.warning("Ошибка входа. Пожалуйста, проверьте свои учетные данные.")
        QMessageBox.critical(self, "Ошибка входа в систему", "Ошибка входа. Пожалуйста, проверьте URL-адрес вашего сервера, имя пользователя и пароль.")


    def populate_file_tree(self, path=""):
        full_url = self.server_url + "remote.php/dav/files/" + quote(self.username, safe='') + "/" + path
        logging.debug(f"Запрос списка файлов из: {full_url}")
        try:
            response = requests.request("PROPFIND", full_url, auth=BasicAuthWithUnicode(self.username, self.password), headers={"Depth": "1"})
            if response.status_code == 207:
                current_item = self.tree_widget.currentItem() if path else None
                if current_item:
                    current_item.takeChildren()
                else:
                    self.tree_widget.clear()
                items = self.extract_links(response.content)
                if items:
                    existing_items = set()  # To keep track of existing items
                    for item in items:
                        decoded_item = requests.utils.unquote(item)
                        if decoded_item != path and decoded_item not in existing_items:
                            tree_item = QTreeWidgetItem([decoded_item])
                            tree_item.setData(0, Qt.UserRole, path + item)
                            if item.endswith('/'):
                                tree_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                            if current_item:
                                current_item.addChild(tree_item)
                            else:
                                self.tree_widget.addTopLevelItem(tree_item)
                            existing_items.add(decoded_item)  # Add the item to the set of existing items
                    logging.info("Список файлов успешно получен.")
                else:
                    logging.info("Файлы не найдены.")
            else:
                logging.error(f"Не удалось получить список файлов: {response.status_code} {response.reason}")
                self.show_login_failed_error()
        except requests.exceptions.RequestException as e:
            logging.error(f"Запрос не выполнен: {e}")
            self.show_login_failed_error()

    

    def extract_links(self, content):
        from xml.etree import ElementTree as ET
        tree = ET.ElementTree(ET.fromstring(content))
        root = tree.getroot()
        namespaces = {'d': 'DAV:'}
        items = []

        logging.debug("Анализ XML-ответа:")
        logging.debug(ET.tostring(root, encoding='unicode'))
        
        for response in root.findall('d:response', namespaces):
            href = response.find('d:href', namespaces).text
            if not href.endswith('/'):
                href = href.split('/')[-1]
            else:
                href = href.split('/')[-2] + '/'
            items.append(href)
            logging.debug(f"Найдена ссылка: {href}")
        return items
    

    def on_item_double_clicked(self, item, column):
        if not self.username or not self.password:
            self.show_login_error()
            return
        
        selected_file = item.data(column, Qt.UserRole)
        if selected_file.endswith('/'):
            logging.debug(f"Переход к каталогу: {selected_file}")
            item.takeChildren()
            self.populate_file_tree(selected_file)
        else:
            try:
                video_url = self.server_url + "remote.php/dav/files/" + quote(self.username, safe='') + "/" + quote(selected_file, safe='')

                username_encoded = self.username
                password_encoded = self.password
                video_url_with_auth = f"{self.server_url.replace('https://', 'https://'+username_encoded+':'+password_encoded+'@')}remote.php/dav/files/{quote(self.username, safe='')}/{quote(selected_file, safe='')}"
                logging.debug(f"URL-адрес видео с авторизацией: {video_url_with_auth}")

                media = self.vlc_instance.media_new(video_url_with_auth)
                self.open_video_player(media)
                logging.info(f"Воспроизведение видео: {selected_file}")
            except Exception as e:
                logging.error(f"Ошибка воспроизведения видео: {e}")
                print(f"Error: {e}")


    def open_video_player(self, media):
        self.video_player_window = VideoPlayerWindow(self.vlc_instance, media)
        self.video_player_window.closed.connect(self.on_video_player_closed)
        self.video_player_window.show()


    def on_video_player_closed(self):
        logging.info("Видеоплеер закрыт")
        self.video_player_window = None


    def toggle_log_window(self):
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()


    def save_log(self):
        now = datetime.now()
        log_filename = f"Nextcloud-Video-Player_{now.strftime('%Y_%m_%d_%H_%M_%S')}.log"
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить журнал", log_filename, "Log Files (*.log);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'w') as file:
                file.write(self.log_window.toPlainText())
            logging.info(f"Журнал сохранён в {file_path}")


    def save_settings(self):
        settings = {
            'server_url': self.server_url,
            'username': self.username,
            'password': self.password,
            'theme': 'dark' if self.theme_action.isChecked() else 'light'
        }
        with open(CONFIG_FILE, 'w') as config_file:
            json.dump(settings, config_file)
        logging.info("Настройки сохранены")


    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as config_file:
                settings = json.load(config_file)
                self.server_url = settings.get('server_url', '')
                self.username = settings.get('username', '')
                self.password = settings.get('password', '')
                theme = settings.get('theme', 'light')
                if theme == 'dark':
                    self.theme_action.setChecked(True)
                    self.set_dark_theme()
                else:
                    self.set_light_theme()
            logging.info("Настройки загруженны")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    player = NextcloudVideoPlayer()
    
    class QTextEditLogger(logging.Handler):


        def __init__(self, parent):
            super().__init__()
            self.log_window = parent.log_window


        def emit(self, record):
            msg = self.format(record)
            self.log_window.append(msg)

    logger = QTextEditLogger(player)
    logger.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(logger)

    player.show()
    sys.exit(app.exec_())
