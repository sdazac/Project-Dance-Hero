"""Practice Mode Window (Full AV Playback, Async Loading & Real-time Scoring)."""

import dataclasses
import time
from collections import deque
from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QPixmap, QResizeEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from opendance.camera.manager import CameraManager
from opendance.camera.state import CameraState
from opendance.config.models import AppConfig
from opendance.motion.angles import compute_joint_angles
from opendance.motion.live_motion import motion_for_latest
from opendance.motion.normalized_pose import NormalizedPose
from opendance.motion.normalizer import normalize_pose
from opendance.pose.result import PoseResult
from opendance.scoring.engine import ScoringEngine
from opendance.scoring.session_tracker import SessionTracker
from opendance.ui.scoreboard_widget import ScoreBoardWidget
from opendance.ui.silhouette_renderer import get_transparent_silhouette
from opendance.ui.timing import fps_to_interval_ms, ms_to_slider, slider_to_ms
from opendance.video.progress import progress_percent
from opendance.video.reference_analyzer import ReferenceAnalyzer


class AnalysisWorker(QThread):
    """Ejecuta el análisis pesado en un hilo secundario para no congelar la UI."""
    finished = Signal(object)
    progress = Signal(int)  # 0..100

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

            def _cb(done: int, total: int) -> None:
                self.progress.emit(progress_percent(done, total))

            reference_seq = analyzer.analyze(self.path, progress_callback=_cb)
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
        # Buffer rodante de poses normalizadas recientes para la motion en vivo.
        # Acotado para que la memoria no se acumule (practice-mode-mvp Req 7.4);
        # 5 frames bastan para una velocidad por diferencia hacia atras estable.
        self._pose_buffer: deque[NormalizedPose] = deque(maxlen=5)
        self._is_playing = False
        self._video_path = ""
        self._worker: Optional[AnalysisWorker] = None
        # Estado del seek: duracion del medio en ms y si el usuario arrastra el
        # slider (para no pelear con las actualizaciones automaticas de posicion).
        self._duration_ms = 0
        self._user_seeking = False
        # Evita presentar el resultado final mas de una vez por sesion.
        self._finished_presented = False

        # Diagnostico de rendimiento: FPS efectivos de render y scoring calculados
        # con una media movil exponencial de los intervalos entre ticks. El FPS de
        # inferencia se lee directamente de CameraManager (Requirement 1.5).
        self._render_fps = 0.0
        self._scoring_fps = 0.0
        self._last_render_ts: Optional[float] = None
        self._last_scoring_ts: Optional[float] = None

        # --- Reproductor de Video (QVideoSink evita bugs de superposición en Windows) ---
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)
        self._media_player.setAudioOutput(self._audio_output)

        self._video_sink = QVideoSink()
        self._media_player.setVideoSink(self._video_sink)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)

        # Detectar el fin de la reproduccion para detener el scoring y mostrar el
        # resultado final. En Qt6 mediaStatusChanged emite MediaStatus y EndOfMedia
        # indica que el medio termino.
        self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Seguir posicion y duracion para mover/habilitar el slider de seek.
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)

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

        # Overlay de diagnostico con los tres FPS efectivos (render/inference/scoring).
        self._debug_overlay = QLabel(self._video_display)
        self._debug_overlay.setStyleSheet(
            "background-color: rgba(0,0,0,150); color: #0f0; font-size: 11px; padding: 2px;"
        )
        self._debug_overlay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._debug_overlay.setText("R: 0 | I: 0 | S: 0")

        # --- Controles ---
        self._load_btn = QPushButton("Load Track (Video)")
        self._play_btn = QPushButton("Play / Pause")
        self._restart_btn = QPushButton("Restart")

        self._play_btn.setEnabled(False)
        self._restart_btn.setEnabled(False)

        # Slider de seek: resolucion entera fija (0..1000) mapeada a ms contra la
        # duracion. Deshabilitado hasta que haya un medio con duracion conocida.
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.setEnabled(False)

        # Selector de velocidad de reproduccion, poblado desde la configuracion.
        self._speed_combo = QComboBox()
        self._speed_combo.setEnabled(False)
        practice_config = self._app_config.practice_config
        for rate in practice_config.playback_speeds:
            self._speed_combo.addItem(f"{rate}x", rate)
        default_index = self._speed_combo.findData(practice_config.default_playback_speed)
        self._speed_combo.setCurrentIndex(default_index if default_index >= 0 else 0)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._load_btn)
        btn_layout.addWidget(self._play_btn)
        btn_layout.addWidget(self._restart_btn)
        btn_layout.addWidget(self._speed_combo)

        layout = QVBoxLayout()
        layout.addWidget(self._video_display, stretch=1)
        layout.addWidget(self._seek_slider)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Bucles desacoplados: el render mantiene la silueta fluida y el scoring
        # corre mas lento para la comparacion pesada (decoupled render/scoring rates).
        self._render_timer = QTimer()
        self._render_timer.setInterval(fps_to_interval_ms(practice_config.render_fps))
        self._render_timer.timeout.connect(self._render_tick)

        self._scoring_timer = QTimer()
        self._scoring_timer.setInterval(fps_to_interval_ms(practice_config.scoring_fps))
        self._scoring_timer.timeout.connect(self._scoring_tick)

        # Conexiones
        self._load_btn.clicked.connect(self._load_video)
        self._play_btn.clicked.connect(self._toggle_playback)
        self._restart_btn.clicked.connect(self._restart_video)

        # Seek: marcar arrastre al presionar y aplicar la posicion al soltar.
        self._seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self._seek_slider.sliderReleased.connect(self._on_slider_released)
        # Velocidad: aplicar la tasa seleccionada al reproductor.
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        # Escuchar errores de camara para detener el bucle de forma segura (Req 7.3).
        self._camera_manager.state_changed.connect(self._on_camera_state_changed)

        # Iniciar Cámara
        self._camera_manager.start()
        if self._camera_manager.frame_worker is not None:
            self._camera_manager.frame_worker.frame_ready.connect(self._on_camera_frame)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Mantener los overlays ajustados al tamaño del reproductor de video
        vw_rect = self._video_display.rect()
        self._scoreboard.setGeometry(10, 10, vw_rect.width() - 20, 60)

        # La geometria del overlay usa el tamaño de silueta configurado para que
        # coincida con el tamaño con el que se renderiza en _render_tick.
        sil_w = sil_h = self._app_config.practice_config.silhouette_size
        self._silhouette_label.setGeometry(
            vw_rect.width() - sil_w - 20,
            vw_rect.height() - sil_h - 20,
            sil_w, sil_h
        )

        self._loading_overlay.setGeometry(vw_rect)

        # Overlay de diagnostico en la esquina superior derecha, debajo del
        # scoreboard, para no solaparlo.
        dbg_w, dbg_h = 140, 20
        self._debug_overlay.setGeometry(
            vw_rect.width() - dbg_w - 10,
            80,
            dbg_w, dbg_h
        )

    @Slot(object, object)
    def _on_camera_frame(self, frame: Any, pose_result: PoseResult) -> None:
        # Latest-wins: solo sobrescribimos el ultimo pose, sin cola. Los poses
        # obsoletos se descartan y el frame de camara completo no se retiene
        # (evita conservar frames a resolucion completa).
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

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        # Guardar la duracion y habilitar el slider solo si es conocida (> 0).
        self._duration_ms = duration_ms
        self._seek_slider.setEnabled(duration_ms > 0)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        # Reflejar la posicion en el slider salvo mientras el usuario lo arrastra.
        # setValue emite valueChanged (no conectado al seek), asi que es seguro.
        if self._user_seeking or self._duration_ms <= 0:
            return
        self._seek_slider.setValue(
            ms_to_slider(position_ms, self._duration_ms, self._seek_slider.maximum())
        )

    def _on_slider_pressed(self) -> None:
        self._user_seeking = True

    def _on_slider_released(self) -> None:
        ms = slider_to_ms(
            self._seek_slider.value(), self._seek_slider.maximum(), self._duration_ms
        )
        self._seek_to(ms)
        self._user_seeking = False

    def _seek_to(self, position_ms: int) -> None:
        self._media_player.setPosition(position_ms)
        # Un seek es un salto temporal: descartar las poses bufferizadas para no
        # calcular la motion en vivo a traves de la discontinuidad (Requirement 1.5).
        self._pose_buffer.clear()

    @Slot(int)
    def _on_speed_changed(self, index: int) -> None:
        rate = self._speed_combo.currentData()
        if isinstance(rate, (int, float)):
            self._set_playback_speed(float(rate))

    def _set_playback_speed(self, rate: float) -> None:
        self._media_player.setPlaybackRate(rate)

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
        # Habilitar los controles de reproduccion; el slider tambien se habilita
        # via durationChanged cuando se conoce la duracion del medio.
        self._seek_slider.setEnabled(True)
        self._speed_combo.setEnabled(True)

        # Aplicar la velocidad por defecto configurada y reflejarla en el combo.
        default_speed = self._app_config.practice_config.default_playback_speed
        self._set_playback_speed(default_speed)
        default_index = self._speed_combo.findData(default_speed)
        if default_index >= 0:
            self._speed_combo.setCurrentIndex(default_index)

        self._restart_video()

    def _restart_video(self) -> None:
        self._session = SessionTracker()
        # Nueva sesion: limpiar el historial de movimiento para no arrastrar
        # velocidades de una sesion anterior.
        self._pose_buffer.clear()
        self._scoreboard.update_score("SS", 100.0, 0)
        # Nueva sesion: permitir presentar el resultado final de nuevo y ocultar
        # cualquier overlay de "sesion completa" de una sesion anterior.
        self._finished_presented = False
        self._loading_overlay.hide()

        self._media_player.setPosition(0)
        self._media_player.play()
        # Reaplicar la velocidad seleccionada por si alguna version de Qt la
        # reinicia al hacer setPosition(0)+play(); no cambia la seleccion del combo.
        current_rate = self._speed_combo.currentData()
        if isinstance(current_rate, (int, float)):
            self._set_playback_speed(float(current_rate))
        self._is_playing = True
        # Ambos timers arrancan juntos al reproducir.
        self._render_timer.start()
        self._scoring_timer.start()

    def _toggle_playback(self) -> None:
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
            # En pausa detenemos solo el scoring; el render sigue vivo para que el
            # usuario pueda alinear su cuerpo (Requirement 3.3).
            self._scoring_timer.stop()
            self._is_playing = False
        else:
            self._media_player.play()
            self._render_timer.start()
            self._scoring_timer.start()
            self._is_playing = True

    def _smooth_fps(self, current_fps: float, last_ts: Optional[float], now: float) -> float:
        # Calcula un FPS suavizado (EMA) a partir del intervalo entre llamadas.
        # Barato: solo un par de operaciones aritmeticas.
        if last_ts is None:
            return current_fps
        dt = now - last_ts
        if dt <= 0:
            return current_fps
        instant_fps = 1.0 / dt
        # Peso 0.2 al valor instantaneo para amortiguar el ruido entre ticks.
        return current_fps + 0.2 * (instant_fps - current_fps)

    def _update_debug_overlay(self) -> None:
        # FPS de inferencia leido del monitor de la camara (0.0 antes de frames).
        inference_fps = self._camera_manager.fps
        self._debug_overlay.setText(
            f"R: {self._render_fps:.0f} | I: {inference_fps:.0f} | S: {self._scoring_fps:.0f}"
        )

    def _render_tick(self) -> None:
        # Dibuja la silueta espejo desde el pose mas reciente. Corre a render_fps
        # y sigue funcionando en pausa para dar feedback de posicion (Requirement 3.3).
        # Un pose None o vacio se ignora sin bloquear el bucle (se conserva el
        # ultimo frame dibujado).

        # Medir el FPS de render efectivo con una EMA barata de los intervalos.
        now = time.perf_counter()
        self._render_fps = self._smooth_fps(self._render_fps, self._last_render_ts, now)
        self._last_render_ts = now
        # El render corre a menudo: aprovechamos para refrescar el diagnostico.
        self._update_debug_overlay()

        if not self._latest_pose or self._latest_pose.is_empty:
            return

        size = self._app_config.practice_config.silhouette_size
        pixmap = get_transparent_silhouette(
            size, size,
            self._latest_pose,
            self._app_config.pose_config.skeleton_visibility_threshold,
            mirror=True
        )
        self._silhouette_label.setPixmap(pixmap)

    def _scoring_tick(self) -> None:
        # Motor de puntuacion en tiempo real. Corre a scoring_fps (mas lento que el
        # render) y solo cuando se esta reproduciendo.
        now = time.perf_counter()
        self._scoring_fps = self._smooth_fps(self._scoring_fps, self._last_scoring_ts, now)
        self._last_scoring_ts = now

        if not self._is_playing or not self._scoring_engine or not self._latest_pose:
            return
        if self._latest_pose.is_empty:
            return

        norm_pose = normalize_pose(self._latest_pose, self._app_config.normalization_config)
        if not norm_pose.valid:
            return

        current_time_ms = self._media_player.position()

        # Usar dataclasses.replace evita el error "FrozenInstanceError" de Python
        norm_pose = dataclasses.replace(norm_pose, timestamp_ms=current_time_ms)

        # Bufferizar la pose alineada para la motion en vivo (acotado, gana la ultima).
        self._pose_buffer.append(norm_pose)

        # Angulos del frame actual y motion derivada del buffer rodante, de modo
        # que las cuatro metricas de similitud contribuyan al score.
        player_angles = compute_joint_angles(norm_pose)
        player_motion = motion_for_latest(self._pose_buffer, self._app_config.motion_config)

        comparison = self._scoring_engine.score_frame(norm_pose, player_angles, player_motion)
        if comparison:
            self._session.update_with_rating(comparison.event_rating)
            self._scoreboard.update_score(
                self._session.state.current_grade,
                self._session.state.accuracy_percentage,
                self._session.state.combo
            )

    @Slot(QMediaPlayer.MediaStatus)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        # EndOfMedia indica que la reproduccion termino: detener el scoring y
        # presentar el resultado final una unica vez. El render puede seguir vivo.
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self._finished_presented:
            return
        self._finished_presented = True
        self._present_final_result()

    def _present_final_result(self) -> None:
        # Detiene el scoring, marca la sesion como no reproduciendo y muestra el
        # grado y la precision finales calculados por SessionTracker.
        self._scoring_timer.stop()
        self._is_playing = False

        final_state = self._session.state
        self._scoreboard.update_score(
            final_state.current_grade,
            final_state.accuracy_percentage,
            final_state.combo
        )
        self._loading_overlay.setText(
            f"Session complete!\nGrade: {final_state.current_grade}   "
            f"Accuracy: {final_state.accuracy_percentage:.1f}%"
        )
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    @Slot(object, str)
    def _on_camera_state_changed(self, state: Any, error_message: str) -> None:
        # Solo actuamos ante un fallo de camara; otros cambios de estado se ignoran.
        if state != CameraState.ERROR:
            return

        # Detener el bucle de forma segura: ambos timers, scoring y reproduccion.
        self._render_timer.stop()
        self._scoring_timer.stop()
        self._is_playing = False
        self._media_player.stop()

        # Mostrar un mensaje claro al usuario (Requirement 7.3).
        message = error_message or "Camera error. The practice session was stopped."
        self._loading_overlay.setText(f"Camera error:\n{message}")
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Detener los timers primero para que no disparen ticks durante la limpieza.
        self._render_timer.stop()
        self._scoring_timer.stop()
        self._camera_manager.stop()
        self._media_player.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        super().closeEvent(event)
