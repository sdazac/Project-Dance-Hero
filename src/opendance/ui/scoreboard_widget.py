"""ScoreBoardWidget for Practice Mode HUD."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

class ScoreBoardWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 200); border-radius: 8px;")

        self.grade_label = QLabel("SS")
        self.acc_label = QLabel("100.0%")
        self.acc_label.setStyleSheet("color: white; font-size: 20px;")
        self.combo_label = QLabel("0x")
        self.combo_label.setStyleSheet("color: cyan; font-size: 24px; font-weight: bold; margin-right: 10px;")

        layout = QHBoxLayout()
        layout.addWidget(QLabel("<span style='color:white; font-size:14px;'>Grade</span>"))
        layout.addWidget(self.grade_label)
        layout.addStretch()
        layout.addWidget(QLabel("<span style='color:white; font-size:14px;'>Acc:</span>"))
        layout.addWidget(self.acc_label)
        layout.addStretch()
        layout.addWidget(QLabel("<span style='color:white; font-size:14px;'>Combo</span>"))
        layout.addWidget(self.combo_label)
        self.setLayout(layout)
        self.update_score("SS", 100.0, 0) # Inicializar estilos

    def update_score(self, grade: str, accuracy: float, combo: int) -> None:
        self.grade_label.setText(grade)
        self.acc_label.setText(f"{accuracy:.1f}%")
        self.combo_label.setText(f"{combo}x")
        
        if grade in ("SS", "S"):
            self.grade_label.setStyleSheet("color: gold; font-size: 32px; font-weight: bold;")
        elif grade == "A":
            self.grade_label.setStyleSheet("color: #00ff00; font-size: 32px; font-weight: bold;")
        elif grade in ("B", "C"):
            self.grade_label.setStyleSheet("color: orange; font-size: 32px; font-weight: bold;")
        else:
            self.grade_label.setStyleSheet("color: red; font-size: 32px; font-weight: bold;")