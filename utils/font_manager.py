"""
Font Management Utilities
Handles font loading, fallbacks, and installation for PDF generation.
"""

import logging
import os
import shutil
from pathlib import Path
from config.pdf_config import FONTS_DIR, CYRILLIC_FONTS

logger = logging.getLogger(__name__)


def get_font_path(font_type="regular"):
    """Get font path with fallback options"""
    # First try the primary font
    primary_font = FONTS_DIR / CYRILLIC_FONTS[font_type]
    if primary_font.exists():
        return f"file://{primary_font.absolute()}"

    # Try the fallback font
    fallback_font = FONTS_DIR / CYRILLIC_FONTS["fallback"]
    if fallback_font.exists():
        logger.warning(f"Primary font {CYRILLIC_FONTS[font_type]} not found, using fallback font")
        return f"file://{fallback_font.absolute()}"

    # Use system fallback
    logger.warning("No suitable fonts found in the fonts directory. Using system fonts.")
    return ""


class FontManager:
    """Manages font installation and availability for PDF generation"""
    
    def __init__(self):
        self.fonts_dir = FONTS_DIR
        self.ensure_fonts_available()
    
    def ensure_fonts_available(self) -> None:
        """Make sure we have at least one usable font for PDF generation"""
        font_found = False

        # Check for primary fonts
        for font_type, font_name in CYRILLIC_FONTS.items():
            if font_type in ["regular", "bold", "fallback"]:
                font_path = self.fonts_dir / font_name
                if font_path.exists():
                    font_found = True
                    logger.info(f"Font found: {font_path}")
                else:
                    logger.warning(f"Font not found: {font_path}")

        # If no fonts found, try to download or use a system font
        if not font_found:
            self._install_fallback_font()

    def _install_fallback_font(self) -> None:
        """Attempt to install a fallback font if none exists"""
        try:
            self.fonts_dir.mkdir(parents=True, exist_ok=True)
            if os.name == 'posix':
                potential_fonts = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Arial Unicode.ttf"
                ]
                for src_font in potential_fonts:
                    if os.path.exists(src_font):
                        dest_font = self.fonts_dir / CYRILLIC_FONTS["fallback"]
                        shutil.copy2(src_font, dest_font)
                        logger.info(f"Copied system font as fallback: {src_font} -> {dest_font}")
                        return
            logger.error("No usable fonts found. PDF generation may fail or use system fonts.")
        except Exception as e:
            logger.error(f"Error installing fallback font: {e}")

    def create_link_callback(self):
        """Create a link callback function for handling font resources in PDF"""
        def link_callback(uri: str, rel: str) -> str:
            # Handle absolute paths
            if os.path.isabs(uri):
                return uri

            # Handle relative paths and font files
            if uri.startswith("file://"):
                path = uri.replace("file://", "")
                if os.path.exists(path):
                    return path

            # For font files in our directory
            if self.fonts_dir.exists():
                # Remove any file:// prefix and FONTS_DIR path
                clean_uri = uri.replace(f"file://{self.fonts_dir.parent}/", "")
                potential_path = os.path.join(str(self.fonts_dir.parent), clean_uri)
                if os.path.exists(potential_path):
                    return potential_path

            # Default fallback
            return uri
        
        return link_callback