"""Practice Mode Window (Full AV Playback, Async Loading & Real-time Scoring)."""

import dataclasses
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QPixmap, QResizeEvent, QCloseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink, QVideoFrame
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from opendance.camera.manager import CameraManager
from opendance.config.models import AppConfig
from opendance.motion.normalizer import normalize_pose
from opendance.scoring.engine import ScoringEngine
from opendance.scoring.session_tracker import SessionTracker
from opendance.ui.scoreboard_widget import ScoreBoardWidget
from opendance.ui.silhouette_renderer import get_transparent_silhouette
from opendance.video.reference_analyzer import ReferenceAnalyzer
from opendance.pose.result import PoseResult


class AnalysisWorker(QThread):
    """Ejecuta el análisis pesado en un hilo secundario para no congelar la UI."""
    finished = Signal(object)

    def __init__(self, path: str, app_config: AppConfig) -> None:
        super().__init__()
        self.path = path
        self.app_config = app_config

    def run(self) -> None:
        try:
            analyzer = ReferenceAnalyzer(
                self.app_config.pose_config,
                self.app_config.normalization_config,
                self.app_config.reference_config
            )
            reference_seq = analyzer.analyze(self.path)
            analyzer.close()
            self.finished.emit(reference_seq)
        except Exception as e:
            self.finished.emit(e)


class PracticeWindow(QWidget):
    def __init__(self, camera_manager: CameraManager, app_config: AppConfig) -> None:
        super().__init__()
        self._camera_manager = camera_manager
        self._app_config = app_config
        self._session = SessionTracker()

        self._latest_pose: Optional[PoseResult] = None
        self._scoring_engine: Optional[ScoringEngine] = None
        self._is_playing = False
        self._video_path = ""
        self._worker: Optional[AnalysisWorker] = None

        # --- Reproductor de Video (QVideoSink evita bugs de superposición en Windows) ---
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._media_player.setAudioOutput(self._audio_output)

        self._video_sink = QVideoSink()
        self._media_player.setVideoSink(self._video_sink)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)

        # Pantalla principal donde dibujaremos los frames del video
        self._video_display = QLabel("Load a dance video to start...")
        self._video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_display.setStyleSheet("background-color: #111; color: white; font-size: 24px;")
        self._video_display.setMinimumSize(800, 600)

        # --- UI Flotante (Ahora son hijos directos del video para flotar correctamente) ---
        self._scoreboard = ScoreBoardWidget(self._video_display)

        self._silhouette_label = QLabel(self._video_display)
        self._silhouette_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._silhouette_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._loading_overlay = QLabel(self._video_display)
        self._loading_overlay.setStyleSheet(
            "background-color: rgba(0,0,0,210); color: white; font-size: 26px; font-weight: bold;"
        )
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.hide()

        # --- Controles ---
        self._load_btn = QPushButton("Load Track (Video)")
        self._play_btn = QPushButton("Play / Pause")
        self._restart_btn = QPushButton("Restart")

        self._play_btn.setEnabled(False)
        self._restart_btn.setEnabled(False)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._load_btn)
        btn_layout.addWidget(self._play_btn)
        btn_layout.addWidget(self._restart_btn)

        layout = QVBoxLayout()
        layout.addWidget(self._video_display, stretch=1)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Bucle principal de juego para calcular scores
        self._timer = QTimer()
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._game_loop_tick)

        # Conexiones
        self._load_btn.clicked.connect(self._load_video)
        self._play_btn.clicked.connect(self._toggle_playback)
        self._restart_btn.clicked.connect(self._restart_video)

        # Iniciar Cámara
        self._camera_manager.start()
        if self._camera_manager.frame_worker is not None:
            self._camera_manager.frame_worker.frame_ready.connect(self._on_camera_frame)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Mantener los overlays ajustados al tamaño del reproductor de video
        vw_rect = self._video_display.rect()
        self._scoreboard.setGeometry(10, 10, vw_rect.width() - 20, 60)

        # Tamaño de silueta reducido (250x250)
        sil_w, sil_h = 250, 250
        self._silhouette_label.setGeometry(
            vw_rect.width() - sil_w - 20,
            vw_rect.height() - sil_h - 20,
            sil_w, sil_h
        )

        self._loading_overlay.setGeometry(vw_rect)

    @Slot(object, object)
    def _on_camera_frame(self, frame: Any, pose_result: PoseResult) -> None:
        self._latest_pose = pose_result

    @Slot(object)
    def _on_video_frame(self, frame: QVideoFrame) -> None:
        if not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return

        # Pintar el frame de video nativo en nuestro QLabel seguro
        scaled = QPixmap.fromImage(image).scaled(
            self._video_display.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._video_display.setPixmap(scaled)

    def _load_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Dance Video", "", "Video Files (*.mp4 *.avi *.mkv)"
        )
        if not path:
            return

        self._video_path = path
        self._loading_overlay.setText(
            "Analyzing choreography... Please wait.\n(Extracting features)"
        )
        self._loading_overlay.show()
        self._loading_overlay.raise_()

        # Bloquear botones para evitar doble clic
        self._load_btn.setEnabled(False)
        self._play_btn.setEnabled(False)
        self._restart_btn.setEnabled(False)

        # Ejecutar análisis en hilo secundario para no congelar la pantalla
        self._worker = AnalysisWorker(path, self._app_config)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.start()

    @Slot(object)
    def _on_analysis_finished(self, result: Any) -> None:
        self._load_btn.setEnabled(True)

        if isinstance(result, Exception):
            self._loading_overlay.setText(f"Error analyzing video:\n{result}")
            return

        self._scoring_engine = ScoringEngine(result, self._app_config)
        self._media_player.setSource(QUrl.fromLocalFile(self._video_path))

        self._loading_overlay.hide()
        self._play_btn.setEnabled(True)
        self._restart_btn.setEnabled(True)

        self._restart_video()

    def _restart_video(self) -> None:
        self._session = SessionTracker()
        self._scoreboard.update_score("SS", 100.0, 0)

        self._media_player.setPosition(0)
        self._media_player.play()
        self._is_playing = True
        self._timer.start()

    def _toggle_playback(self) -> None:
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
            self._timer.stop()
            self._is_playing = False
        else:
            self._media_player.play()
            self._timer.start()
            self._is_playing = True

    def _game_loop_tick(self) -> None:
        if not self._latest_pose:
            return

        # 1. Actualizar siempre la silueta espejo
        # (funciona incluso si está pausado, genial para probar tu posición)
        pixmap = get_transparent_silhouette(
            250, 250,
            self._latest_pose,
            self._app_config.pose_config.skeleton_visibility_threshold,
            mirror=True
        )
        self._silhouette_label.setPixmap(pixmap)

        # 2. MOTOR DE PUNTUACIÓN EN TIEMPO REAL
        if self._is_playing and self._scoring_engine and not self._latest_pose.is_empty:
            norm_pose = normalize_pose(self._latest_pose, self._app_config.normalization_config)
            if not norm_pose.valid:
                return

            current_time_ms = self._media_player.position()

            # Usar dataclasses.replace evita el error "FrozenInstanceError" de Python
            norm_pose = dataclasses.replace(norm_pose, timestamp_ms=current_time_ms)

            comparison = self._scoring_engine.score_frame(norm_pose, {}, None)
            if comparison:
                self._session.update_with_rating(comparison.event_rating)
                self._scoreboard.update_score(
                    self._session.state.current_grade,
                    self._session.state.accuracy_percentage,
                    self._session.state.combo
                )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._camera_manager.stop()
        self._media_player.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        super().closeEvent(event)