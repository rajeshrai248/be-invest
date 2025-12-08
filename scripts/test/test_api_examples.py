#!/usr/bin/env python3
"""Example script demonstrating be-invest API usage.

This script shows how to:
1. Fetch cost analysis for all brokers
2. Get specific broker details
3. Refresh PDF data
4. Trigger comprehensive analysis
5. Get markdown summary
"""

import requests
import json
import time
from typing import Optional

# API Base URL
API_URL = "http://localhost:8000"

# Color codes for terminal output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{title:^80}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")


def print_success(msg: str):
    """Print success message."""
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg: str):
    """Print error message."""
    print(f"{RED}❌ {msg}{RESET}")


def print_info(msg: str):
    """Print info message."""
    print(f"{YELLOW}ℹ️  {msg}{RESET}")


def check_health() -> bool:
    """Check if API is running."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("API is healthy and running")
            return True
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to API. Make sure it's running: python scripts/run_api.py")
        return False
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def get_all_brokers():
    """Get list of all brokers."""
    print_header("Getting List of All Brokers")
    try:
        response = requests.get(f"{API_URL}/brokers")
        response.raise_for_status()
        brokers = response.json()

        print(f"Found {len(brokers)} brokers:\n")
        for broker in brokers:
            print(f"  • {broker['name']}")
            print(f"    Website: {broker['website']}")
            print(f"    Instruments: {', '.join(broker['instruments'])}")
            print(f"    Data sources: {len(broker.get('data_sources', []))}")

        return [b['name'] for b in brokers]
    except Exception as e:
        print_error(f"Failed to get brokers: {e}")
        return []


def get_all_cost_analysis():
    """Get comprehensive cost analysis for all brokers."""
    print_header("Getting Cost Analysis for All Brokers")
    try:
        response = requests.get(f"{API_URL}/cost-analysis")
        response.raise_for_status()
        data = response.json()

        print_success(f"Retrieved analysis for {len(data)} brokers")

        for broker_name, analysis in data.items():
            print(f"\n{YELLOW}{broker_name}:{RESET}")

            if "error" in analysis:
                print(f"  ⚠️  Error: {analysis['error']}")
                continue

            if "summary" in analysis:
                print(f"  Summary: {analysis['summary'][:100]}...")

            if "fee_categories" in analysis:
                print(f"  Fee categories: {len(analysis['fee_categories'])}")
                for cat in analysis['fee_categories'][:2]:
                    print(f"    - {cat.get('category', 'Unknown')}")

        return data
    except Exception as e:
        print_error(f"Failed to get cost analysis: {e}")
        return {}


def get_broker_cost_analysis(broker_name: str):
    """Get cost analysis for a specific broker."""
    print_header(f"Getting Cost Analysis for {broker_name}")
    try:
        response = requests.get(f"{API_URL}/cost-analysis/{broker_name}")
        response.raise_for_status()
        data = response.json()

        print_success(f"Retrieved analysis for {broker_name}")

        analysis = data.get("analysis", {})

        if "summary" in analysis:
            print(f"\n{YELLOW}Summary:{RESET}")
            print(f"  {analysis['summary']}")

        if "fee_categories" in analysis:
            print(f"\n{YELLOW}Fee Categories ({len(analysis['fee_categories'])}): {RESET}")
            for cat in analysis['fee_categories'][:3]:
                print(f"  • {cat.get('category', 'Unknown')}")
                if "tiers" in cat:
                    print(f"    Tiers: {len(cat['tiers'])}")

        if "supported_instruments" in analysis:
            print(f"\n{YELLOW}Supported Instruments:{RESET}")
            instruments = analysis['supported_instruments']
            print(f"  {', '.join(instruments)}")

        return data
    except requests.exceptions.HTTPError as e:
        print_error(f"Broker not found: {e}")
        return {}
    except Exception as e:
        print_error(f"Failed to get broker analysis: {e}")
        return {}


def get_summary():
    """Get markdown summary."""
    print_header("Getting Markdown Summary")
    try:
        response = requests.get(f"{API_URL}/summary")
        response.raise_for_status()
        summary = response.text

        lines = summary.split('\n')
        print_success(f"Retrieved summary ({len(lines)} lines, {len(summary):,} chars)")

        # Print first 30 lines
        print("\n{YELLOW}Summary Preview:{RESET}\n")
        for line in lines[:30]:
            print(line)
        print(f"\n... ({len(lines) - 30} more lines)")

        return summary
    except Exception as e:
        print_error(f"Failed to get summary: {e}")
        return ""


def refresh_pdfs(brokers: Optional[list] = None, force: bool = False):
    """Refresh PDF downloads and text extraction."""
    print_header("Refreshing PDFs")

    params = {}
    if brokers:
        params['brokers_to_refresh'] = brokers
    if force:
        params['force'] = True

    try:
        print_info(f"Requesting PDF refresh{f' for {brokers}' if brokers else ''} (force={force})...")

        response = requests.post(f"{API_URL}/refresh-pdfs", params=params)
        response.raise_for_status()
        data = response.json()

        stats = {
            'total_pdfs': data.get('total_pdfs_processed', 0),
            'total_chars': data.get('total_chars_extracted', 0),
            'errors': data.get('total_errors', 0),
            'brokers': len(data.get('brokers_refreshed', []))
        }

        print_success(f"PDF refresh complete!")
        print(f"  Brokers processed: {stats['brokers']}")
        print(f"  PDFs extracted: {stats['total_pdfs']}")
        print(f"  Total characters: {stats['total_chars']:,}")
        print(f"  Errors: {stats['errors']}")

        # Show details per broker
        for broker in data.get('brokers_refreshed', []):
            print(f"\n  {YELLOW}{broker['name']}:{RESET}")
            print(f"    PDFs: {broker.get('pdfs_processed', 0)}")
            print(f"    Characters: {broker.get('chars_extracted', 0):,}")
            for source in broker.get('sources', []):
                if source.get('status') == 'extracted':
                    print(f"      ✓ {source.get('filename', 'unknown')}: {source.get('chars', 0):,} chars")

        return data
    except Exception as e:
        print_error(f"PDF refresh failed: {e}")
        return {}


def refresh_and_analyze(brokers: Optional[list] = None, force: bool = False):
    """Refresh and analyze brokers."""
    print_header("Refreshing PDFs and Analyzing with LLM")

    params = {}
    if brokers:
        params['brokers_to_process'] = brokers
    if force:
        params['force'] = True

    print_info("This may take 1-3 minutes. Requires OPENAI_API_KEY environment variable.")
    print_info("Downloading PDFs, extracting text, and running LLM analysis...")

    try:
        response = requests.post(f"{API_URL}/refresh-and-analyze", params=params)
        response.raise_for_status()
        data = response.json()

        print_success("Refresh and analysis complete!")

        refresh = data.get('refresh_results', {})
        print(f"\n{YELLOW}PDF Refresh Results:{RESET}")
        print(f"  PDFs processed: {refresh.get('total_pdfs_processed', 0)}")
        print(f"  Characters extracted: {refresh.get('total_chars_extracted', 0):,}")
        print(f"  Errors: {refresh.get('total_errors', 0)}")

        analysis = data.get('analysis_results', {})
        print(f"\n{YELLOW}Analysis Results:{RESET}")
        for broker_name, broker_data in analysis.items():
            sources = broker_data.get('sources', [])
            print(f"  • {broker_name}: {len(sources)} sources analyzed")

        if data.get('errors'):
            print(f"\n{YELLOW}Errors encountered:{RESET}")
            for error in data.get('errors', []):
                print(f"  ⚠️  {error}")

        return data
    except Exception as e:
        print_error(f"Refresh and analyze failed: {e}")
        return {}


def interactive_menu():
    """Show interactive menu."""
    while True:
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}{'be-invest API Examples':^80}{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        print("1. List all brokers")
        print("2. Get cost analysis for all brokers")
        print("3. Get cost analysis for specific broker")
        print("4. Get markdown summary")
        print("5. Refresh PDFs")
        print("6. Refresh and analyze (requires OPENAI_API_KEY)")
        print("7. Exit")

        choice = input("\nSelect option (1-7): ").strip()

        if choice == "1":
            get_all_brokers()

        elif choice == "2":
            get_all_cost_analysis()

        elif choice == "3":
            brokers = get_all_brokers()
            if brokers:
                print(f"\nAvailable brokers: {', '.join(brokers)}")
                broker_name = input("Enter broker name: ").strip()
                get_broker_cost_analysis(broker_name)

        elif choice == "4":
            get_summary()

        elif choice == "5":
            refresh_pdfs()

        elif choice == "6":
            refresh_and_analyze()

        elif choice == "7":
            print_success("Goodbye!")
            break

        input("\nPress Enter to continue...")


def main():
    """Main entry point."""
    print(f"\n{GREEN}{'='*80}{RESET}")
    print(f"{GREEN}{'be-invest API Example Script':^80}{RESET}")
    print(f"{GREEN}{'='*80}{RESET}\n")

    # Check if API is running
    if not check_health():
        print("\nTo start the API, run:")
        print(f"  {YELLOW}python scripts/run_api.py{RESET}")
        return

    print("\nRunning in demo mode. Available options:")
    print("  1. Run interactive menu: python scripts/test_api.py --interactive")
    print("  2. Get all brokers: python scripts/test_api.py --brokers")
    print("  3. Get cost analysis: python scripts/test_api.py --costs")
    print("  4. Refresh PDFs: python scripts/test_api.py --refresh")
    print("  5. Refresh and analyze: python scripts/test_api.py --analyze\n")

    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive":
            interactive_menu()
        elif sys.argv[1] == "--brokers":
            get_all_brokers()
        elif sys.argv[1] == "--costs":
            get_all_cost_analysis()
        elif sys.argv[1] == "--refresh":
            refresh_pdfs()
        elif sys.argv[1] == "--analyze":
            refresh_and_analyze()
    else:
        # Run default demo
        print(f"{YELLOW}Running default demo...{RESET}\n")
        get_all_brokers()
        time.sleep(1)
        get_all_cost_analysis()


if __name__ == "__main__":
    main()

