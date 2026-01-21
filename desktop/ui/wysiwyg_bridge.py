"""Міст для взаємодії між Python та JavaScript у WYSIWYG редакторі."""

import json
from pathlib import Path
from typing import Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWebEngineCore import QWebEngineScript


class WysiwygBridge(QObject):
    """
    Міст для взаємодії між Python та JavaScript у WYSIWYG редакторі.

    Дозволяє JavaScript викликати Python методи і навпаки.
    """

    # Сигнали, що генеруються JavaScript
    content_changed = pyqtSignal(str, bool)  # (content_json, has_changes)
    field_updated = pyqtSignal(str, str)  # (field_name, value)
    signatories_changed = pyqtSignal(str)  # (signatories_json)

    def __init__(self, parent=None):
        """
        Ініціалізує міст.

        Args:
            parent: Батьківський об'єкт
        """
        super().__init__(parent)
        self._current_content: dict[str, str] = {}
        self._current_signatories: list[dict] = []

    @pyqtSlot(str, bool)
    def on_content_changed(self, content_json: str, has_changes: bool) -> None:
        """
        Обробляє зміну контенту з JavaScript.

        Args:
            content_json: JSON рядок з контентом документу
            has_changes: Чи є зміни відносно оригіналу
        """
        try:
            self._current_content = json.loads(content_json)
            self.content_changed.emit(content_json, has_changes)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from JS: {e}")

    @pyqtSlot(str, str)
    def on_field_updated(self, field_name: str, value: str) -> None:
        """
        Обробляє оновлення поля.

        Args:
            field_name: Назва поля
            value: Нове значення
        """
        self.field_updated.emit(field_name, value)

    @pyqtSlot(str)
    def on_signatories_changed(self, signatories_json: str) -> None:
        """
        Обробляє зміну списку погоджувачів.

        Args:
            signatories_json: JSON рядок зі списком погоджувачів
        """
        try:
            self._current_signatories = json.loads(signatories_json)
            self.signatories_changed.emit(signatories_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing signatories JSON from JS: {e}")

    def get_current_content(self) -> dict[str, str]:
        """
        Повертає поточний контент.

        Returns:
            Словник з контентом блоків
        """
        return self._current_content.copy()

    def update_field(self, web_view, field_name: str, value: Any) -> None:
        """
        Оновлює значення auto-field у документі.

        Args:
            web_view: QWebEngineView інстанс
            field_name: Назва поля
            value: Нове значення
        """
        script = f"""
        (function() {{
            if (typeof updateAutoField === 'function') {{
                updateAutoField('{field_name}', '{value}');
            }} else {{
                setTimeout(() => {{
                    if (typeof updateAutoField === 'function') {{
                        updateAutoField('{field_name}', '{value}');
                    }}
                }}, 500);
            }}
        }})();
        """
        web_view.page().runJavaScript(script)

    def update_block(self, web_view, block_name: str, html: str) -> None:
        """
        Оновлює цілий блок документу.

        Args:
            web_view: QWebEngineView інстанс
            block_name: Назва блоку
            html: HTML контент
        """
        # Екрануємо HTML для коректної передачі в JS
        escaped_html = json.dumps(html)
        script = f"""
        (function() {{
            if (typeof updateBlock === 'function') {{
                updateBlock('{block_name}', {escaped_html});
            }}
        }})();
        """
        web_view.page().runJavaScript(script)

    def set_document_status(self, web_view, status: str, status_text: str = "") -> None:
        """
        Встановлює статус документу (оновлює UI).

        Args:
            web_view: QWebEngineView інстанс
            status: Статус (draft, signed_by_applicant, approved_by_dispatcher,
                       signed_dep_head, agreed, signed_rector, scanned, processed)
            status_text: Текст статусу (опціонально)
        """
        script = f"""
        (function() {{
            if (typeof setDocumentStatus === 'function') {{
                setDocumentStatus('{status}', '{status_text}');
            }} else {{
                setTimeout(() => {{
                    if (typeof setDocumentStatus === 'function') {{
                        setDocumentStatus('{status}', '{status_text}');
                    }}
                }}, 500);
            }}
        }})();
        """
        web_view.page().runJavaScript(script)

    def get_block_content(self, web_view, block_name: str, callback: Callable[[str], None]) -> None:
        """
        Отримує контент конкретного блоку.

        Args:
            web_view: QWebEngineView інстанс
            block_name: Назва блоку
            callback: Функція зворотного виклику з результатом
        """
        script = f"""
        (function() {{
            if (typeof getBlockContent === 'function') {{
                getBlockContent('{block_name}');
            }}
        }})();
        """
        web_view.page().runJavaScript(script, callback)

    def reset_to_original(self, web_view) -> None:
        """
        Скидає документ до оригінального стану.

        Args:
            web_view: QWebEngineView інстанс
        """
        script = """
        (function() {
            if (typeof resetToOriginal === 'function') {
                resetToOriginal();
            }
        })();
        """
        web_view.page().runJavaScript(script)

    def export_content(self, web_view) -> None:
        """
        Змушує JavaScript експортувати контент.

        Args:
            web_view: QWebEngineView інстанс
        """
        script = """
        (function() {
            if (typeof exportContent === 'function') {
                exportContent();
            }
        })();
        """
        web_view.page().runJavaScript(script)

    def get_document_html_for_pdf(self, web_view, callback: Callable[[str], None]) -> None:
        """
        Отримує повний HTML документ для генерації PDF.

        Args:
            web_view: QWebEngineView інстанс
            callback: Функція зворотного виклику з результатом HTML
        """
        script = """
        (function() {
            if (typeof getDocumentHtmlForPdf === 'function') {
                return getDocumentHtmlForPdf();
            }
            return '';
        })();
        """
        web_view.page().runJavaScript(script, callback)

    def update_signatories(self, web_view, signatories: list[dict]) -> None:
        """
        Оновлює список погоджувачів у документі.

        Args:
            web_view: QWebEngineView інстанс
            signatories: Список словників з даними погоджувачів
        """
        signatories_json = json.dumps(signatories, ensure_ascii=False)
        # Wrap in safe partial execution
        script = f"""
        (function() {{
            if (typeof updateSignatories === 'function') {{
                updateSignatories({signatories_json});
            }} else {{
                setTimeout(() => {{
                    if (typeof updateSignatories === 'function') {{
                        updateSignatories({signatories_json});
                    }}
                }}, 500);
            }}
        }})();
        """
        web_view.page().runJavaScript(script)

    def set_predefined_signatories(self, web_view, signatories: list[dict]) -> None:
        """
        Встановлює попередньо визначених погоджувачів (будуть додаватися при натисканні + Погоджувач).

        Args:
            web_view: QWebEngineView інстанс
            signatories: Список словників з даними погоджувачів
        """
        signatories_json = json.dumps(signatories, ensure_ascii=False)
        script = f"""
        (function() {{
            if (typeof setPredefinedSignatories === 'function') {{
                setPredefinedSignatories({signatories_json});
            }} else {{
                setTimeout(() => {{
                     if (typeof setPredefinedSignatories === 'function') {{
                        setPredefinedSignatories({signatories_json});
                     }}
                }}, 500);
            }}
        }})();
        """
        web_view.page().runJavaScript(script)

    def initialize_signatories(self, web_view) -> None:
        """
        Ініціалізує погоджувачів (викликає завантаження попередньо визначених).

        Args:
            web_view: QWebEngineView інстанс
        """
        script = """
        (function() {
            if (typeof initializeSignatories === 'function') {
                initializeSignatories();
            }
        })();
        """
        web_view.page().runJavaScript(script)

    def get_current_signatories(self) -> list[dict]:
        """
        Повертає поточний список погоджувачів.

        Returns:
            Список словників з даними погоджувачів
        """
        return self._current_signatories.copy()

    def execute_format_command(self, web_view, command: str, value: Any = None) -> None:
        """
        Виконує команду форматування.

        Args:
            web_view: QWebEngineView інстанс
            command: Назва команди (bold, italic, justifyLeft, etc.)
            value: Значення команди (опціонально)
        """
        if value is None:
            script = f"document.execCommand('{command}', false, null);"
        else:
            value_str = json.dumps(value)
            script = f"document.execCommand('{command}', false, {value_str});"
        web_view.page().runJavaScript(script)

    def set_font_size(self, web_view, size: int) -> None:
        """
        Встановлює розмір шрифту.

        Args:
            web_view: QWebEngineView інстанс
            size: Розмір (1-7)
        """
        script = f"document.getElementById('fontSizeSelect').value = '{size}';"
        script += f"document.execCommand('fontSize', false, '{size}');"
        web_view.page().runJavaScript(script)

    def load_content(self, web_view, html_content: str) -> None:
        """
        Завантажує HTML контент у редактор.

        Args:
            web_view: QWebEngineView інстанс
            html_content: HTML контент документа
        """
        # Отримуємо базові налаштування
        templates_dir = Path(__file__).parent.parent / "templates"
        base_url = QUrl.fromLocalFile(str(templates_dir) + "/")
        web_view.setHtml(html_content, base_url)

    def set_line_height(self, web_view, height: float) -> None:
        """
        Встановлює міжрядковий інтервал.

        Args:
            web_view: QWebEngineView інстанс
            height: Інтервал (1.0, 1.15, 1.5, 2.0)
        """
        script = f"document.getElementById('lineHeightSelect').value = '{height}';"
        # Застосовуємо до виділеного тексту
        js_code = f"""
        (function() {{
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {{
                const range = selection.getRangeAt(0);
                let container = range.commonAncestorContainer;
                if (container.nodeType === 3) {{
                    container = container.parentElement;
                }}
                container.style.lineHeight = '{height}';
            }}
        }})();
        """
        web_view.page().runJavaScript(script + js_code)

    def is_modified(self) -> bool:
        """
        Перевіряє, чи було змінено документ.

        Returns:
            True якщо документ змінено
        """
        return bool(self._current_content)


class WysiwygEditorState:
    """
    Клас для зберігання стану WYSIWYG редактора.

    Містить дані про відформатовані блоки, які потрібно зберегти
    при генерації фінального документа.
    """

    def __init__(self):
        """Ініціалізує стан редактора."""
        self.blocks: dict[str, str] = {}
        self.custom_fields: dict[str, str] = {}
        self.formatting: dict[str, dict] = {}

    def update_block(self, block_name: str, html: str) -> None:
        """
        Оновлює контент блоку.

        Args:
            block_name: Назва блоку
            html: HTML контент
        """
        self.blocks[block_name] = html

    def update_field(self, field_name: str, value: str) -> None:
        """
        Оновлює значення поля.

        Args:
            field_name: Назва поля
            value: Значення
        """
        self.custom_fields[field_name] = value

    def set_formatting(self, element_id: str, format_props: dict) -> None:
        """
        Зберігає форматування для елементу.

        Args:
            element_id: ID елементу або CSS selector
            format_props: Словник з властивостями форматування
        """
        self.formatting[element_id] = format_props

    def get_block(self, block_name: str) -> str | None:
        """
        Отримує контент блоку.

        Args:
            block_name: Назва блоку

        Returns:
            HTML контент або None
        """
        return self.blocks.get(block_name)

    def get_field(self, field_name: str) -> str | None:
        """
        Отримує значення поля.

        Args:
            field_name: Назва поля

        Returns:
            Значення або None
        """
        return self.custom_fields.get(field_name)

    def clear(self) -> None:
        """Очищає весь стан."""
        self.blocks.clear()
        self.custom_fields.clear()
        self.formatting.clear()

    def to_dict(self) -> dict:
        """
        Перетворює стан у словник.

        Returns:
            Словник з усіма даними стану
        """
        return {
            "blocks": self.blocks.copy(),
            "custom_fields": self.custom_fields.copy(),
            "formatting": self.formatting.copy(),
        }

    def from_dict(self, data: dict) -> None:
        """
        Завантажує стан зі словника.

        Args:
            data: Словник з даними стану
        """
        self.blocks = data.get("blocks", {}).copy()
        self.custom_fields = data.get("custom_fields", {}).copy()
        self.formatting = data.get("formatting", {}).copy()
