"""ScoreBoardWidget for Practice Mode HUD."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class ScoreBoardWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.grade_label = QLabel("SS")
        self.grade_label.setStyleSheet("color: gold; font-size: 32px; font-weight: bold;")
        self.acc_label = QLabel("100.0%")
        self.acc_label.setStyleSheet("color: white; font-size: 20px;")
        self.combo_label = QLabel("0x")
        self.combo_label.setStyleSheet(
            "color: cyan; font-size: 24px; font-weight: bold; margin-right: 10px;"
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo_label)
        layout.addWidget(self.grade_label)
        layout.addWidget(self.acc_label)
        layout.addStretch()
        
        self.setLayout(layout)

    def update_score(self, grade: str, accuracy: float, combo: int) -> None:
        self.grade_label.setText(grade)
        self.acc_label.setText(f"{accuracy:.1f}%")
        self.combo_label.setText(f"{combo}x")

        if grade in ("SS", "S"):
            self.grade_label.setStyleSheet("color: gold; font-size: 32px; font-weight: bold;")
        elif grade in ("A", "B"):
            self.grade_label.setStyleSheet("color: #4CAF50; font-size: 32px; font-weight: bold;")
        elif grade == "C":
            self.grade_label.setStyleSheet("color: orange; font-size: 32px; font-weight: bold;")
        else:
            self.grade_label.setStyleSheet("color: red; font-size: 32px; font-weight: bold;")