"""
Entry point for the Restaurant POS application.

Starts uvicorn programmatically, opens the browser when the server is ready,
and handles errors gracefully with logging and user-facing message boxes.
"""
import sys
import os
import socket
import time
import logging
import threading
import json
from urllib.request import urlopen


# Guard stdout/stderr BEFORE any other imports.
# When run with --noconsole (PyInstaller windowed build), sys.stdout/sys.stderr are None.
# Any library that tries to write to them will crash. We replace them with the OS null device.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')


def main():
    """Main entry point for the POS application."""
    import uvicorn
    import ctypes
    from app.main import app
    from app.database import DATA_DIR

    def setup_startup_logging(data_dir: str) -> logging.Logger:
        """Set up basic file logging for startup and server management."""
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, 'pos.log')

        logger = logging.getLogger('pos_startup')
        # Remove any existing handlers to avoid duplicates
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_path)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        return logger

    logger = setup_startup_logging(DATA_DIR)

    def is_port_in_use(port=8000):
        """Check if a port is already in use."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0

    def wait_for_health(server_thread, max_attempts=240):
        """
        Poll the /api/health endpoint until the server is ready.

        Attempts every 250ms for up to 60 seconds (240 attempts).
        Returns True if healthy, False if timeout or server thread dies.
        """
        for attempt in range(max_attempts):
            # If server thread dies unexpectedly, bail immediately with real error
            if not server_thread.is_alive():
                logger.error("Server thread stopped unexpectedly during startup")
                return False

            try:
                response = urlopen('http://127.0.0.1:8000/api/health', timeout=1)
                if response.status == 200:
                    logger.info("Server is healthy, opening window")
                    return True
            except Exception:
                pass
            time.sleep(0.25)

        logger.warning("Server failed to reach healthy state in 60 seconds")
        return False

    # Check if port 8000 is already in use
    if is_port_in_use():
        logger.error("Port 8000 is already in use. App cannot start.")
        ctypes.windll.user32.MessageBoxW(
            0,
            "Restaurant POS is already running.\nClose the existing window or restart the computer if it seems stuck.",
            "Application Already Running",
            0
        )
        sys.exit(1)

    # Create uvicorn server configuration
    config = uvicorn.Config(
        app,
        host='127.0.0.1',
        port=8000,
        log_level='info',
        log_config=None,  # Do not configure logging; leave our handlers untouched
    )
    server = uvicorn.Server(config)

    # Track exceptions from the server thread so the startup guard can see them
    server_exception = None

    def run_server():
        """Run the uvicorn server in this thread."""
        nonlocal server_exception
        try:
            server.run()
        except Exception as e:
            server_exception = e
            logger.error(f"Server thread failed: {e}")
            raise

    # Start server in a background daemon thread
    logger.info("Starting Restaurant POS server on 127.0.0.1:8000")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for the server to become healthy before opening the window
    if not wait_for_health(server_thread):
        if server_exception:
            raise server_exception
        raise RuntimeError("Server failed to become healthy within timeout")

    # Fetch restaurant name from settings for window title.
    # Use same default as the Settings model so fresh installs show "My Restaurant" consistently.
    window_title = "My Restaurant"  # default fallback
    try:
        response = urlopen('http://127.0.0.1:8000/api/settings', timeout=2)
        settings = json.loads(response.read().decode())
        restaurant_name = settings.get('restaurant_name', '').strip()
        if restaurant_name:  # Use it only if non-empty
            window_title = restaurant_name
    except Exception:
        # Any failure (timeout, bad JSON, network error, etc.) falls through to default
        pass

    # Create and start the webview window on the main thread.
    # webview.create_window() creates the window object; webview.start() is the blocking call.
    import webview
    window = webview.create_window(
        title=window_title,
        url='http://127.0.0.1:8000',
        width=1280,
        height=800,
        resizable=True,
        background_color='#ffffff',
    )

    # Tray icon reference, will be set by setup_tray if it succeeds
    tray_icon = None
    tray_initiated_exit = False  # Flag to track if tray menu triggered the exit

    def setup_tray(window, server):
        """Run tray icon on this thread. Failures are logged but not raised."""
        nonlocal tray_icon, tray_initiated_exit
        try:
            import pystray
            from PIL import Image, ImageDraw

            def create_app_icon():
                """Generate a simple icon for the tray."""
                size = (64, 64)
                image = Image.new('RGBA', size, color=(70, 130, 180, 255))  # Steel blue with alpha
                draw = ImageDraw.Draw(image)
                draw.text((16, 24), "POS", fill=(255, 255, 255, 255))  # White "POS" text
                return image

            def on_open_pos(icon, item):
                """Tray menu: Open POS — bring window to front."""
                window.show()

            def on_exit(icon, item):
                """Tray menu: Exit — close window and shut down server through normal path."""
                nonlocal tray_initiated_exit
                logger.info("User exited via tray icon")
                tray_initiated_exit = True
                server.should_exit = True
                window.destroy()

            # Create icon with correct parameter name: icon= (not image=)
            tray_icon = pystray.Icon(
                "RestaurantPOS",
                icon=create_app_icon(),
                menu=pystray.Menu(
                    pystray.MenuItem("Open POS", on_open_pos),
                    pystray.MenuItem("Exit", on_exit),
                ),
            )
            tray_icon.run()
        except Exception as e:
            logger.error(f"Failed to start tray icon: {e}")
            # Do not raise; the POS must work without the tray

    # Start tray icon on a daemon thread
    try:
        tray_thread = threading.Thread(target=setup_tray, args=(window, server), daemon=True)
        tray_thread.start()
    except Exception as e:
        logger.error(f"Failed to start tray thread: {e}")
        tray_thread = None

    # Start webview on main thread (blocking call)
    webview.start(gui='edgechromium', debug=False)

    # After webview.start() returns (user closed the window), shut down the server cleanly
    logger.info("Window closed, shutting down server")

    # Stop the tray icon if it was started
    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception as e:
            logger.error(f"Error stopping tray icon: {e}")

    server.should_exit = True

    # Wait for the server thread to exit gracefully (with a timeout)
    server_thread.join(timeout=5)
    if server_thread.is_alive():
        logger.warning("Server thread did not exit cleanly within 5 seconds")

    logger.info("Restaurant POS shut down cleanly")


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Unhandled exception - log it and show a message box.
        # With --noconsole, unhandled exceptions are completely invisible without logging.
        import traceback

        # Try to log to pos.log
        try:
            from app.database import get_data_dir
            data_dir = get_data_dir()
            os.makedirs(data_dir, exist_ok=True)
            log_path = os.path.join(data_dir, 'pos.log')
            with open(log_path, 'a') as f:
                f.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} [CRITICAL] Restaurant POS failed to start:\n")
                f.write(traceback.format_exc())
                f.write('\n')
        except Exception:
            # If we can't even log, we can't do much, but try to show the error anyway
            pass

        # Show error message box
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Restaurant POS failed to start.\nPlease check the log file (pos.log) in your data folder and contact support.",
                "Startup Failed",
                0
            )
        except Exception:
            pass

        sys.exit(1)
