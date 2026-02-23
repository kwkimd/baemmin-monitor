#!/usr/bin/env python3
"""
배민 모니터링 + AI 통합 (강제 통합 버전)
- AI 제안을 반드시 메인 HTML에 포함
- 상세한 디버깅 로그
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).parent.absolute()
KST = timezone(timedelta(hours=9))


def main():
    import logging
    
    # 로거 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger()
    
    logger.info("=" * 60)
    logger.info("🚀 AI 통합 모니터링 시스템")
    logger.info("=" * 60)
    
    # 1. 최신 모니터링 결과 로드
    logs_dir = SCRIPT_DIR / 'logs'
    result_files = sorted(logs_dir.glob('results_*.json'), reverse=True)
    
    if not result_files:
        logger.error("❌ 모니터링 결과 없음. 먼저 모니터링실행.bat을 실행하세요.")
        return 1
    
    logger.info(f"✅ 모니터링 결과: {result_files[0].name}")
    with open(result_files[0], 'r', encoding='utf-8') as f:
        monitoring_results = json.load(f)
    
    # 2. AI 제안 결과 로드
    ai_dir = SCRIPT_DIR / 'ai_suggestions'
    ai_files = sorted(ai_dir.glob('suggestions_*.json'), reverse=True) if ai_dir.exists() else []
    
    ai_suggestions = {}
    if ai_files:
        logger.info(f"✅ AI 제안 파일: {ai_files[0].name}")
        with open(ai_files[0], 'r', encoding='utf-8') as f:
            ai_suggestions = json.load(f)
        
        # AI 데이터 확인
        logger.info(f"\n📊 AI 제안 데이터:")
        if ai_suggestions:
            for area, items in ai_suggestions.items():
                logger.info(f"  ✓ {area}: {len(items)}개")
        else:
            logger.warning("  ⚠️ AI 제안 데이터가 비어있습니다")
    else:
        logger.warning("⚠️ AI 제안 파일 없음. copywriter.py를 먼저 실행하세요.")
    
    # 3. HTML 생성
    logger.info(f"\n📄 HTML 생성 중...")
    
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from html_generator import generate_html_report
        
        # 버전 목록 (GitHub)
        version_list = []
        try:
            from main import GitHubUploader, Config as MainConfig
            
            config_file = SCRIPT_DIR / 'config.json'
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    MainConfig.GITHUB_TOKEN = config.get('github_token', '')
                    MainConfig.GITHUB_REPO = config.get('github_repo', '')
            
            if MainConfig.GITHUB_TOKEN and MainConfig.GITHUB_REPO:
                uploader = GitHubUploader(MainConfig.GITHUB_TOKEN, MainConfig.GITHUB_REPO, logger)
                version_list = uploader.get_version_list()
                logger.info(f"  ✓ GitHub 버전: {len(version_list)}개")
        except Exception as e:
            logger.warning(f"  ⚠️ GitHub 연동 스킵: {e}")
        
        # HTML 생성 (AI 포함)
        html_content = generate_html_report(
            monitoring_results, 
            version_list, 
            ai_suggestions  # AI 데이터 전달
        )
        
        # HTML에 AI 버튼이 있는지 확인
        if '💡 AI 제안 보기' in html_content:
            logger.info("  ✅ AI 제안 버튼 포함됨!")
        else:
            logger.warning("  ⚠️ AI 제안 버튼 없음")
        
        # 로컬 저장
        html_path = SCRIPT_DIR / 'report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"  ✅ 저장: {html_path}")
        
        # GitHub 업로드
        try:
            if MainConfig.GITHUB_TOKEN and MainConfig.GITHUB_REPO:
                uploader.upload_with_version(monitoring_results, html_content)
                logger.info("  ✅ GitHub Pages 업로드 완료")
        except:
            logger.warning("  ⚠️ GitHub 업로드 스킵")
        
    except Exception as e:
        logger.error(f"❌ HTML 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 완료!")
    logger.info("=" * 60)
    logger.info(f"\n📍 확인: C:\\배민모니터링\\report.html")
    
    # 최종 확인 안내
    if ai_suggestions:
        logger.info("✅ AI 제안이 포함되어 있습니다.")
        logger.info("   각 항목에서 '💡 AI 제안 보기' 버튼을 찾아보세요!")
    else:
        logger.info("⚠️ AI 제안이 없습니다.")
        logger.info("   AI 제안을 받으려면:")
        logger.info("   1. cd C:\\배민모니터링")
        logger.info("   2. python copywriter.py")
        logger.info("   3. python run_with_ai_force.py")
    
    return 0


if __name__ == '__main__':
    input("\n아무 키나 누르면 시작...")
    exit(main())
