#!/usr/bin/env python3
"""
Enhanced Step 4: Merge translations back into HTML with batch support
Creates final translated HTML files using either DeepL or OpenAI translations
"""

import argparse
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
import os

def load_json(file_path):
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)

def merge_translations_into_html(html_file, translations, output_file):
    """
    Merge translations back into the HTML file by replacing BLOCK_X_SX placeholders
    with enhanced error handling and reporting
    """
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: HTML file {html_file} not found")
        sys.exit(1)
    
    # Track replacements and missing translations
    replaced_count = 0
    missing_count = 0
    placeholder_pattern = re.compile(r'BLOCK_\d+_S\d+')
    found_placeholders = set(placeholder_pattern.findall(html_content))
    
    # Replace each placeholder with its translation
    for block_id in found_placeholders:
        translation = translations.get(block_id, "").strip()
        if translation:
            html_content = html_content.replace(block_id, translation)
            replaced_count += 1
        else:
            missing_count += 1
    
    # Parse and prettify the HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        print(f"  ✅ Successfully created: {output_file}")
        print(f"  📊 Merged {replaced_count} translations")
        if missing_count > 0:
            print(f"  ⚠️  Warning: {missing_count} placeholders had no translations")
        
        # Verify file was created and has content
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"  📁 File size: {file_size:,} bytes")
            return True
        else:
            print(f"  ❌ Failed to create output file: {output_file}")
            return False
        
    except Exception as e:
        print(f"  ⚠️  HTML parsing failed ({str(e)[:50]}), writing raw content")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  ✅ Raw content written to: {output_file}")
            return True
        except Exception as write_error:
            print(f"  ❌ Failed to write file: {write_error}")
            return False

def validate_translations(translations, translation_source):
    """Enhanced validation with detailed statistics"""
    if not translations:
        print(f"⚠️  Warning: No translations found in {translation_source}")
        return False
    
    total_keys = len(translations)
    non_empty = sum(1 for v in translations.values() if v and v.strip())
    empty = total_keys - non_empty
    
    print(f"\n📊 {translation_source} Statistics:")
    print(f"  Total translation keys: {total_keys}")
    print(f"  Non-empty translations: {non_empty}")
    print(f"  Empty/missing translations: {empty}")
    
    return non_empty > 0

def process_translation_set(html_path, translations_path, output_path, label):
    """Handle a single translation source with better reporting"""
    print(f"\n🔄 Processing {label} translations...")
    print(f"  📥 Source: {translations_path}")
    print(f"  📤 Target: {output_path}")
    
    # Verify input files exist
    if not os.path.exists(html_path):
        print(f"  ❌ HTML file not found: {html_path}")
        return False
    
    if not os.path.exists(translations_path):
        print(f"  ❌ Translations file not found: {translations_path}")
        return False
    
    translations = load_json(translations_path)
    if validate_translations(translations, label):
        return merge_translations_into_html(html_path, translations, output_path)
    return False

def main():
    parser = argparse.ArgumentParser(
        description="Merge translations back into HTML file with batch support",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--html", required=True, 
                       help="Path to non_translatable.html file")
    parser.add_argument("--deepl", 
                       help="Path to segments_only.json (DeepL translations)")
    parser.add_argument("--openai", 
                       help="Path to openai_translations.json (OpenAI translations)")
    parser.add_argument("--output-deepl", 
                       help="Output file for DeepL version (required if --deepl or --both)")
    parser.add_argument("--output-openai", 
                       help="Output file for OpenAI version (required if --openai or --both)")
    parser.add_argument("--both", action="store_true",
                       help="Process both translation sources")
    
    args = parser.parse_args()
    
    # Input validation
    if not any([args.deepl, args.openai, args.both]):
        print("❌ Error: Must specify at least one translation source")
        print("Use --deepl, --openai, or --both")
        sys.exit(1)
    
    if args.both and not all([args.deepl, args.openai]):
        print("❌ Error: --both requires both --deepl and --openai")
        sys.exit(1)
    
    if not Path(args.html).exists():
        print(f"❌ Error: HTML file {args.html} does not exist")
        sys.exit(1)
    
    # Validate output paths are provided
    if (args.deepl or args.both) and not args.output_deepl:
        print("❌ Error: --output-deepl is required when using --deepl or --both")
        sys.exit(1)
    
    if (args.openai or args.both) and not args.output_openai:
        print("❌ Error: --output-openai is required when using --openai or --both")
        sys.exit(1)
    
    print(f"\n{' Starting HTML Merge Process ':=^60}")
    print(f"📄 Source HTML: {args.html}")
    
    # Process translations
    results = {}
    success_count = 0
    
    if args.deepl or args.both:
        print(f"\n🌐 Processing DeepL translations...")
        success = process_translation_set(
            args.html, args.deepl, args.output_deepl, "DeepL"
        )
        results["DeepL"] = (args.output_deepl, success)
        if success:
            success_count += 1
    
    if args.openai or args.both:
        print(f"\n🤖 Processing OpenAI translations...")
        success = process_translation_set(
            args.html, args.openai, args.output_openai, "OpenAI"
        )
        results["OpenAI"] = (args.output_openai, success)
        if success:
            success_count += 1
    
    # Final report
    print(f"\n{' Final Results ':=^60}")
    for service, (output_path, success) in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        
        if success and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"{service:<8} {status} - {output_path} ({size:,} bytes)")
        else:
            print(f"{service:<8} {status} - {output_path} (file not created)")
    
    print(f"\n🎯 Summary: {success_count}/{len(results)} translations processed successfully")
    
    if success_count == 0:
        print("❌ No files were created successfully")
        sys.exit(1)
    else:
        print("✅ Process completed!")

if __name__ == "__main__":
    main()
