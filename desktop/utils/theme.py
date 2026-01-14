"""Утиліти для теми інтерфейсу."""

from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtCore import QSettings
from pathlib import Path

import darkdetect


def apply_theme(window: QMainWindow, theme: str | None = None):
    """
    Застосовує тему до вікна.

    Args:
        window: Головне вікно
        theme: Тема ("dark", "light" або None для автовизначення)
    """
    if theme is None:
        theme = "dark" if darkdetect.isDark() else "light"

    if theme == "dark":
        stylesheet = _get_dark_stylesheet()
    else:
        stylesheet = _get_light_stylesheet()

    window.setStyleSheet(stylesheet)


def _get_dark_stylesheet() -> str:
    """Повертає таблицю стилів для темної теми."""
    return """
        QMainWindow {
            background-color: #1e1e1e;
        }

        QWidget {
            background-color: #2d2d2d;
            color: #e0e0e0;
        }

        QTabWidget::pane {
            border: 1px solid #3d3d3d;
            background-color: #2d2d2d;
        }

        QTabBar::tab {
            background-color: #3d3d3d;
            color: #e0e0e0;
            padding: 8px 16px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: #2d2d2d;
        }

        QTableWidget {
            background-color: #252525;
            alternate-background-color: #2d2d2d;
            gridline-color: #3d3d3d;
        }

        QTableWidget::item:selected {
            background-color: #404040;
        }

        QPushButton {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #505050;
            padding: 6px 12px;
            border-radius: 3px;
        }

        QPushButton:hover {
            background-color: #505050;
        }

        QPushButton:pressed {
            background-color: #303030;
        }

        QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {
            background-color: #252525;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
            padding: 4px;
            border-radius: 3px;
        }

        QGroupBox {
            border: 1px solid #3d3d3d;
            margin-top: 8px;
            padding-top: 12px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
        }

        QMenuBar {
            background-color: #2d2d2d;
            color: #e0e0e0;
        }

        QMenuBar::item:selected {
            background-color: #404040;
        }

        QMenu {
            background-color: #2d2d2d;
            color: #e0e0e0;
        }
    """


def _get_light_stylesheet() -> str:
    """Повертає таблицю стилів для світлої теми."""
    return """
        QMainWindow {
            background-color: #f5f5f5;
        }

        QWidget {
            background-color: #ffffff;
            color: #333333;
        }

        QTabWidget::pane {
            border: 1px solid #ddd;
            background-color: #ffffff;
        }

        QTabBar::tab {
            background-color: #e0e0e0;
            color: #333333;
            padding: 8px 16px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: #ffffff;
        }

        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f9f9f9;
            gridline-color: #ddd;
        }

        QTableWidget::item:selected {
            background-color: #e3f2fd;
        }

        QPushButton {
            background-color: #f0f0f0;
            color: #333333;
            border: 1px solid #ccc;
            padding: 6px 12px;
            border-radius: 3px;
        }

        QPushButton:hover {
            background-color: #e0e0e0;
        }

        QPushButton:pressed {
            background-color: #d0d0d0;
        }

        QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #ccc;
            padding: 4px;
            border-radius: 3px;
        }

        QGroupBox {
            border: 1px solid #ccc;
            margin-top: 8px;
            padding-top: 12px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
        }

        QMenuBar {
            background-color: #f0f0f0;
            color: #333333;
        }

        QMenuBar::item:selected {
            background-color: #e0e0e0;
        }

        QMenu {
            background-color: #ffffff;
            color: #333333;
        }
    """


def get_settings() -> QSettings:
    """
    Повертає QSettings для додатку.

    Returns:
        QSettings об'єкт
    """
    return QSettings("VacationManager", "VacationManager")
