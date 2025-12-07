"""
ChromeDriver path finding utilities
"""
import os
import shutil
import platform


def find_chromedriver_path():
    """
    Find chromedriver path across different platforms.
    Returns the path if found, None otherwise.
    """
    # Platform-specific common paths
    # Prioritize CI-specific paths first (where chromium-chromedriver installs)
    linux_paths = [
        '/usr/lib/chromium-browser/chromedriver',  # CI-specific path (highest priority)
        '/usr/bin/chromedriver',
        '/usr/lib/chromium/chromedriver',
    ]

    macos_paths = [
        '/opt/homebrew/bin/chromedriver',  # Apple Silicon
        '/usr/local/bin/chromedriver',  # Intel
    ]

    # Check platform-specific paths first
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        search_paths = macos_paths + linux_paths
    else:  # Linux or other (CI environment)
        search_paths = linux_paths + macos_paths

    # Check common paths
    for path in search_paths:
        if path and os.path.exists(path):
            return path

    # Fallback to PATH
    return shutil.which('chromedriver')


def get_chromedriver_install_instruction():
    """
    Get platform-specific installation instruction for chromedriver.
    """
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        return "brew install chromedriver"
    else:  # Linux
        return "sudo apt-get install chromium-chromedriver"

