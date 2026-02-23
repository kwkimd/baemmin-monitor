#!/usr/bin/env python3
"""
copywriter.py import 테스트
"""

import sys
from pathlib import Path

print("=" * 60)
print("copywriter.py Import Test")
print("=" * 60)

# 1. 파일 존재 확인
script_dir = Path(__file__).parent.absolute()
copywriter_path = script_dir / 'copywriter.py'

print(f"\n1. File Check:")
print(f"   Path: {copywriter_path}")
print(f"   Exists: {copywriter_path.exists()}")

if copywriter_path.exists():
    print(f"   Size: {copywriter_path.stat().st_size} bytes")

# 2. Import 테스트
print(f"\n2. Import Test:")
try:
    import copywriter
    print("   ✅ copywriter module imported successfully")
    
    # 클래스 확인
    print(f"\n3. Class Check:")
    if hasattr(copywriter, 'CopywriterAI'):
        print("   ✅ CopywriterAI class found")
    else:
        print("   ❌ CopywriterAI class NOT found")
    
    if hasattr(copywriter, 'PerformanceDataLoader'):
        print("   ✅ PerformanceDataLoader class found")
    else:
        print("   ❌ PerformanceDataLoader class NOT found")
    
    if hasattr(copywriter, 'Config'):
        print("   ✅ Config class found")
    else:
        print("   ❌ Config class NOT found")

except ImportError as e:
    print(f"   ❌ ImportError: {e}")
except Exception as e:
    print(f"   ❌ Error: {type(e).__name__}: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

# 3. 필수 라이브러리 확인
print(f"\n4. Required Libraries Check:")
required_libs = [
    'google.generativeai',
    'sheets_manager',
]

for lib in required_libs:
    try:
        __import__(lib.replace('.', '_') if '.' in lib else lib)
        print(f"   ✅ {lib}")
    except ImportError:
        print(f"   ❌ {lib} - NOT INSTALLED")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
