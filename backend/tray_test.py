#!/usr/bin/env python3
"""
Minimal test of pywebview + pystray interaction.

Tests whether calling window.show() and window.destroy() from the tray thread
works without hanging or crashing. No uvicorn, database, or logging setup.

Print at each step so we can see exactly where things fail (or succeed).
"""
import threading
import time


def test_tray_gui():
    print("[main] Starting tray GUI test")

    # Create webview window
    import webview

    print("[main] Creating webview window on about:blank")
    window = webview.create_window(
        title='Tray Test Window',
        url='about:blank',
        width=800,
        height=600,
        resizable=True,
    )
    print("[main] Webview window created, object ready")

    # Setup tray icon
    import pystray
    from PIL import Image, ImageDraw

    def create_test_icon():
        """Generate a simple icon for the test in RGBA mode (Windows compatible)."""
        size = (64, 64)
        # Use RGBA mode for better Windows compatibility
        image = Image.new('RGBA', size, color=(100, 150, 200, 255))  # Light blue with alpha
        draw = ImageDraw.Draw(image)
        draw.text((20, 24), "T", fill=(255, 255, 255, 255))  # White "T" for Test
        return image

    def on_open_pos(icon, item):
        """Tray menu: Open — bring window to front."""
        print("[tray] Menu item clicked: Open POS")
        print("[tray]   Before window.show()")
        try:
            window.show()
            print("[tray]   After window.show() — SUCCESS")
        except Exception as e:
            print(f"[tray]   window.show() FAILED: {e}")

    def on_exit(icon, item):
        """Tray menu: Exit — close window."""
        print("[tray] Menu item clicked: Exit")
        print("[tray]   Before window.destroy()")
        try:
            window.destroy()
            print("[tray]   After window.destroy() — SUCCESS")
        except Exception as e:
            print(f"[tray]   window.destroy() FAILED: {e}")

    def run_tray():
        """Run tray icon on this thread."""
        print("[tray] Tray thread started, creating icon")
        try:
            # Generate icon in RGBA mode
            icon_image = create_test_icon()
            print(f"[tray] Icon image created: {icon_image.mode} {icon_image.size}")

            icon = pystray.Icon(
                "test",
                icon=icon_image,
                menu=pystray.Menu(
                    pystray.MenuItem("Open POS", on_open_pos),
                    pystray.MenuItem("Exit", on_exit),
                ),
            )
            print("[tray] Icon created successfully, calling icon.run()")
            icon.run()
            print("[tray] icon.run() returned (should not see this unless window closed)")
        except Exception as e:
            print(f"[tray] EXCEPTION in tray setup: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    # Start tray on daemon thread
    tray_thread = threading.Thread(target=run_tray, daemon=True)
    print("[main] Starting tray thread")
    tray_thread.start()
    print("[main] Tray thread started, sleeping briefly to let it initialize")
    time.sleep(1.0)
    print("[main] About to call webview.start() (blocking on main thread)")

    # Start webview on main thread (blocking call)
    webview.start(gui='edgechromium', debug=False)
    print("[main] webview.start() returned (window was closed)")

    # Shutdown
    print("[main] Shutting down")
    tray_thread.join(timeout=2)
    print("[main] Test complete")


if __name__ == '__main__':
    test_tray_gui()
