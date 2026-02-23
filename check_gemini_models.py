#!/usr/bin/env python3
"""
Gemini API 사용 가능 모델 확인 스크립트
"""

import google.generativeai as genai

# API 키 설정
API_KEY = 'AIzaSyBu-j8yELkteVbv0GRtnKR9xeT0XCvkgPM'
genai.configure(api_key=API_KEY)

print("=" * 60)
print("🤖 Gemini API - 사용 가능한 모델 목록")
print("=" * 60)
print()

# 사용 가능한 모델 목록 출력
models = []
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        models.append(m.name)
        print(f"✅ {m.name}")

print()
print("=" * 60)
print(f"총 {len(models)}개 모델 사용 가능")
print("=" * 60)
print()

# 추천 모델
print("💡 추천 모델:")
print()

flash_models = [m for m in models if 'flash' in m.lower()]
pro_models = [m for m in models if 'pro' in m.lower()]

if flash_models:
    print("⚡ Flash 계열 (빠르고 저렴):")
    for m in flash_models:
        print(f"  - {m}")
    print()

if pro_models:
    print("🎯 Pro 계열 (고성능):")
    for m in pro_models:
        print(f"  - {m}")
    print()

# 가장 최신 모델 추천
print("🌟 권장 모델:")
if flash_models:
    print(f"  빠른 분석용: {flash_models[-1]}")
if pro_models:
    print(f"  깊은 분석용: {pro_models[-1]}")

print()
print("=" * 60)
