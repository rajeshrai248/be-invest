"""Quick test and fix for OpenAI API integration.

This script helps diagnose and fix API issues.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def test_api_key():
    """Test if API key is set and valid format."""
    print("\n" + "="*70)
    print("🔍 TESTING OPENAI API KEY")
    print("="*70)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("❌ API key not set!")
        print("\nSet it with:")
        print("  PowerShell: $env:OPENAI_API_KEY = 'sk-...'")
        print("  Bash: export OPENAI_API_KEY='sk-...'")
        return False

    print(f"✅ API key is set")
    print(f"   Length: {len(api_key)} characters")
    print(f"   Starts with: {api_key[:20]}...")

    if not api_key.startswith("sk-"):
        print("❌ API key doesn't start with 'sk-'")
        print("   Get a new one from: https://platform.openai.com/account/api-keys")
        return False

    print("✅ API key format looks correct")
    return True


def test_openai_package():
    """Test if OpenAI SDK is installed."""
    print("\n" + "="*70)
    print("📦 CHECKING OPENAI SDK")
    print("="*70)

    try:
        import openai
        print(f"✅ OpenAI SDK installed")
        print(f"   Version: {openai.__version__}")
        return True
    except ImportError:
        print("❌ OpenAI SDK not installed")
        print("\nInstall with:")
        print("  pip install openai")
        return False


def test_api_connection():
    """Test actual API connection."""
    print("\n" + "="*70)
    print("🌐 TESTING API CONNECTION")
    print("="*70)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  No API key set, skipping connection test")
        return False

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        print("🚀 Making test request to GPT-4o...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": "Say 'OK' and nothing else"
                }
            ],
            max_tokens=10,
            temperature=0
        )

        result = response.choices[0].message.content
        print(f"✅ API connection successful!")
        print(f"   Response: {result}")
        return True

    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False


def main():
    print("\n🔧 BROKER SUMMARY - API DIAGNOSTICS")
    print("="*70)

    # Run tests
    key_ok = test_api_key()
    sdk_ok = test_openai_package()

    if key_ok and sdk_ok:
        conn_ok = test_api_connection()

        if conn_ok:
            print("\n" + "="*70)
            print("✅ ALL SYSTEMS OPERATIONAL")
            print("="*70)
            print("\nYou can now run:")
            print("  python scripts/generate_summary.py --model gpt-4o")
            return 0

    print("\n" + "="*70)
    print("⚠️  SOME ISSUES DETECTED")
    print("="*70)

    if not key_ok:
        print("\n1. Set your API key:")
        print("   $env:OPENAI_API_KEY = 'sk-your-actual-key'")

    if not sdk_ok:
        print("\n2. Install OpenAI SDK:")
        print("   pip install openai")

    print("\n3. Then run diagnostics again:")
    print("   python scripts/test_api.py")

    return 1


if __name__ == "__main__":
    sys.exit(main())

