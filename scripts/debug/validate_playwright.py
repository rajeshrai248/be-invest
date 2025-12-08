"""Helper to validate Playwright installation and suggest fixes.

Usage:
  python scripts/validate_playwright.py

What it does:
- Prints the Python executable used.
- Checks whether `playwright` and other dependencies are importable.
- If importable, attempts to start a headless Chromium browser (safe quick test).
- On common failures, prints exact commands to run (using the same interpreter).
- Shows environment variable settings that affect Playwright behavior.

The script does NOT auto-install; it only provides guidance and optional CLI commands.
"""
from __future__ import annotations
import sys
import os
import traceback

def main():
    print("=" * 80)
    print("🔍 BE-INVEST PLAYWRIGHT & DEPENDENCIES VALIDATION")
    print("=" * 80)
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print("=" * 80)

    # Check environment variables
    print("\n📋 Environment Variables:")
    auto_install = os.getenv("BE_INVEST_PLAYWRIGHT_AUTOINSTALL", "not set")
    browsers_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "default")
    print(f"  BE_INVEST_PLAYWRIGHT_AUTOINSTALL: {auto_install}")
    print(f"  PLAYWRIGHT_BROWSERS_PATH: {browsers_path}")

    # Check optional performance dependencies
    print("\n📦 Optional Dependencies:")
    try:
        from bs4 import BeautifulSoup
        # Test if BeautifulSoup can actually use lxml
        _ = BeautifulSoup("<html></html>", "lxml")
        print("  ✅ lxml: installed and working (BeautifulSoup will use fast lxml parser)")
    except ImportError:
        print("  ⚠️  lxml: not installed (BeautifulSoup will use slower html.parser)")
        print(f"     Install with: {sys.executable} -m pip install --user lxml")
    except Exception as e:
        print(f"  ⚠️  lxml: installed but not working ({str(e)[:50]}...)")
        print(f"     Reinstall with: {sys.executable} -m pip install --force-reinstall --user lxml")

    # Check whether playwright is importable
    print("\n🎭 Playwright Package:")
    try:
        import playwright
        from playwright.sync_api import sync_playwright
        print(f"  ✅ Playwright: installed (version {playwright.__version__ if hasattr(playwright, '__version__') else 'unknown'})")
    except Exception as e:
        print("  ❌ Playwright: NOT importable")
        print("\n📝 Action Required:")
        print(f"  1. Install Playwright: {sys.executable} -m pip install --upgrade --user playwright")
        print(f"  2. Install browsers: {sys.executable} -m playwright install chromium")
        print(f"  3. (Windows) Install helper: {sys.executable} -m playwright install winldd")
        print("\n⚠️  Note: The app will fall back to 'requests' library if Playwright is unavailable.")
        return 2

    # Print where playwright script would be installed (helpful for PATH issues)
    try:
        scripts_dir = os.path.join(os.path.dirname(sys.executable), 'Scripts')
        print(f"\n📂 Scripts Directory: {scripts_dir}")
        if scripts_dir not in os.environ.get('PATH', ''):
            print("  ℹ️  Scripts dir not on PATH. Use 'python -m playwright' to avoid PATH issues.")
    except Exception:
        pass

    # Try a quick headless launch test to check browser binaries
    print("\n🚀 Testing Chromium Launch:")
    try:
        print("  Attempting headless Chromium launch (tests browser binaries)...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser_version = getattr(browser, 'version', None)
            browser.close()

        print(f"  ✅ SUCCESS: Chromium launched OK" + (f" (version: {browser_version})" if browser_version else ""))
        print("\n" + "=" * 80)
        print("✅ RESULT: Playwright and Chromium are fully functional!")
        print("=" * 80)
        return 0
    except Exception as exc:
        msg = str(exc)
        print(f"  ❌ FAILED: {msg[:100]}...")

        # Show full traceback for debugging
        if '--verbose' in sys.argv or '-v' in sys.argv:
            tb = traceback.format_exc()
            print("\n📋 Full Traceback:")
            print(tb)

        # Common guidance for missing executables
        print("\n" + "=" * 80)
        if "Executable doesn't exist" in msg or "playwright install" in msg or "Looks like Playwright was just installed" in msg:
            print("❌ DIAGNOSIS: Playwright browser binaries are not installed")
            print("=" * 80)
            print("\n📝 Solution - Run these commands:")
            print(f"  1. {sys.executable} -m pip install --upgrade --user playwright")
            print(f"  2. {sys.executable} -m playwright install chromium")
            print(f"  3. (Windows only) {sys.executable} -m playwright install winldd")
            print("\n💡 Alternative - Set custom browsers path if AppData is restricted:")
            print(f"  $env:PLAYWRIGHT_BROWSERS_PATH = 'C:\\Users\\{os.getlogin()}\\ms-playwright'")
            print(f"  {sys.executable} -m playwright install chromium")
            print("\n⚠️  IMPORTANT: The be-invest app will automatically fall back to 'requests'")
            print("   library if Playwright is unavailable. News scraping will still work,")
            print("   but JavaScript-rendered pages may not be fully scraped.")
            return 3
        else:
            print("❌ DIAGNOSIS: Playwright launch failed (non-installation error)")
            print("=" * 80)
            print("\n📋 Error details above. Common causes:")
            print("  - Antivirus blocking browser executable")
            print("  - Corrupted Playwright installation")
            print("  - Insufficient permissions")
            print("\n📝 Try these steps:")
            print(f"  1. Reinstall: {sys.executable} -m pip install --force-reinstall playwright")
            print(f"  2. Clean install browsers: {sys.executable} -m playwright install chromium")
            print("  3. Run this script with --verbose flag for full traceback")
            print("\n⚠️  The app will use 'requests' fallback if Playwright is unavailable.")
            return 4

if __name__ == '__main__':
    rc = main()
    sys.exit(rc)

