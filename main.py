#!/usr/bin/env python3
"""
배민외식업광장 슬롯 모니터링 시스템
GitHub Actions 버전 - Selenium + Stealth 설정
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from sheets_manager import GoogleSheetsManager

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))


# ============================================================
# 설정
# ============================================================
class Config:
    """설정 클래스"""
    
    TARGET_URL = os.getenv('TARGET_URL', 'https://ceo.baemin.com')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')
    
    PAGE_LOAD_TIMEOUT = 45
    ELEMENT_WAIT_TIMEOUT = 20
    
    SCREENSHOTS_DIR = Path('screenshots')
    LOGS_DIR = Path('logs')
    
    SLOT_SELECTORS = {
        'main_banner': '.main-banner, .banner, [class*="banner"], [class*="slide"], [class*="hero"]',
        'content_cards': '.card, .content-card, [class*="card"], [class*="article"], [class*="post"]',
        'menu_items': '.menu-item, .nav-item, [class*="menu"], [class*="nav"]',
        'links': 'a[href]',
        'images': 'img[src]',
        'sections': 'section, [class*="section"], [class*="container"]',
    }


# ============================================================
# 로깅 설정
# ============================================================
def setup_logging():
    """로깅 설정"""
    Config.LOGS_DIR.mkdir(exist_ok=True)
    
    now_kst = datetime.now(KST)
    log_filename = Config.LOGS_DIR / f"monitor_{now_kst.strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


# ============================================================
# 브라우저 설정 (Selenium + Stealth 설정)
# ============================================================
def create_browser(logger):
    """Selenium 브라우저 생성 (봇 탐지 우회 설정)"""
    
    logger.info("🚀 브라우저 시작 중...")
    
    options = Options()
    
    # 헤드리스 모드
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # 창 크기
    options.add_argument('--window-size=1920,1080')
    
    # 봇 탐지 우회 설정
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent (실제 Chrome과 동일)
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/130.0.0.0 Safari/537.36'
    )
    
    # 언어 설정
    options.add_argument('--lang=ko-KR')
    options.add_experimental_option('prefs', {
        'intl.accept_languages': 'ko-KR,ko,en-US,en',
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False
    })
    
    # 추가 우회 설정
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--ignore-certificate-errors')
    
    try:
        # ChromeDriver 경로 (GitHub Actions에서 자동 설정됨)
        driver = webdriver.Chrome(options=options)
        
        # JavaScript로 webdriver 속성 숨기기
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });
                window.chrome = {
                    runtime: {}
                };
            '''
        })
        
        driver.set_page_load_timeout(Config.PAGE_LOAD_TIMEOUT)
        
        logger.info("✅ 브라우저 시작 완료")
        return driver
        
    except Exception as e:
        logger.error(f"❌ 브라우저 생성 실패: {e}")
        raise


# ============================================================
# 모니터링 클래스
# ============================================================
class BaeminMonitor:
    """배민외식업광장 모니터링 클래스"""
    
    def __init__(self, logger):
        self.logger = logger
        self.driver = None
        now_kst = datetime.now(KST)
        self.results = {
            'timestamp': now_kst.isoformat(),
            'date': now_kst.strftime('%Y-%m-%d'),
            'time': now_kst.strftime('%H:%M:%S'),
            'url': Config.TARGET_URL,
            'status': 'pending',
            'access_status': 'unknown',
            'slots': [],
            'broken_links': [],
            'total_slots': 0,
            'total_links': 0,
            'broken_link_count': 0,
            'errors': []
        }
    
    def start(self):
        """브라우저 시작"""
        self.driver = create_browser(self.logger)
    
    def stop(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.logger.info("🛑 브라우저 종료")
    
    def load_page(self):
        """페이지 로드"""
        self.logger.info(f"📄 페이지 로드 중: {Config.TARGET_URL}")
        
        try:
            self.driver.get(Config.TARGET_URL)
            
            # Cloudflare 체크 대기
            self.logger.info("⏳ 페이지 로딩 대기 중...")
            time.sleep(10)
            
            # 페이지 로드 대기
            WebDriverWait(self.driver, Config.ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            # 추가 대기
            time.sleep(3)
            
            # 접근 상태 확인
            page_source = self.driver.page_source.lower()
            page_title = self.driver.title
            
            self.logger.info(f"📋 페이지 제목: {page_title}")
            
            # 차단 여부 확인
            blocked_keywords = ['보안', '차단', 'blocked', 'access denied', '접근 제한']
            is_blocked = any(kw in page_source for kw in blocked_keywords)
            
            if is_blocked and '외식업' not in page_source:
                self.logger.warning("⚠️ 접근이 차단된 것 같습니다")
                self.results['access_status'] = 'blocked'
            else:
                self.logger.info("✅ 페이지 접근 성공!")
                self.results['access_status'] = 'success'
            
            # 스크롤 다운
            self._scroll_page()
            
            self.logger.info("✅ 페이지 로드 완료")
            return True
            
        except TimeoutException:
            self.logger.error("❌ 페이지 로드 타임아웃")
            self.results['errors'].append('Page load timeout')
            self.results['access_status'] = 'timeout'
            return False
        except Exception as e:
            self.logger.error(f"❌ 페이지 로드 오류: {e}")
            self.results['errors'].append(f'Page load error: {str(e)}')
            self.results['access_status'] = 'error'
            return False
    
    def _scroll_page(self):
        """페이지 스크롤"""
        try:
            total_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            
            for i in range(0, min(total_height, 5000), 500):
                self.driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(0.5)
            
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            self.logger.warning(f"⚠️ 스크롤 오류: {e}")
    
    def extract_slots(self):
        """슬롯 정보 추출"""
        self.logger.info("🔍 슬롯 정보 추출 중...")
        
        slots = []
        slot_index = 1
        
        for slot_type, selector in Config.SLOT_SELECTORS.items():
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for elem in elements[:20]:
                    try:
                        text = elem.text.strip() if elem.text else ''
                        
                        if len(text) < 2:
                            continue
                        
                        slot_info = {
                            'index': f'S{slot_index:02d}',
                            'type': slot_type,
                            'text': text[:100],
                            'tag': elem.tag_name,
                            'visible': elem.is_displayed(),
                        }
                        
                        if elem.tag_name == 'a':
                            slot_info['href'] = elem.get_attribute('href') or ''
                        
                        if elem.tag_name == 'img':
                            slot_info['src'] = elem.get_attribute('src') or ''
                            slot_info['alt'] = elem.get_attribute('alt') or ''
                        
                        slots.append(slot_info)
                        slot_index += 1
                        
                    except Exception as e:
                        self.logger.debug(f"요소 처리 오류: {e}")
                        
            except Exception as e:
                self.logger.debug(f"선택자 '{selector}' 오류: {e}")
        
        self.results['slots'] = slots
        self.results['total_slots'] = len(slots)
        self.logger.info(f"✅ {len(slots)}개 슬롯 추출 완료")
    
    def check_links(self):
        """링크 상태 확인"""
        self.logger.info("🔗 링크 상태 확인 중...")
        
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href]')
            checked_urls = set()
            broken_links = []
            
            for link in links[:30]:
                try:
                    url = link.get_attribute('href')
                    
                    if not url or url in checked_urls:
                        continue
                    
                    if url.startswith('javascript:') or url.startswith('#') or url.startswith('mailto:'):
                        continue
                    
                    checked_urls.add(url)
                    
                    try:
                        response = requests.head(
                            url, 
                            timeout=10, 
                            allow_redirects=True,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            }
                        )
                        
                        if response.status_code >= 400:
                            broken_links.append({
                                'url': url,
                                'status_code': response.status_code,
                                'text': link.text[:50] if link.text else ''
                            })
                            self.logger.warning(f"⚠️ 깨진 링크: {url} ({response.status_code})")
                            
                    except requests.RequestException as e:
                        pass
                        
                except Exception as e:
                    self.logger.debug(f"링크 처리 오류: {e}")
            
            self.results['total_links'] = len(checked_urls)
            self.results['broken_links'] = broken_links
            self.results['broken_link_count'] = len(broken_links)
            
            self.logger.info(f"✅ 링크 확인 완료: {len(checked_urls)}개 중 {len(broken_links)}개 깨짐")
            
        except Exception as e:
            self.logger.error(f"❌ 링크 확인 오류: {e}")
            self.results['errors'].append(f'Link check error: {str(e)}')
    
    def take_screenshot(self):
        """스크린샷 저장"""
        Config.SCREENSHOTS_DIR.mkdir(exist_ok=True)
        
        now_kst = datetime.now(KST)
        filename = Config.SCREENSHOTS_DIR / f"screenshot_{now_kst.strftime('%Y%m%d_%H%M%S')}.png"
        
        try:
            self.driver.save_screenshot(str(filename))
            self.logger.info(f"📸 스크린샷 저장: {filename}")
            self.results['screenshot'] = str(filename)
        except Exception as e:
            self.logger.error(f"❌ 스크린샷 오류: {e}")
    
    def get_page_info(self):
        """페이지 기본 정보 수집"""
        try:
            self.results['page_title'] = self.driver.title
            self.results['current_url'] = self.driver.current_url
        except Exception as e:
            self.logger.warning(f"⚠️ 페이지 정보 수집 오류: {e}")
    
    def run(self):
        """모니터링 실행"""
        try:
            self.start()
            
            if self.load_page():
                self.get_page_info()
                self.take_screenshot()
                
                if self.results['access_status'] == 'success':
                    self.extract_slots()
                    self.check_links()
                    self.results['status'] = 'success'
                else:
                    self.results['status'] = 'blocked'
            else:
                self.results['status'] = 'failed'
                self.take_screenshot()
            
        except Exception as e:
            self.logger.error(f"❌ 모니터링 오류: {e}")
            self.results['status'] = 'error'
            self.results['errors'].append(str(e))
            
        finally:
            self.stop()
        
        return self.results


# ============================================================
# Google Sheets 저장
# ============================================================
def save_to_sheets(results, logger):
    """결과를 Google Sheets에 저장"""
    
    if not Config.SPREADSHEET_ID:
        logger.warning("⚠️ SPREADSHEET_ID가 설정되지 않음")
        return False
    
    try:
        sheets = GoogleSheetsManager(Config.SPREADSHEET_ID)
        
        row_data = [
            results['date'],
            results['time'],
            results.get('page_title', ''),
            results['status'],
            results.get('access_status', 'unknown'),
            results['total_slots'],
            results['total_links'],
            results['broken_link_count'],
            ', '.join([bl['url'] for bl in results['broken_links'][:5]]),
            ', '.join(results['errors'][:3]) if results['errors'] else '',
        ]
        
        for i, slot in enumerate(results['slots'][:10]):
            row_data.extend([
                slot.get('type', ''),
                slot.get('text', '')[:50],
            ])
        
        sheets.append_row(row_data)
        logger.info("✅ Google Sheets 저장 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ Google Sheets 저장 오류: {e}")
        return False


# ============================================================
# 결과 요약
# ============================================================
def print_summary(results, logger):
    """결과 요약 출력"""
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 모니터링 결과 요약")
    logger.info("=" * 60)
    logger.info(f"📅 날짜: {results['date']} {results['time']} (KST)")
    logger.info(f"🌐 URL: {results['url']}")
    logger.info(f"🔓 접근: {results.get('access_status', 'unknown')}")
    logger.info(f"📋 상태: {results['status']}")
    logger.info(f"📄 제목: {results.get('page_title', 'N/A')}")
    logger.info(f"📦 슬롯 수: {results['total_slots']}")
    logger.info(f"🔗 링크 수: {results['total_links']}")
    logger.info(f"💔 깨진 링크: {results['broken_link_count']}")
    
    if results['errors']:
        logger.info("\n❌ 오류:")
        for err in results['errors']:
            logger.info(f"  - {err}")
    
    logger.info("=" * 60 + "\n")


# ============================================================
# 메인
# ============================================================
def main():
    """메인 함수"""
    
    logger = setup_logging()
    
    now_kst = datetime.now(KST)
    logger.info("🎯 배민외식업광장 모니터링 시작")
    logger.info(f"📅 실행 시간 (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🌐 대상 URL: {Config.TARGET_URL}")
    
    monitor = BaeminMonitor(logger)
    results = monitor.run()
    
    print_summary(results, logger)
    save_to_sheets(results, logger)
    
    # JSON 저장
    now_kst = datetime.now(KST)
    results_file = Config.LOGS_DIR / f"results_{now_kst.strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    return 0 if results['status'] == 'success' else 1


if __name__ == '__main__':
    exit(main())
