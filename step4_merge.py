#!/usr/bin/env python3
"""
Enhanced Step 4: Merge translations back into HTML with batch support
Now includes language-specific post-processing (lang attribute, link fixes, etc.)
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

def post_process_html(html_content, output_file, target_lang):
    """
    Apply language-specific post-processing:
    1. Update lang attribute
    2. Fix internal links
    3. Update language switcher
    4. Rename output file with language suffix
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Update HTML lang attribute
        if soup.html:
            soup.html['lang'] = target_lang
        
        # 2. Process internal links
        # 2. Process internal links
        link_pattern = re.compile(r'^(?!http|#|mailto:).*\.html$')
        for link in soup.find_all('a', href=link_pattern):
            href = link['href']
            base, *extra = href.split('?')
    
        # Only process links without language suffixes (base versions)
            if not re.search(r'-(?:fr|es|zh|en)\.html', base):
                 new_href = base.replace('.html', f'-{target_lang}.html')
                 if extra:
                     new_href += '?' + '?'.join(extra)
                 link['href'] = new_href
        
        # 3. Update language switcher
        for switcher in soup.find_all(class_='language-switcher'):
            for link in switcher.find_all('a'):
                classes = link.get('class', [])
                if 'active' in classes:
                  classes.remove('active')
        
                # More precise matching for language switcher
                href = link['href']
                # Check if this is the link for the current target language
                if (href.endswith(f'-{target_lang}.html') or 
                    (target_lang == 'en' and href.endswith('.html') and not re.search(r'-(?:fr|es|zh)\.html$', href))):
                    classes.append('active')
                    link['class'] = classes
        
        
        # 4. Generate final output path (with language suffix)
        output_path = Path(output_file)
        final_output = output_path.with_name(
            output_path.stem.replace('_FR', '') + f'-{target_lang}.html'
        )
        
        # Write directly to the final file (overwrite if exists)
        os.makedirs(final_output.parent, exist_ok=True)
        with open(final_output, 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        
        print(f"  ✓ Final output: {final_output}")
        return str(final_output)
        
    except Exception as e:
        print(f"  ✗ Post-processing failed: {str(e)}")
        return None

def merge_translations_into_html(html_file, translations, output_file, target_lang):
    """
    Merge translations into HTML and apply post-processing in one step.
    """
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: HTML file {html_file} not found")
        sys.exit(1)
    
    # Replace placeholders with translations
    replaced_count = 0
    missing_count = 0
    placeholder_pattern = re.compile(r'BLOCK_\d+_S\d+')
    found_placeholders = set(placeholder_pattern.findall(html_content))
    
    for block_id in found_placeholders:
        translation = translations.get(block_id, "").strip()
        if translation:
            html_content = html_content.replace(block_id, translation)
            replaced_count += 1
        else:
            missing_count += 1
    
    # Apply post-processing and write to final file
    final_output = post_process_html(html_content, output_file, target_lang)
    if not final_output:
        return False
    
    print(f"  📊 Merged {replaced_count} translations")
    if missing_count > 0:
        print(f"  ⚠️  Warning: {missing_count} placeholders had no translations")
    return True

def validate_translations(translations, translation_source):
    """Existing logic (unchanged)"""
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

def process_translation_set(html_path, translations_path, output_path, label, target_lang):
    """Handle a single translation source with post-processing"""
    print(f"\n🔄 Processing {label} translations...")
    translations = load_json(translations_path)
    if validate_translations(translations, label):
        return merge_translations_into_html(html_path, translations, output_path, target_lang)
    return False

def main():
    parser = argparse.ArgumentParser(
        description="Merge translations back into HTML file with batch support",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--html", required=True, help="Path to source HTML file")
    parser.add_argument("--deepl", help="Path to DeepL translations JSON")
    parser.add_argument("--openai", help="Path to OpenAI translations JSON")
    parser.add_argument("--output-deepl", help="Base output path for DeepL version")
    parser.add_argument("--output-openai", help="Base output path for OpenAI version")
    parser.add_argument("--both", action="store_true", help="Process both DeepL and OpenAI")
    parser.add_argument("--target-lang", required=True, choices=['fr', 'es', 'zh', 'en'],
                      help="Target language code for post-processing")
    
    args = parser.parse_args()
    
    # Input validation (unchanged)
    if not any([args.deepl, args.openai, args.both]):
        print("❌ Error: Must specify at least one translation source (--deepl, --openai, or --both)")
        sys.exit(1)
    
    if args.both and not all([args.deepl, args.openai]):
        print("❌ Error: --both requires both --deepl and --openai")
        sys.exit(1)
    
    if not Path(args.html).exists():
        print(f"❌ Error: HTML file {args.html} does not exist")
        sys.exit(1)
    
    if (args.deepl or args.both) and not args.output_deepl:
        print("❌ Error: --output-deepl is required when using --deepl or --both")
        sys.exit(1)
    
    if (args.openai or args.both) and not args.output_openai:
        print("❌ Error: --output-openai is required when using --openai or --both")
        sys.exit(1)
    
    # Process translations
    results = {}
    if args.deepl or args.both:
        success = process_translation_set(
            args.html, args.deepl, args.output_deepl, "DeepL", args.target_lang
        )
        results["DeepL"] = (args.output_deepl, success)
    
    if args.openai or args.both:
        success = process_translation_set(
            args.html, args.openai, args.output_openai, "OpenAI", args.target_lang
        )
        results["OpenAI"] = (args.output_openai, success)
    
    # Final report (unchanged)
    print(f"\n{' Final Results ':=^60}")
    for service, (output_path, success) in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{service:<8} {status} - {output_path}")

if __name__ == "__main__":
    main()
