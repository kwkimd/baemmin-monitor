#!/usr/bin/env python3
"""
배민외식업광장 모니터링 + AI 제안 통합 시스템
- 10개 영역 모니터링
- 선택적 AI 문구 제안
- HTML 대시보드에 AI 제안 표시
"""

import os
import sys
import json
from pathlib import Path

# 기존 모듈 import
from main import main as monitoring_main, Config as MainConfig, SCRIPT_DIR
from html_generator import generate_html_report

SCRIPT_DIR = Path(__file__).parent.absolute()


def run_ai_analysis_if_needed(results, logger):
    """AI 분석 실행 (선택적)"""
    
    # AI 분석 여부 확인
    ai_enabled = os.environ.get('ENABLE_AI', 'false').lower() == 'true'
    
    if not ai_enabled:
        logger.info("ℹ️ AI 문구 제안 비활성화 (기본값)")
        logger.info("💡 AI 제안을 활성화하려면: set ENABLE_AI=true")
        return {}
    
    logger.info("\n" + "=" * 60)
    logger.info("🤖 Gemini AI 문구 제안 시작")
    logger.info("=" * 60)
    
    try:
        from copywriter import CopywriterAI, PerformanceDataLoader, Config as AIConfig
        from sheets_manager import GoogleSheetsManager
        import time

        # 설정 로드 (config.json의 gemini_api_key 읽기)
        AIConfig.load_config()

        if not AIConfig.GEMINI_API_KEY:
            logger.error("❌ Gemini API 키 없음. config.json의 gemini_api_key를 설정하세요.")
            return {}
        
        # AI 제안 제외 영역 (콘텐츠 특성상 카피 개선이 불필요한 영역)
        AI_EXCLUDED_AREAS = {
            '최신외식업소식', '파트너비즈니스팁', '최신장사노하우',
            '장사노하우슬롯', '이벤트혜택', '외식업광장숏츠'
        }

        # 영역별 데이터 정리
        items = results.get('items', [])
        area_data = {}

        for item in items:
            area = item.get('area', '기타')
            # AI 제외 영역 건너뜀
            if area in AI_EXCLUDED_AREAS:
                continue
            # 탭메뉴 제외
            if '[탭]' in item.get('title', ''):
                continue

            if area not in area_data:
                area_data[area] = []
            area_data[area].append(item)
        
        # 성과 데이터 로드
        try:
            sheets_manager = GoogleSheetsManager(str(AIConfig.CREDENTIALS_FILE))
            perf_loader = PerformanceDataLoader(str(AIConfig.CREDENTIALS_FILE))
            performance_data = perf_loader.load_performance_data(AIConfig.PERFORMANCE_SHEET_ID)
            logger.info(f"✅ 성과 데이터 {len(performance_data)}개 로드")
        except Exception as e:
            logger.warning(f"⚠️ 성과 데이터 로드 실패: {e}")
            performance_data = {}
        
        # AI 분석
        ai = CopywriterAI(AIConfig.GEMINI_API_KEY)
        ai.set_performance_data(performance_data)
        
        ai_results = {}
        total_analyzed = 0
        
        for area, items_list in area_data.items():
            logger.info(f"  📌 [{area}] 분석 중...")
            area_results = []
            
            for item in items_list[:10]:  # 영역당 최대 10개 (메인배너 7~8개 커버)
                title = item.get('title', '')
                
                if not title:
                    continue
                
                try:
                    analysis = ai.analyze_title(area, title)
                    area_results.append({
                        'original_title': title,
                        'analysis': analysis
                    })
                    total_analyzed += 1
                    logger.info(f"    ✓ {title[:40]}...")
                    time.sleep(1.5)  # API 제한 고려
                except Exception as e:
                    logger.warning(f"    ⚠️ 분석 실패: {e}")
            
            if area_results:
                ai_results[area] = area_results
        
        excluded_count = len(AI_EXCLUDED_AREAS)
        logger.info(f"✅ AI 분석 완료: {total_analyzed}개 항목 (제외 영역 {excluded_count}개)")
        
        # JSON 저장
        ai_output_dir = SCRIPT_DIR / 'ai_suggestions'
        ai_output_dir.mkdir(exist_ok=True)
        
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))
        now_kst = datetime.now(KST)
        
        json_file = ai_output_dir / f"suggestions_{now_kst.strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(ai_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 AI 제안 저장: {json_file}")
        
        return ai_results
        
    except ImportError:
        logger.warning("⚠️ copywriter.py 모듈이 없습니다. AI 제안 건너뜀.")
        return {}
    except Exception as e:
        logger.error(f"❌ AI 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    """통합 메인 함수"""
    
    import logging
    from datetime import datetime, timezone, timedelta
    
    # 로거 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger()
    
    logger.info("🚀 AI 통합 모니터링 시스템 시작")

    # GitHub 설정 로드 (upload_with_version에서 필요)
    MainConfig.load_config()

    # 최신 results 파일 찾기
    logs_dir = SCRIPT_DIR / 'logs'
    result_files = sorted(logs_dir.glob('results_*.json'), reverse=True)
    
    if not result_files:
        logger.warning("⚠️ 기존 모니터링 결과가 없습니다. 먼저 모니터링을 실행합니다...")
        monitoring_main()
        result_files = sorted(logs_dir.glob('results_*.json'), reverse=True)
        
        if not result_files:
            logger.error("❌ 모니터링 결과를 찾을 수 없습니다")
            return 1
    else:
        logger.info("✅ 기존 모니터링 결과를 사용합니다")
    
    # 최신 결과 로드
    logger.info(f"📂 결과 파일: {result_files[0].name}")
    with open(result_files[0], 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # AI 분석 실행 (선택적)
    ai_suggestions = run_ai_analysis_if_needed(results, logger)
    
    # AI 제안 통합 여부 확인
    logger.info(f"\n📊 AI 제안 데이터: {len(ai_suggestions)}개 영역")
    if ai_suggestions:
        for area, items in ai_suggestions.items():
            logger.info(f"  - {area}: {len(items)}개 항목")
    
    # HTML 재생성 (AI 제안 포함 또는 미포함)
    logger.info("\n📄 HTML 리포트 생성 중...")
    
    try:
        from html_generator import generate_html_report
        from main import GitHubUploader
        
        # 버전 목록 로드 (GitHub)
        version_list = []
        if MainConfig.GITHUB_TOKEN and MainConfig.GITHUB_REPO:
            try:
                uploader = GitHubUploader(MainConfig.GITHUB_TOKEN, MainConfig.GITHUB_REPO, logger)
                version_list = uploader.get_version_list()
            except:
                pass
        
        # HTML 생성 (AI 제안 포함)
        html_content = generate_html_report(results, version_list, ai_suggestions, github_repo=MainConfig.GITHUB_REPO)
        
        # 로컬 저장
        html_path = SCRIPT_DIR / 'report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        if ai_suggestions:
            logger.info(f"✅ AI 제안 포함 HTML 저장: {html_path}")
        else:
            logger.info(f"✅ HTML 저장 (AI 제안 없음): {html_path}")
        
        # GitHub 업로드 (AI 제안 포함)
        if MainConfig.GITHUB_TOKEN and MainConfig.GITHUB_REPO:
            uploader = GitHubUploader(MainConfig.GITHUB_TOKEN, MainConfig.GITHUB_REPO, logger)
            uploader.upload_with_version(results, html_content, ai_suggestions)
            logger.info("✅ GitHub Pages 업로드 완료 (AI 제안 포함)")
        
    except Exception as e:
        logger.error(f"❌ HTML 생성 오류: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n🎉 모든 작업 완료!")

    # Slack 최종 완료 요약 알림
    try:
        slack_webhook = ''
        config_path = SCRIPT_DIR / 'config.json'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as _f:
                _cfg = json.load(_f)
                slack_webhook = _cfg.get('slack_webhook_url', '')

        if slack_webhook:
            from slack_notifier import SlackNotifier
            dashboard_url = ''
            if MainConfig.GITHUB_REPO:
                owner, repo_name = MainConfig.GITHUB_REPO.split('/', 1)
                dashboard_url = f"https://{owner}.github.io/{repo_name}/"
            SlackNotifier(slack_webhook).notify_summary(results, ai_suggestions, dashboard_url)
            logger.info("📨 Slack 완료 요약 알림 전송")
    except Exception as e:
        logger.warning(f"⚠️ Slack 알림 실패: {e}")

    return 0


if __name__ == '__main__':
    exit(main())
