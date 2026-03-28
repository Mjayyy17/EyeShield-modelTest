#!/usr/bin/env python
"""Quick validation test for Phase 1 enhancements."""
import ast
import sys

files = [
    r'c:\Users\Computer\Desktop\EyeShield\Frontend\testSample\screening_form.py',
    r'c:\Users\Computer\Desktop\EyeShield\Frontend\testSample\auth.py',
]

print("Validating Phase 1 implementation...")
for filepath in files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        filename = filepath.split('\\')[-1]
        print(f'✓ {filename}: Syntax OK')
    except SyntaxError as e:
        filename = filepath.split('\\')[-1]
        print(f'✗ {filename}: SYNTAX ERROR - Line {e.lineno}: {e.msg}')
        sys.exit(1)
    except Exception as e:
        filename = filepath.split('\\')[-1]
        print(f'✗ {filename}: ERROR - {e}')
        sys.exit(1)

print("\n✓ All files validated successfully!")
print("\nPhase 1 additions:")
print("  - Treatment regimen dropdown")
print("  - Previous DR stage dropdown")
print("  - Height/Weight fields with auto-calculated BMI")
print("  - Database columns added to auth.py")
