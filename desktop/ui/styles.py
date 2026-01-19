"""
Стилі та кольори для Desktop додатку.
"""

# Light Theme Colors (Matching Fusion / Main Window)
WINDOW_BG = "#F0F0F0"       # Standard Fusion grey background
TEXT_COLOR = "#000000"      # Black text
ACCENT_COLOR = "#3A86FF"    # Blue accent (used in buttons usually)
SECONDARY_TEXT = "#555555"  # Grey text for secondary info

def get_splash_stylesheet() -> str:
    """Повертає CSS для сплеш-скріна (Light Theme)."""
    return f"""
        QLabel {{
            color: {TEXT_COLOR};
            font-family: "Segoe UI";
        }}
        QProgressBar {{
            border: 1px solid #CCCCCC;
            border-radius: 4px;
            background-color: #FFFFFF;
            text-align: center;
            color: {TEXT_COLOR};
            height: 20px;
        }}
        QProgressBar::chunk {{
            border-radius: 3px;
            background-color: {ACCENT_COLOR};
        }}
    """
