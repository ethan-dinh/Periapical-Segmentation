import sys
from pathlib import Path


def load_stylesheet() -> str:
    """
    Loads the application stylesheet from resources/style.qss.
    Returns empty string if file not found.
    """
    # Determine the directory where theme.py resides (DentAnX/ui)
    current_dir = Path(__file__).parent
    
    # Construct path to resources/style.qss
    # Relative path: ../resources/style.qss
    style_path = current_dir.parent / "resources" / "style.qss"
    
    if not style_path.exists():
        print(f"Warning: Stylesheet not found at {style_path}", file=sys.stderr)
        return ""
        
    try:
        return style_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Error loading stylesheet: {e}", file=sys.stderr)
        return ""
