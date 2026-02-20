#!/usr/bin/env python
"""
Analyze why Revolut and Degiro scraping is disabled.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append('src')

from be_invest.config_loader import load_brokers_from_yaml

def analyze_scraping_status():
    """Analyze the scraping status of all brokers."""

    print("\n" + "="*80)
    print("🔍 SCRAPING ANALYSIS: Why Revolut and Degiro Cannot Be Scraped")
    print("="*80 + "\n")

    # Load configuration
    brokers = load_brokers_from_yaml(Path('data/brokers.yaml'))

    print(f"📋 Found {len(brokers)} brokers in configuration\n")

    for broker in brokers:
        print(f"🏦 {broker.name}")
        print(f"   Website: {broker.website}")

        # Check data sources
        if hasattr(broker, 'data_sources') and broker.data_sources:
            print(f"   📊 Data sources: {len(broker.data_sources)}")
            for i, ds in enumerate(broker.data_sources, 1):
                status = "✅ ENABLED" if ds.allowed_to_scrape else "❌ DISABLED"
                print(f"      {i}. {ds.description} - {status}")
                if not ds.allowed_to_scrape:
                    print(f"         URL: {ds.url}")
                    if hasattr(ds, 'notes') and ds.notes:
                        print(f"         Notes: {ds.notes}")

        # Check news sources
        if hasattr(broker, 'news_sources') and broker.news_sources:
            print(f"   📰 News sources: {len(broker.news_sources)}")
            for i, ns in enumerate(broker.news_sources, 1):
                status = "✅ ENABLED" if ns.allowed_to_scrape else "❌ DISABLED"
                print(f"      {i}. {ns.description} - {status}")
                if not ns.allowed_to_scrape:
                    print(f"         URL: {ns.url}")
                    if hasattr(ns, 'notes') and ns.notes:
                        print(f"         Notes: {ns.notes}")

        print()  # Empty line between brokers

    # Focus on Revolut and Degiro
    print("\n" + "="*60)
    print("🎯 SPECIFIC ANALYSIS: Revolut and Degiro")
    print("="*60 + "\n")

    revolut = [b for b in brokers if b.name == "Revolut"]
    degiro = [b for b in brokers if "Degiro" in b.name]

    if revolut:
        revolut = revolut[0]
        print("🔴 REVOLUT ISSUES:")
        print("   • News source disabled with note: 'returns junk data'")
        print("   • Data sources are enabled (PDFs) but use LLM extraction")
        print("   • Web scraping of news is intentionally disabled")
        if revolut.news_sources:
            for ns in revolut.news_sources:
                if not ns.allowed_to_scrape:
                    print(f"   • Disabled URL: {ns.url}")
                    print(f"   • Reason: {ns.description}")

    if degiro:
        degiro = degiro[0]
        print("\n🔴 DEGIRO ISSUES:")
        print("   • News source disabled due to anti-bot protection")
        print("   • Site actively blocks automated access")
        print("   • Data source is PDF-based (no web scraping)")
        if degiro.news_sources:
            for ns in degiro.news_sources:
                if not ns.allowed_to_scrape:
                    print(f"   • Disabled URL: {ns.url}")
                    print(f"   • Reason: {ns.description}")

    print("\n" + "="*60)
    print("💡 SOLUTIONS")
    print("="*60)
    print("1. Revolut: Use API or RSS feed if available")
    print("2. Degiro: Find alternative news sources or use RSS")
    print("3. Both: Focus on PDF data extraction for pricing")
    print("4. Alternative: Use third-party financial news APIs")
    print("\n")

if __name__ == "__main__":
    analyze_scraping_status()
