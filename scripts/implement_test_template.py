#!/usr/bin/env python3
"""
Test Generation Helper
Converts templates to actual tests with proper implementation.
"""

import sys
from pathlib import Path

def main():
    templates_dir = Path(__file__).parent.parent / "tests" / "generated_templates"
    
    print("Available test templates:")
    templates = list(templates_dir.glob("*.py"))
    
    for i, template in enumerate(templates, 1):
        print(f"{i}. {template.name}")
    
    choice = input("\nSelect template to implement (number): ")
    
    try:
        selected = templates[int(choice) - 1]
        print(f"\nOpening {selected.name} for implementation...")
        print("Remember to:")
        print("  1. Replace TODO comments with actual implementation")
        print("  2. Add proper test data and fixtures")
        print("  3. Include edge cases and error scenarios")
        print("  4. Run mutation testing to verify test quality")
        
        # Copy to proper test directory
        target_dir = Path(__file__).parent.parent / "tests" / "unit"
        target_path = target_dir / selected.name
        
        if target_path.exists():
            print(f"\n⚠️  {target_path} already exists!")
        else:
            import shutil
            shutil.copy(selected, target_path)
            print(f"\n✓ Copied to: {target_path}")
            
    except (ValueError, IndexError):
        print("Invalid selection")
        sys.exit(1)

if __name__ == "__main__":
    main()
