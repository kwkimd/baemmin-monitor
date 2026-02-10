#!/usr/bin/env python3
"""
배민외식업광장 슬롯 모니터링 시스템
GitHub Actions 버전 - 쿠키 로그인 지원
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from sheets_manager import GoogleSheetsManager


# ============================================================
# 설정
# ============================================================
class Config:
    """설정 클래스 - 환경변수에서 읽어옴"""
    
    # 모니터링 대상 URL
    TARGET_URL = os.getenv(
        'TARGET_URL', 
        'https://ceo.baemin.com'
    )
    
    # Google Sheets ID
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')
    
    # 쿠키 (환경변수에서 JSON 문자열로)
    COOKIES_JSON = os.getenv('BAEMIN_COOKIES', '')
    
    # 타임아웃 설정
    PAGE_LOAD_TIMEOUT = 30
    ELEMENT_WAIT_TIMEOUT = 15
    
    # 폴더 설정
    SCREENSHOTS_DIR = Path('screenshots')
    LOGS_DIR = Path('logs')
    
    # 슬롯 CSS 선택자 (배민외식업광장에 맞게 조정)
    SLOT_SELECTORS = {
        'main_banner': '.main-banner, .banner, [class*="banner"], [class*="slide"]',
        'content_cards': '.card, .content-card, [class*="card"], [class*="article"]',
        'menu_items': '.menu-item, .nav-item, [class*="menu"], [class*="nav"]',
        'links': 'a[href]',
        'images': 'img[src]',
        'sections': 'section, [class*="section"]',
    }


# ============================================================
# 로깅 설정
# ============================================================
def setup_logging():
    """로깅 설정"""
    Config.LOGS_DIR.mkdir(exist_ok=True)
    
    log_filename = Config.LOGS_DIR / f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
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
# 브라우저 설정
# ============================================================
def create_browser():
    """Selenium 브라우저 생성 (GitHub Actions용 헤드리스)"""
    
    options = Options()
    
    # 헤드리스 모드
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # 창 크기 설정
    options.add_argument('--window-size=1920,1080')
    
    # 봇 탐지 우회
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent 설정 (실제 브라우저처럼)
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
    
    # 언어 설정
    options.add_argument('--lang=ko-KR')
    options.add_experimental_option('prefs', {
        'intl.accept_languages': 'ko-KR,ko,en-US,en'
    })
    
    # ChromeDriver 자동 관리
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 봇 탐지 우회 스크립트
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        '''
    })
    
    driver.set_page_load_timeout(Config.PAGE_LOAD_TIMEOUT)
    
    return driver


# ============================================================
# 쿠키 로드
# ============================================================
def load_cookies(driver, logger):
    """환경변수에서 쿠키 로드하여 브라우저에 추가"""
    
    if not Config.COOKIES_JSON:
        logger.warning("⚠️ BAEMIN_COOKIES 환경변수가 설정되지 않음")
        return False
    
    try:
        cookies = json.loads(Config.COOKIES_JSON)
        logger.info(f"📦 {len(cookies)}개의 쿠키 로드 중...")
        
        # 먼저 도메인에 접속해야 쿠키 설정 가능
        driver.get("https://ceo.baemin.com")
        time.sleep(2)
        
        # 쿠키 추가
        for cookie in cookies:
            try:
                cookie_dict = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', '.baemin.com'),
                }
                
                # 선택적 필드
                if 'path' in cookie:
                    cookie_dict['path'] = cookie['path']
                else:
                    cookie_dict['path'] = '/'
                    
                if 'secure' in cookie:
                    cookie_dict['secure'] = cookie['secure']
                    
                if 'httpOnly' in cookie:
                    cookie_dict['httpOnly'] = cookie['httpOnly']
                
                driver.add_cookie(cookie_dict)
                logger.debug(f"  ✓ 쿠키 추가: {cookie['name']}")
                
            except Exception as e:
                logger.warning(f"  ⚠️ 쿠키 추가 실패 ({cookie.get('name', 'unknown')}): {e}")
        
        logger.info("✅ 쿠키 로드 완료")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ 쿠키 JSON 파싱 오류: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ 쿠키 로드 오류: {e}")
        return False


# ============================================================
# 모니터링 클래스
# ============================================================
class BaeminMonitor:
    """배민외식업광장 모니터링 클래스"""
    
    def __init__(self, logger):
        self.logger = logger
        self.driver = None
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'url': Config.TARGET_URL,
            'status': 'pending',
            'login_status': 'unknown',
            'slots': [],
            'broken_links': [],
            'total_slots': 0,
            'total_links': 0,
            'broken_link_count': 0,
            'errors': []
        }
    
    def start(self):
        """브라우저 시작"""
        self.logger.info("🚀 브라우저 시작 중...")
        self.driver = create_browser()
        self.logger.info("✅ 브라우저 시작 완료")
    
    def stop(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            self.logger.info("🛑 브라우저 종료")
    
    def login_with_cookies(self):
        """쿠키로 로그인"""
        self.logger.info("🔐 쿠키로 로그인 시도 중...")
        
        if load_cookies(self.driver, self.logger):
            # 페이지 새로고침하여 쿠키 적용
            self.driver.refresh()
            time.sleep(3)
            
            # 로그인 상태 확인
            page_source = self.driver.page_source
            
            if '로그인' in page_source and '보안' in page_source:
                self.logger.warning("⚠️ 로그인 실패 - 여전히 로그인 페이지")
                self.results['login_status'] = 'failed'
                return False
            else:
                self.logger.info("✅ 로그인 성공!")
                self.results['login_status'] = 'success'
                return True
        else:
            self.results['login_status'] = 'no_cookies'
            return False
    
    def load_page(self):
        """페이지 로드"""
        self.logger.info(f"📄 페이지 로드 중: {Config.TARGET_URL}")
        
        try:
            self.driver.get(Config.TARGET_URL)
            
            # 페이지 로드 대기
            WebDriverWait(self.driver, Config.ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            # 추가 대기 (동적 콘텐츠 로딩)
            time.sleep(3)
            
            # 스크롤 다운 (lazy loading 처리)
            self._scroll_page()
            
            self.logger.info("✅ 페이지 로드 완료")
            return True
            
        except TimeoutException:
            self.logger.error("❌ 페이지 로드 타임아웃")
            self.results['errors'].append('Page load timeout')
            return False
        except Exception as e:
            self.logger.error(f"❌ 페이지 로드 오류: {e}")
            self.results['errors'].append(f'Page load error: {str(e)}')
            return False
    
    def _scroll_page(self):
        """페이지 스크롤 (lazy loading 처리)"""
        try:
            total_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            
            for i in range(0, total_height, 500):
                self.driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(0.3)
            
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
                        slot_info = {
                            'index': f'S{slot_index:02d}',
                            'type': slot_type,
                            'text': elem.text[:100] if elem.text else '',
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
            
            for link in links[:50]:
                try:
                    url = link.get_attribute('href')
                    
                    if not url or url in checked_urls:
                        continue
                    
                    if url.startswith('javascript:') or url.startswith('#'):
                        continue
                    
                    checked_urls.add(url)
                    
                    try:
                        response = requests.head(
                            url, 
                            timeout=10, 
                            allow_redirects=True,
                            headers={'User-Agent': 'Mozilla/5.0'}
                        )
                        
                        if response.status_code >= 400:
                            broken_links.append({
                                'url': url,
                                'status_code': response.status_code,
                                'text': link.text[:50] if link.text else ''
                            })
                            self.logger.warning(
                                f"⚠️ 깨진 링크: {url} ({response.status_code})"
                            )
                            
                    except requests.RequestException as e:
                        broken_links.append({
                            'url': url,
                            'status_code': 'ERROR',
                            'text': link.text[:50] if link.text else '',
                            'error': str(e)[:50]
                        })
                        
                except Exception as e:
                    self.logger.debug(f"링크 처리 오류: {e}")
            
            self.results['total_links'] = len(checked_urls)
            self.results['broken_links'] = broken_links
            self.results['broken_link_count'] = len(broken_links)
            
            self.logger.info(
                f"✅ 링크 확인 완료: 총 {len(checked_urls)}개 중 "
                f"{len(broken_links)}개 깨짐"
            )
            
        except Exception as e:
            self.logger.error(f"❌ 링크 확인 오류: {e}")
            self.results['errors'].append(f'Link check error: {str(e)}')
    
    def take_screenshot(self):
        """스크린샷 저장"""
        Config.SCREENSHOTS_DIR.mkdir(exist_ok=True)
        
        filename = Config.SCREENSHOTS_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
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
            
            # 쿠키로 로그인 시도
            self.login_with_cookies()
            
            if self.load_page():
                self.get_page_info()
                self.extract_slots()
                self.check_links()
                self.take_screenshot()
                self.results['status'] = 'success'
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
        logger.warning("⚠️ SPREADSHEET_ID가 설정되지 않음 - Sheets 저장 건너뜀")
        return False
    
    try:
        sheets = GoogleSheetsManager(Config.SPREADSHEET_ID)
        
        row_data = [
            results['date'],
            results['time'],
            results.get('page_title', ''),
            results['status'],
            results.get('login_status', 'unknown'),
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
# 결과 요약 출력
# ============================================================
def print_summary(results, logger):
    """결과 요약 출력"""
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 모니터링 결과 요약")
    logger.info("=" * 60)
    logger.info(f"📅 날짜: {results['date']} {results['time']}")
    logger.info(f"🌐 URL: {results['url']}")
    logger.info(f"🔐 로그인: {results.get('login_status', 'unknown')}")
    logger.info(f"📋 상태: {results['status']}")
    logger.info(f"📦 슬롯 수: {results['total_slots']}")
    logger.info(f"🔗 링크 수: {results['total_links']}")
    logger.info(f"💔 깨진 링크: {results['broken_link_count']}")
    
    if results['broken_links']:
        logger.info("\n⚠️ 깨진 링크 목록:")
        for bl in results['broken_links'][:10]:
            logger.info(f"  - {bl['url']} ({bl['status_code']})")
    
    if results['errors']:
        logger.info("\n❌ 오류 목록:")
        for err in results['errors']:
            logger.info(f"  - {err}")
    
    logger.info("=" * 60 + "\n")


# ============================================================
# 메인 실행
# ============================================================
def main():
    """메인 함수"""
    
    logger = setup_logging()
    
    logger.info("🎯 배민외식업광장 모니터링 시작")
    logger.info(f"📅 실행 시간: {datetime.now().isoformat()}")
    logger.info(f"🌐 대상 URL: {Config.TARGET_URL}")
    
    monitor = BaeminMonitor(logger)
    results = monitor.run()
    
    print_summary(results, logger)
    
    save_to_sheets(results, logger)
    
    results_file = Config.LOGS_DIR / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"📄 결과 JSON 저장: {results_file}")
    
    if results['status'] == 'success':
        logger.info("✅ 모니터링 완료!")
        return 0
    else:
        logger.error("❌ 모니터링 실패!")
        return 1


if __name__ == '__main__':
    exit(main())
