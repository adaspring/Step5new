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
        
        print(f"  Merged {replaced_count} translations")
        if missing_count > 0:
            print(f"  Warning: {missing_count} placeholders had no translations")
        
    except Exception as e:
        print(f"  Warning: HTML parsing failed ({str(e)[:50]}), writing raw content")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

def validate_translations(translations, translation_source):
    """Enhanced validation with detailed statistics"""
    if not translations:
        print(f"Warning: No translations found in {translation_source}")
        return False
    
    total_keys = len(translations)
    non_empty = sum(1 for v in translations.values() if v and v.strip())
    empty = total_keys - non_empty
    
    print(f"\n{translation_source} Statistics:")
    print(f"  Total translation keys: {total_keys}")
    print(f"  Non-empty translations: {non_empty}")
    print(f"  Empty/missing translations: {empty}")
    
    return non_empty > 0

def process_translation_set(html_path, translations_path, output_path, label):
    """Handle a single translation source with better reporting"""
    print(f"\nProcessing {label} translations...")
    print(f"  Source: {translations_path}")
    print(f"  Target: {output_path}")
    
    translations = load_json(translations_path)
    if validate_translations(translations, label):
        merge_translations_into_html(html_path, translations, output_path)
        return True
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
    parser.add_argument("--output-deepl", default="final_deepl_{lang}.html",
                       help="Output filename pattern for DeepL version (use {lang} placeholder)")
    parser.add_argument("--output-openai", default="final_openai_{lang}.html",
                       help="Output filename pattern for OpenAI version (use {lang} placeholder)")
    parser.add_argument("--both", action="store_true",
                       help="Process both translation sources")
    parser.add_argument("--output-dir", default="outputs",
                       help="Base directory for output files")
    
    args = parser.parse_args()
    
    # Input validation
    if not any([args.deepl, args.openai, args.both]):
        print("Error: Must specify at least one translation source")
        print("Use --deepl, --openai, or --both")
        sys.exit(1)
    
    if args.both and not all([args.deepl, args.openai]):
        print("Error: --both requires both --deepl and --openai")
        sys.exit(1)
    
    if not Path(args.html).exists():
        print(f"Error: HTML file {args.html} does not exist")
        sys.exit(1)

    # Extract target language from HTML filename (e.g., "FR" from "file_FR.html")
    try:
        lang = Path(args.html).stem.split('_')[-1]  # Gets last underscore segment
        if not lang.isalpha() or len(lang) != 2:  # Basic language code validation
            raise ValueError
    except (IndexError, ValueError):
        lang = "XX"
        print("Warning: Could not detect language from filename, using 'XX' as fallback")
    
    # Create output structure
    subdir = os.path.basename(os.path.dirname(args.html))  # e.g., "index"
    final_output_dir = os.path.join(args.output_dir, subdir)
    os.makedirs(final_output_dir, exist_ok=True)
    
    # Format output filenames with language code
    deepl_output = os.path.join(
        final_output_dir,
        args.output_deepl.format(lang=lang)
    )
    openai_output = os.path.join(
        final_output_dir,
        args.output_openai.format(lang=lang)
    )
    
    print(f"\n{' Starting HTML Merge Process ':=^50}")
    print(f"Source HTML: {args.html}")
    print(f"Target Language: {lang}")
    print(f"Output Directory: {final_output_dir}")
    print(f"DeepL Output: {os.path.basename(deepl_output)}")
    print(f"OpenAI Output: {os.path.basename(openai_output)}")
    
    # Process translations
    results = {}
    if args.deepl or args.both:
        success = process_translation_set(
            args.html, args.deepl, deepl_output, "DeepL"
        )
        results["deepl"] = (deepl_output, success)
    
    if args.openai or args.both:
        success = process_translation_set(
            args.html, args.openai, openai_output, "OpenAI"
        )
        results["openai"] = (openai_output, success)
    
    # Final report
    print(f"\n{' Merge Results ':=^50}")
    for label, (path, success) in results.items():
        status = "SUCCESS" if success else "PARTIAL"
        size = Path(path).stat().st_size if Path(path).exists() else 0
        print(f"{label.upper():<8} {status:<8} {path} ({size:,} bytes)")
    
    print("\nProcess completed!")
