#!/usr/bin/env python3
"""
배민외식업광장 AI 문구 제안 시스템 - 최적화 버전
- Gemini 1.5 Flash (안정, 무료 할당량 많음)
- 짧은 프롬프트 (토큰 절약)
- 필수 정보만 포함
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import google.generativeai as genai
from sheets_manager import GoogleSheetsManager

KST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).parent.absolute()


class Config:
    GEMINI_API_KEY = 'AIzaSyBu-j8yELkteVbv0GRtnKR9xeT0XCvkgPM'
    MONITORING_SHEET_ID = ''
    PERFORMANCE_SHEET_ID = '1AISTFsSGHFr9QXVdrX_lLey0oqwa3Eo5umTMaAKAWFQ'
    CONFIG_FILE = SCRIPT_DIR / 'config.json'
    CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
    OUTPUT_DIR = SCRIPT_DIR / 'copywriting_reports'
    
    @classmethod
    def load_config(cls):
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cls.MONITORING_SHEET_ID = config.get('spreadsheet_id', '')


class PerformanceDataLoader:
    def __init__(self, credentials_path):
        # spreadsheet_id는 더미값 사용 (read_range 호출 시 실제 ID를 직접 전달)
        self.sheets = GoogleSheetsManager(spreadsheet_id='_dummy_', sheet_name='모니터링로그')
    
    def load_performance_data(self, spreadsheet_id):
        try:
            if not hasattr(self.sheets, 'read_range'):
                return {}
            data = self.sheets.read_range(spreadsheet_id, 'A1:Z1000')
            if not data or len(data) < 2:
                return {}
            performance = {}
            for row in data[1:]:
                if len(row) < 3:
                    continue
                try:
                    area = row[1] if len(row) > 1 else ''
                    title = row[2] if len(row) > 2 else ''
                    impressions = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                    clicks = int(row[4]) if len(row) > 4 and row[4].isdigit() else 0
                    if title and (impressions > 0 or clicks > 0):
                        key = f"{area}_{title}"
                        performance[key] = {
                            'area': area, 'title': title,
                            'impressions': impressions, 'clicks': clicks,
                            'ctr': (clicks / impressions * 100) if impressions > 0 else 0
                        }
                except:
                    continue
            return performance
        except Exception as e:
            print(f"⚠️ 성과 데이터 로드 실패: {e}")
            return {}


class CopywriterAI:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # Gemini 2.5 Pro - RPD 1,500회 + TPM 무제한
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.performance_data = {}
        print("✅ 모델: gemini-2.5-pro (RPD: 1,500회, TPM: 무제한)")
    
    def set_performance_data(self, performance_data):
        self.performance_data = performance_data
    
    def analyze_title(self, area, title):
        # 성과 데이터가 있으면 프롬프트에 포함
        perf_info = ""
        if self.performance_data:
            key = f"{area}_{title}"
            perf = self.performance_data.get(key)
            if perf:
                ctr = perf.get('ctr', 0)
                impressions = perf.get('impressions', 0)
                clicks = perf.get('clicks', 0)
                perf_info = f"\n현재 성과: 노출 {impressions}회, 클릭 {clicks}회, CTR {ctr:.1f}%"

        prompt = f"""배민 사장님용 {area} 제목 개선:
"{title}"{perf_info}

3가지 제안해줘 (각각 이유 포함). JSON만:
{{"analysis":"간단분석","suggestions":[{{"title":"제목","reason":"이유","score":8.5}}]}}"""
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(result_text)
            return result
        except Exception as e:
            print(f"❌ AI 오류 ({title[:20]}...): {e}")
            return {'analysis': f'오류: {str(e)}', 'suggestions': []}
    
    def analyze_all_areas(self, monitoring_data):
        results = {}
        for area, items in monitoring_data.items():
            print(f"\n📌 [{area}] 분석 중...")
            area_results = []
            
            # 영역당 최대 3개만 (할당량 절약)
            for item in items[:3]:
                title = item.get('title', '')
                if not title or '[탭]' in title:
                    continue
                
                print(f"  - {title[:30]}...")
                analysis = self.analyze_title(area, title)
                area_results.append({
                    'original_title': title,
                    'analysis': analysis
                })
                time.sleep(2)  # 할당량 보호
            
            if area_results:
                results[area] = area_results
        
        return results


def load_monitoring_data(sheets_manager, spreadsheet_id):
    """최신 모니터링 데이터 가져오기 (logs 폴더에서)"""
    try:
        # logs 폴더에서 최신 results 파일 읽기
        logs_dir = SCRIPT_DIR / 'logs'
        result_files = sorted(logs_dir.glob('results_*.json'), reverse=True)
        
        if not result_files:
            print("❌ logs 폴더에 results 파일이 없습니다")
            print("   먼저 모니터링실행.bat을 실행하세요")
            return {}
        
        print(f"✅ 모니터링 결과: {result_files[0].name}")
        
        with open(result_files[0], 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        # items를 영역별로 그룹화
        items = results.get('items', [])
        area_data = {}
        
        for item in items:
            area = item.get('area', '기타')
            title = item.get('title', '')
            
            if area not in area_data:
                area_data[area] = []
            
            area_data[area].append({'title': title})
        
        return area_data
        
    except Exception as e:
        print(f"❌ 데이터 로드 오류: {e}")
        return {}


def generate_html_report(results, timestamp):
    area_sections = ""
    for area, items in results.items():
        if not items:
            continue
        items_html = ""
        for item in items:
            original = item['original_title']
            analysis = item['analysis']
            suggestions_html = ""
            for i, sug in enumerate(analysis.get('suggestions', []), 1):
                suggestions_html += f'''
                <div class="sug">
                    <div class="sug-h"><span>제안 {i}</span><span>★ {sug.get('score', 0)}</span></div>
                    <div class="sug-t">{sug.get('title', '')}</div>
                    <div class="sug-r">{sug.get('reason', '')}</div>
                </div>'''
            items_html += f'''
            <div class="item">
                <div class="orig"><strong>원본:</strong> {original}</div>
                <div class="anal"><strong>분석:</strong> {analysis.get('analysis', '')}</div>
                <div class="sugs">{suggestions_html}</div>
            </div>'''
        area_sections += f'''<div class="area"><h2>{area}</h2>{items_html}</div>'''
    
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>배민 AI 제안</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}}.container{{max-width:1200px;margin:0 auto}}.header{{background:#fff;border-radius:20px;padding:30px;margin-bottom:20px;box-shadow:0 10px 40px rgba(0,0,0,0.1)}}.header h1{{font-size:28px;color:#333}}.area{{background:#fff;border-radius:15px;padding:25px;margin-bottom:20px}}.area h2{{color:#667eea;border-bottom:2px solid #667eea;padding-bottom:10px;margin-bottom:20px}}.item{{background:#f8f9fa;border-radius:10px;padding:20px;margin-bottom:20px}}.orig,.anal{{padding:10px;margin-bottom:10px;background:#fff;border-radius:5px}}.sugs{{display:grid;gap:15px}}.sug{{background:#fff;border-radius:8px;padding:15px;border:2px solid #667eea}}.sug-h{{display:flex;justify-content:space-between;margin-bottom:10px}}.sug-t{{font-weight:700;margin-bottom:8px}}.sug-r{{font-size:13px;color:#666}}</style>
</head><body><div class="container">
<div class="header"><h1>🎯 배민 AI 문구 제안</h1><p>{timestamp}</p></div>
{area_sections}</div></body></html>'''


def main():
    print("🎯 배민 AI 문구 제안 (최적화)")
    Config.load_config()
    Config.OUTPUT_DIR.mkdir(exist_ok=True)
    
    if not Config.CREDENTIALS_FILE.exists():
        print("❌ credentials.json 없음")
        return
    
    sheets_manager = GoogleSheetsManager(str(Config.CREDENTIALS_FILE))
    
    print("\n📥 데이터 로드...")
    monitoring_data = load_monitoring_data(sheets_manager, Config.MONITORING_SHEET_ID)
    if not monitoring_data:
        print("❌ 데이터 없음")
        return
    
    print(f"✅ {len(monitoring_data)}개 영역")
    
    print("\n🤖 AI 분석 (영역당 최대 3개)...")
    ai = CopywriterAI(Config.GEMINI_API_KEY)
    results = ai.analyze_all_areas(monitoring_data)
    
    print("\n📄 리포트 생성...")
    now_kst = datetime.now(KST)
    timestamp = now_kst.strftime('%Y-%m-%d %H:%M:%S')
    html = generate_html_report(results, timestamp)
    
    filename = Config.OUTPUT_DIR / f"ai_suggestions_{now_kst.strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 저장: {filename}")
    
    json_filename = Config.OUTPUT_DIR / f"ai_suggestions_{now_kst.strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON: {json_filename}")
    
    print("\n🎉 완료!")
    return 0


if __name__ == '__main__':
    exit(main())
