"""
CivitAI Scraper Test Utility
Tests the scraping functionality and displays detailed version information
"""
import sys
import json
from app.services.civitai import CivitAIService


def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}")
    else:
        print(f"{'=' * 80}")


def print_subsection(title):
    """Print a subsection header"""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def test_scrape(url):
    """Test scraping a CivitAI URL and display results"""
    
    print_separator("🔍 CIVITAI SCRAPER TEST")
    print(f"\nURL: {url}\n")
    
    # Create service
    service = CivitAIService()
    
    # Extract IDs first
    print_subsection("📋 Extracting IDs from URL")
    ids = service.extract_ids_from_url(url)
    print(f"Model ID:      {ids['modelId']}")
    print(f"Version ID:    {ids['versionId']}")
    
    if not ids['modelId']:
        print("\n❌ ERROR: Could not extract model ID from URL")
        print("   Make sure the URL is in format: https://civitai.com/models/[ID]")
        return
    
    # Attempt scrape
    print_subsection("🌐 Scraping CivitAI Page")
    
    try:
        scraped_data = service.scrape_model_page(url, "Test Model")
        
        print(f"✅ Scrape successful!")
        print(f"   Scraped at: {scraped_data['scrapedAt']}")
        
        # Display basic info
        print_subsection("📝 Model Information")
        print(f"Model Name:    {scraped_data['modelName']}")
        print(f"Model ID:      {scraped_data['modelId']}")
        print(f"Current Ver:   {scraped_data['currentVersionId']}")
        print(f"\nDescription (first 200 chars):")
        print(f"  {scraped_data['description'][:200]}...")
        
        # Display tags
        print_subsection("🏷️  Tags")
        if scraped_data['tags']:
            for i, tag in enumerate(scraped_data['tags'], 1):
                print(f"  {i:2d}. {tag}")
            print(f"\nTotal: {len(scraped_data['tags'])} tags")
        else:
            print("  No tags found")
        
        # Display aggregated trigger words
        print_subsection("✨ Aggregated Trigger Words (from all versions)")
        if scraped_data['trainedWords']:
            for i, word in enumerate(scraped_data['trainedWords'], 1):
                print(f"  {i:2d}. {word}")
            print(f"\nTotal: {len(scraped_data['trainedWords'])} unique trigger words")
        else:
            print("  No trigger words found")
        
        # Display versions in detail
        print_subsection("📦 Available Versions")
        versions = scraped_data['versions']
        
        if versions:
            print(f"\nFound {len(versions)} version(s):\n")
            
            for i, version in enumerate(versions, 1):
                print(f"{'─' * 40}")
                print(f"Version #{i}")
                print(f"{'─' * 40}")
                print(f"  ID:        {version['id']}")
                print(f"  Name:      {version['name']}")
                print(f"  Status:    {version['status']}")
                print(f"  Available: {version['available']}")
                
                # Show if this is the current version from URL
                is_current = version['id'] == scraped_data['currentVersionId']
                if is_current:
                    print(f"  >>> THIS IS THE VERSION FROM YOUR URL <<<")
                
                # Show trigger words for this version
                if version['trainedWords']:
                    print(f"  Trigger words ({len(version['trainedWords'])}):")
                    for word in version['trainedWords']:
                        print(f"    - {word}")
                else:
                    print(f"  Trigger words: None")
                
                print()
            
            # Version matching analysis
            print_separator("🔍 VERSION MATCHING ANALYSIS")
            
            if scraped_data['currentVersionId']:
                print(f"\nURL specified version ID: {scraped_data['currentVersionId']}")
                
                # Find matching version
                matching_version = None
                for v in versions:
                    if v['id'] == scraped_data['currentVersionId']:
                        matching_version = v
                        break
                
                if matching_version:
                    print(f"✅ MATCH FOUND!")
                    print(f"   Matched to: {matching_version['name']}")
                    print(f"   Status: {matching_version['status']}")
                else:
                    print(f"❌ NO MATCH FOUND")
                    print(f"   The version ID from URL ({scraped_data['currentVersionId']}) ")
                    print(f"   does not match any scraped versions.")
                    print(f"\n   Available version IDs:")
                    for v in versions:
                        print(f"     - {v['id']} ({v['name']})")
            else:
                print("\n⚠️  No version ID in URL (using default/latest)")
        else:
            print("  ❌ No versions found!")
        
        # Display raw JSON
        print_separator("📄 Raw JSON Output")
        print("\nComplete scraped data structure:\n")
        print(json.dumps(scraped_data, indent=2, ensure_ascii=False))
        
        # Activity log
        print_separator("📊 Activity Log")
        activities = service.get_activity_log()
        if activities:
            for activity in activities:
                status_icon = "✅" if activity['status'] == 'success' else "❌"
                print(f"\n{status_icon} {activity['timestamp']}")
                print(f"   Action: {activity['action']}")
                print(f"   Model:  {activity['modelName']}")
                print(f"   Status: {activity['status']}")
                if activity['details']:
                    print(f"   Details: {activity['details']}")
        
        print_separator()
        print("\n✅ Test complete!\n")
        
    except Exception as e:
        print(f"\n❌ ERROR during scrape:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        print_separator()


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           CivitAI Scraper Test Utility                      ║
║                                                              ║
║  This utility tests CivitAI scraping and shows detailed     ║
║  information about versions and trigger words.              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Check if URL was provided as argument
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Prompt for URL
        print("Enter a CivitAI model URL:")
        print("Example: https://civitai.com/models/123456?modelVersionId=789012")
        print()
        url = input("URL: ").strip()
    
    if not url:
        print("\n❌ No URL provided. Exiting.")
        return
    
    # Clean up URL (remove quotes if pasted)
    url = url.strip('"\'')
    
    # Validate URL format
    if not url.startswith('http'):
        print(f"\n❌ Invalid URL format: {url}")
        print("   URL should start with http:// or https://")
        return
    
    if 'civitai.com' not in url:
        print(f"\n⚠️  Warning: URL doesn't contain 'civitai.com'")
        print("   This might not be a CivitAI URL")
        print()
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Cancelled.")
            return
    
    # Run the test
    test_scrape(url)


if __name__ == '__main__':
    main()