#!/usr/bin/env python3
"""
배민외식업광장 AI 문구 제안 시스템 - 최적화 버전
- Gemini 2.5 Pro (안정, 무료 할당량 많음)
- 캐싱: 같은 제목은 7일간 재사용 (API 호출 절약)
- 배치 처리: 영역당 제목들을 한 번에 분석 (속도 개선)
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
    CACHE_FILE = SCRIPT_DIR / 'ai_suggestions' / 'title_cache.json'
    CACHE_TTL_DAYS = 7  # 캐시 유효기간 (일)

    @classmethod
    def load_config(cls):
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cls.MONITORING_SHEET_ID = config.get('spreadsheet_id', '')


class AICache:
    """AI 분석 결과 캐시 - 같은 제목이면 API 재호출 생략"""

    def __init__(self, cache_file: Path, ttl_days: int = 7):
        self.cache_file = cache_file
        self.ttl_days = ttl_days
        self._data = {}
        self._load()
        self._hits = 0
        self._misses = 0

    def _load(self):
        """캐시 파일에서 데이터 로드"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                print(f"  💾 캐시 로드: {len(self._data)}개 항목 ({self.cache_file.name})")
            except Exception as e:
                print(f"  ⚠️ 캐시 로드 실패: {e}")
                self._data = {}

    def _save(self):
        """캐시 데이터를 파일에 저장"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ 캐시 저장 실패: {e}")

    def get(self, area: str, title: str):
        """캐시에서 결과 조회. 만료됐거나 없으면 None 반환"""
        key = f"{area}::{title}"
        entry = self._data.get(key)
        if not entry:
            self._misses += 1
            return None

        # TTL 확인
        cached_at = entry.get('cached_at', '')
        if cached_at:
            try:
                cached_dt = datetime.fromisoformat(cached_at)
                if datetime.now(timezone.utc) - cached_dt > timedelta(days=self.ttl_days):
                    self._misses += 1
                    return None  # 만료됨
            except Exception:
                self._misses += 1
                return None

        self._hits += 1
        return entry.get('result')

    def set(self, area: str, title: str, result: dict):
        """분석 결과를 캐시에 저장"""
        key = f"{area}::{title}"
        self._data[key] = {
            'cached_at': datetime.now(timezone.utc).isoformat(),
            'result': result
        }
        self._save()

    def stats(self) -> str:
        """캐시 적중률 통계 문자열 반환"""
        total = self._hits + self._misses
        rate = (self._hits / total * 100) if total > 0 else 0
        return f"캐시 히트: {self._hits}/{total} ({rate:.0f}%)"

    def purge_expired(self):
        """만료된 캐시 항목 정리"""
        now = datetime.now(timezone.utc)
        expired_keys = []
        for key, entry in self._data.items():
            try:
                cached_dt = datetime.fromisoformat(entry.get('cached_at', ''))
                if now - cached_dt > timedelta(days=self.ttl_days):
                    expired_keys.append(key)
            except Exception:
                expired_keys.append(key)

        for key in expired_keys:
            del self._data[key]

        if expired_keys:
            self._save()
            print(f"  🗑️ 만료 캐시 {len(expired_keys)}개 정리")


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
                except Exception:
                    continue
            return performance
        except Exception as e:
            print(f"⚠️ 성과 데이터 로드 실패: {e}")
            return {}


class CopywriterAI:
    def __init__(self, api_key, cache_file=None):
        genai.configure(api_key=api_key)
        # Gemini 2.5 Pro - RPD 1,500회 + TPM 무제한
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        self.performance_data = {}

        # 캐시 초기화
        cache_path = cache_file or Config.CACHE_FILE
        self.cache = AICache(Path(cache_path), ttl_days=Config.CACHE_TTL_DAYS)
        # 만료 항목 정리
        self.cache.purge_expired()

        print("✅ 모델: gemini-2.5-pro (RPD: 1,500회, TPM: 무제한)")

    def set_performance_data(self, performance_data):
        self.performance_data = performance_data

    def _build_perf_info(self, area: str, title: str) -> str:
        """성과 데이터 문자열 생성 (프롬프트용)"""
        if not self.performance_data:
            return ""
        perf = self.performance_data.get(f"{area}_{title}")
        if not perf:
            return ""
        return (f"\n현재 성과: 노출 {perf.get('impressions', 0)}회, "
                f"클릭 {perf.get('clicks', 0)}회, CTR {perf.get('ctr', 0):.1f}%")

    def analyze_title(self, area: str, title: str) -> dict:
        """단일 제목 분석 (캐시 우선)"""
        # 캐시 확인
        cached = self.cache.get(area, title)
        if cached is not None:
            print(f"  💾 캐시 히트: {title[:25]}...")
            return cached

        perf_info = self._build_perf_info(area, title)
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
            self.cache.set(area, title, result)  # 캐시에 저장
            return result
        except Exception as e:
            print(f"❌ AI 오류 ({title[:20]}...): {e}")
            return {'analysis': f'오류: {str(e)}', 'suggestions': []}

    def analyze_batch(self, area: str, items: list) -> list:
        """
        영역 내 여러 제목을 한 번의 API 호출로 분석 (배치 처리)
        캐시 히트 항목은 API 호출 없이 바로 반환.
        """
        cached_results = []
        uncached_items = []

        for item in items:
            title = item.get('title', '')
            if not title or '[탭]' in title:
                continue
            cached = self.cache.get(area, title)
            if cached is not None:
                print(f"  💾 캐시 히트: {title[:25]}...")
                cached_results.append({'original_title': title, 'analysis': cached})
            else:
                uncached_items.append(item)

        # 모두 캐시 히트면 API 호출 불필요
        if not uncached_items:
            return cached_results

        # 배치 프롬프트 구성
        titles_block = ""
        for i, item in enumerate(uncached_items, 1):
            title = item.get('title', '')
            perf_info = self._build_perf_info(area, title)
            titles_block += f'{i}. "{title}"{perf_info}\n'

        prompt = f"""배민 사장님용 {area} 제목들을 개선해줘:

{titles_block}
각 제목마다 3가지 제안 (이유 포함). JSON만 (배열 순서는 위 번호 순):
{{"results":[{{"original":"원본제목","analysis":"간단분석","suggestions":[{{"title":"제목","reason":"이유","score":8.5}}]}}]}}"""

        print(f"  📦 배치 API 호출: {len(uncached_items)}개 제목 묶음 처리")

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            batch_result = json.loads(result_text)
            batch_results = []

            for res in batch_result.get('results', []):
                original = res.get('original', '')
                analysis = {
                    'analysis': res.get('analysis', ''),
                    'suggestions': res.get('suggestions', [])
                }
                if original:
                    self.cache.set(area, original, analysis)  # 개별 캐시 저장
                batch_results.append({'original_title': original, 'analysis': analysis})

            return cached_results + batch_results

        except Exception as e:
            print(f"❌ 배치 AI 오류: {e} → 개별 처리로 폴백")
            # 배치 실패 시 개별 호출로 폴백
            fallback_results = list(cached_results)
            for item in uncached_items:
                title = item.get('title', '')
                print(f"  - 개별 재시도: {title[:30]}...")
                analysis = self.analyze_title(area, title)
                fallback_results.append({'original_title': title, 'analysis': analysis})
                time.sleep(2)
            return fallback_results

    def analyze_all_areas(self, monitoring_data: dict) -> dict:
        """모든 영역을 배치 처리로 분석 (영역당 1회 API 호출)"""
        results = {}
        total_areas = len(monitoring_data)

        for idx, (area, items) in enumerate(monitoring_data.items(), 1):
            print(f"\n📌 [{area}] 분석 중... ({idx}/{total_areas})")

            # 영역당 최대 3개만 (할당량 절약)
            area_items = [
                item for item in items[:3]
                if item.get('title') and '[탭]' not in item.get('title', '')
            ]

            if not area_items:
                print(f"  ⚠️ 분석 가능한 제목 없음")
                continue

            # 배치 분석 (캐시 활용 + 미캐시 항목만 API 호출)
            area_results = self.analyze_batch(area, area_items)

            if area_results:
                results[area] = area_results

            # 배치가 아닌 영역 사이 간격 (여러 영역 연속 호출 시 할당량 보호)
            if idx < total_areas:
                time.sleep(1)

        print(f"\n📊 {self.cache.stats()}")
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
    print("🎯 배민 AI 문구 제안 (최적화 - 캐싱 + 배치)")
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

    print("\n🤖 AI 분석 (영역당 배치 처리, 최대 3개)...")
    api_key = Config.GEMINI_API_KEY
    # config.json에서 API 키 우선 사용
    config_path = Config.CONFIG_FILE
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            api_key = cfg.get('gemini_api_key', api_key)

    ai = CopywriterAI(api_key)
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
