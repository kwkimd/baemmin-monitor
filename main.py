#!/usr/bin/env python3
"""
배민외식업광장 슬롯 모니터링 시스템 v3
- 10개 영역 모니터링 (플레이스홀더 추가)
- HTML 리포트 + 버전 관리
- GitHub 자동 업로드
"""

import os
import json
import time
import logging
import requests
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
# from webdriver_manager.chrome import ChromeDriverManager  # selenium-manager로 대체

from sheets_manager import GoogleSheetsManager
from html_generator import generate_html_report

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

# 스크립트 위치 기준으로 경로 설정
SCRIPT_DIR = Path(__file__).parent.absolute()


# ============================================================
# 설정
# ============================================================
class Config:
    """설정 클래스"""
    
    TARGET_URL = 'https://ceo.baemin.com'
    SPREADSHEET_ID = ''
    
    # GitHub 설정
    GITHUB_TOKEN = ''
    GITHUB_REPO = ''
    
    PAGE_LOAD_TIMEOUT = 45
    ELEMENT_WAIT_TIMEOUT = 20
    
    SCREENSHOTS_DIR = SCRIPT_DIR / 'screenshots'
    LOGS_DIR = SCRIPT_DIR / 'logs'
    CONFIG_FILE = SCRIPT_DIR / 'config.json'
    CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
    
    # 버전 관리 파일
    VERSIONS_FILE = 'versions.json'
    
    # 영역별 최소 기대 개수 (이보다 적으면 알림)
    EXPECTED_COUNTS = {
        '메인배너': 7,
        '최신외식업소식': 1,
        '서비스강조배너': 1,
        '파트너비즈니스팁': 1,
        '최신장사노하우': 1,
        '장사노하우슬롯': 1,
        '이벤트혜택': 1,
        '외식업광장숏츠': 1,
        '마이영역배너': 3,
        '플레이스홀더': 1,
    }
    
    # 9개 모니터링 영역
    MONITOR_AREAS = {
        '메인배너': {
            'container': '.EmblaCorestyled__Slide-sc-1kd33ib-5 .styled__BannerLink-sc-1lf27j1-0',
            'title_selector': '.styled__MainText-sc-1lf27j1-3',
            'subtitle_selector': '.styled__SubText-sc-1lf27j1-2',
            'description': '상단 메인 배너 슬라이드'
        },
        '최신외식업소식': {
            'container': '#slot-215 .styled__ListWrap-sc-bv0jg9-0',
            'items_selector': '.TextItemstyled__ItemLink-sc-11mndzl-0',
            'title_selector': '.Typography_b_9cyf_1bisyd4a',
            'badge_selector': '.Badge_b_9cyf_19agxiso',
            'description': '지원/동향/소식 뉴스'
        },
        '서비스강조배너': {
            'container': '.styled__CardBanner-sc-1qd6ixe-0',
            'link_selector': '.styled__CardBannerLink-sc-1qd6ixe-1',
            'title_selector': '.styled__TitleLine-sc-1qd6ixe-3',
            'image_selector': 'img',
            'description': '우리 가게 노출을 강화해보세요'
        },
        '파트너비즈니스팁': {
            'container': '.styled__TabBgControlWrapper-sc-bl1gfb-0',
            'title_selector': '.styled__Title-sc-bl1gfb-2',
            'tab_selector': '[role="tab"]',
            'items_selector': '.styled__DetailLink-sc-jmokk4-7',
            'description': '가게 운영 TIP / 외식업트렌드'
        },
        '최신장사노하우': {
            'container': '#slot-217 .styled__ModuleWrapper-sc-1hw99an-0.hAPdeK',
            'items_selector': '.VerticalItemstyled__VerticalLink-sc-1pwndbf-0',
            'title_selector': '.Typography_b_9cyf_1bisyd4a',
            'tag_selector': '.Typography_b_9cyf_1bisyd41z',
            'description': '장사 노하우 콘텐츠'
        },
        '장사노하우슬롯': {
            'container': '.styled__SlotWrap-sc-26notz-0.SPRaE',
            'items_selector': '.styled__ListWrap-sc-26notz-1.gMfHkL article a',
            'title_selector': '.HorizontalItemstyled__ContentInfoWrap-sc-vn9sod-3 span.Typography_b_9cyf_1bisyd4a',
            'description': '카드뉴스 형태 소식'
        },
        '이벤트혜택': {
            'container': '#slot-222',
            'items_selector': '.styled__ColorfulSwiperCardItem-sc-1cmxvoj-1',
            'title_selector': '.Typography_b_9cyf_1bisyd49',
            'badge_selector': '.Badge_b_9cyf_19agxiso',
            'date_selector': '.Typography_b_9cyf_1bisyd4a',
            'description': '이벤트·혜택'
        },
        '외식업광장숏츠': {
            'container': '#slot-238',
            'items_selector': '.styled__VideoContentWrapper-sc-1r2bu1h-0 a',
            'title_selector': '.Typography_b_9cyf_1bisyd4a',
            'description': '지금 핫한 외식업광장 숏폼'
        },
        '마이영역배너': {
            'container': '.styled__Wrapper-sc-1huixac-0 .EmblaCorestyled__Slide-sc-1kd33ib-5 a',
            'title_selector': '.styled__SmallTextBannerTitle-sc-1huixac-3',
            'subtitle_selector': '.styled__SmallTextBannerSubTitle-sc-1huixac-4',
            'description': '우측 하단 배너 슬라이드'
        },
        '플레이스홀더': {
            'input_selector': 'input.SearchInputstyled__Input-sc-18afat6-2',
            'description': '검색창 플레이스홀더 텍스트'
        },
    }
    
    @classmethod
    def load_config(cls):
        """설정 파일에서 로드"""
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cls.SPREADSHEET_ID = config.get('spreadsheet_id', '')
                cls.TARGET_URL = config.get('target_url', cls.TARGET_URL)
                cls.GITHUB_TOKEN = config.get('github_token', '')
                cls.GITHUB_REPO = config.get('github_repo', '')


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
# 브라우저 설정
# ============================================================
def create_browser(logger):
    """Selenium 브라우저 생성"""
    
    logger.info("🚀 브라우저 시작 중 (백그라운드)...")
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
    
    options.add_argument('--lang=ko-KR')
    options.add_experimental_option('prefs', {
        'intl.accept_languages': 'ko-KR,ko,en-US,en',
    })
    
    try:
        # Chrome 바이너리 경로 명시 (selenium-manager가 버전 자동 감지)
        import os
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path
        driver = webdriver.Chrome(options=options)  # selenium-manager 사용
        
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
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
            'items': [],
            'errors': []
        }
    
    def start(self):
        self.driver = create_browser(self.logger)
    
    def stop(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.logger.info("🛑 브라우저 종료")
    
    def _close_popups(self):
        """팝업 닫기"""
        self.logger.info("🔍 팝업 확인 중...")
        
        popup_close_selectors = [
            "//button[contains(text(), '닫기')]",
            "//button[contains(text(), '3일간')]",
            "//span[contains(text(), '닫기')]",
            "//span[contains(text(), '3일간')]",
            "//div[contains(text(), '닫기')]",
            "//a[contains(text(), '닫기')]",
            "//button[contains(@class, 'close')]",
        ]
        
        popup_closed = False
        
        for selector in popup_close_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    if elem.is_displayed():
                        elem.click()
                        self.logger.info(f"✅ 팝업 닫기 클릭")
                        popup_closed = True
                        time.sleep(1)
                        break
                if popup_closed:
                    break
            except:
                continue
        
        if not popup_closed:
            self.logger.info("ℹ️ 닫을 팝업 없음")
        
        return popup_closed
    
    def load_page(self):
        """페이지 로드"""
        self.logger.info(f"📄 페이지 로드 중: {Config.TARGET_URL}")
        
        try:
            self.driver.get(Config.TARGET_URL)
            
            self.logger.info("⏳ 페이지 로딩 대기 중...")
            time.sleep(5)
            
            WebDriverWait(self.driver, Config.ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            time.sleep(2)
            self._close_popups()
            time.sleep(1)
            
            page_source = self.driver.page_source.lower()
            page_title = self.driver.title
            
            self.logger.info(f"📋 페이지 제목: {page_title}")
            
            blocked_keywords = ['보안', '차단', 'blocked', 'access denied', '접근 제한']
            is_blocked = any(kw in page_source for kw in blocked_keywords)
            
            if is_blocked and '외식업' not in page_source:
                self.logger.warning("⚠️ 접근이 차단된 것 같습니다")
                self.results['access_status'] = 'blocked'
            else:
                self.logger.info("✅ 페이지 접근 성공!")
                self.results['access_status'] = 'success'
            
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
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            
            for i in range(0, min(total_height, 10000), 500):
                self.driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(0.3)
            
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            self.logger.warning(f"⚠️ 스크롤 오류: {e}")
    
    def extract_all_areas(self):
        """10개 영역 데이터 추출"""
        self.logger.info("🔍 10개 영역 데이터 추출 중...")
        
        items = []
        alerts = []  # 미노출 알림
        area_counts = {}  # 영역별 수집 개수
        
        for area_name, area_config in Config.MONITOR_AREAS.items():
            self.logger.info(f"  📌 {area_name} 추출 중...")
            
            try:
                area_items = self._extract_area(area_name, area_config)
                items.extend(area_items)
                area_counts[area_name] = len(area_items)
                self.logger.info(f"    → {len(area_items)}개 항목 발견")
                
                # 기대 개수 대비 미달 체크
                expected = Config.EXPECTED_COUNTS.get(area_name, 1)
                actual = len(area_items)
                
                if actual == 0:
                    alert_msg = f"🚨 [{area_name}] 미노출 - 콘텐츠가 수집되지 않았습니다"
                    alerts.append({'area': area_name, 'type': 'missing', 'message': alert_msg, 'expected': expected, 'actual': actual})
                    self.logger.warning(alert_msg)
                elif actual < expected:
                    alert_msg = f"⚠️ [{area_name}] 부족 - 기대: {expected}개, 실제: {actual}개"
                    alerts.append({'area': area_name, 'type': 'insufficient', 'message': alert_msg, 'expected': expected, 'actual': actual})
                    self.logger.warning(alert_msg)
                    
            except Exception as e:
                self.logger.warning(f"    ⚠️ {area_name} 추출 오류: {e}")
                alerts.append({'area': area_name, 'type': 'error', 'message': f"🚨 [{area_name}] 오류 - {str(e)}", 'expected': Config.EXPECTED_COUNTS.get(area_name, 1), 'actual': 0})
        
        self.results['items'] = items
        self.results['alerts'] = alerts
        self.results['area_counts'] = area_counts
        self.logger.info(f"✅ 총 {len(items)}개 항목 추출 완료")
        
        if alerts:
            self.logger.warning(f"🚨 알림: {len(alerts)}개 영역에서 문제 발견")
    
    def _extract_area(self, area_name, config):
        """특정 영역 데이터 추출"""
        items = []
        
        if area_name == '메인배너':
            items = self._extract_main_banner(config)
        elif area_name == '최신외식업소식':
            items = self._extract_news(config)
        elif area_name == '서비스강조배너':
            items = self._extract_service_banner(config)
        elif area_name == '파트너비즈니스팁':
            items = self._extract_partner_tips(config)
        elif area_name == '최신장사노하우':
            items = self._extract_knowhow(config)
        elif area_name == '장사노하우슬롯':
            items = self._extract_helpful_news(config)
        elif area_name == '이벤트혜택':
            items = self._extract_events(config)
        elif area_name == '외식업광장숏츠':
            items = self._extract_shorts(config)
        elif area_name == '마이영역배너':
            items = self._extract_my_banner(config)
        elif area_name == '플레이스홀더':
            items = self._extract_placeholder(config)
        
        for item in items:
            item['area'] = area_name
        
        return items
    
    def _extract_main_banner(self, config):
        """메인 배너 추출 (슬라이드 7개)"""
        items = []
        collected_titles = set()
        
        try:
            for slide_idx in range(7):
                banners = self.driver.find_elements(By.CSS_SELECTOR, '.EmblaCorestyled__Slide-sc-1kd33ib-5 .styled__BannerLink-sc-1lf27j1-0')
                
                for banner in banners:
                    try:
                        title = ''
                        subtitle = ''
                        
                        try:
                            title_elem = banner.find_element(By.CSS_SELECTOR, '.styled__MainText-sc-1lf27j1-3')
                            title = title_elem.text.strip().replace('\n', ' ')
                        except:
                            pass
                        
                        try:
                            subtitle_elem = banner.find_element(By.CSS_SELECTOR, '.styled__SubText-sc-1lf27j1-2')
                            subtitle = subtitle_elem.text.strip()
                        except:
                            pass
                        
                        href = banner.get_attribute('href') or ''
                        
                        if title or subtitle:
                            full_title = f"{subtitle} - {title}" if subtitle and title else (title or subtitle)
                            
                            if full_title not in collected_titles:
                                collected_titles.add(full_title)
                                items.append({
                                    'title': full_title[:200],
                                    'link': href,
                                    'link_status': self._check_link(href)
                                })
                    except:
                        continue
                
                try:
                    next_buttons = self.driver.find_elements(By.CSS_SELECTOR, '.NextButton__AbsoluteNextWrapper-sc-1ld200l-0 button')
                    if next_buttons and len(next_buttons) > 0:
                        next_buttons[0].click()
                        time.sleep(0.5)
                except:
                    pass
                    
        except:
            pass
        return items
    
    def _extract_news(self, config):
        """최신 외식업 소식 추출"""
        items = []
        try:
            news_items = self.driver.find_elements(By.CSS_SELECTOR, config['items_selector'])
            for news in news_items:
                try:
                    text = news.text.strip()
                    href = news.get_attribute('href') or ''
                    
                    if text and len(text) > 3:
                        lines = text.split('\n')
                        title = ' '.join(lines).strip()
                        
                        items.append({
                            'title': title[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_service_banner(self, config):
        """서비스 강조 배너 추출"""
        items = []
        try:
            banners = self.driver.find_elements(By.CSS_SELECTOR, config['link_selector'])
            for banner in banners:
                try:
                    title = ''
                    try:
                        title_elem = banner.find_element(By.CSS_SELECTOR, config['title_selector'])
                        title = title_elem.text.strip()
                    except:
                        title = banner.text.strip()
                    
                    href = banner.get_attribute('href') or ''
                    
                    if title and len(title) > 3:
                        items.append({
                            'title': title[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_partner_tips(self, config):
        """파트너 비즈니스 팁 추출 (탭 클릭)"""
        items = []
        try:
            tabs = self.driver.find_elements(By.CSS_SELECTOR, config['tab_selector'])
            collected_titles = set()
            
            for tab_idx, tab in enumerate(tabs):
                try:
                    tab_text = tab.text.strip()
                    if tab_text:
                        items.append({
                            'title': f"[탭] {tab_text}",
                            'link': '',
                            'link_status': '탭메뉴'
                        })
                        
                        try:
                            tab.click()
                            time.sleep(0.5)
                        except:
                            pass
                        
                        detail_links = self.driver.find_elements(By.CSS_SELECTOR, config['items_selector'])
                        for link in detail_links:
                            try:
                                text = link.text.strip()
                                href = link.get_attribute('href') or ''
                                
                                if text and len(text) > 3:
                                    if text not in collected_titles:
                                        collected_titles.add(text)
                                        items.append({
                                            'title': f"[{tab_text}] {text[:180]}",
                                            'link': href,
                                            'link_status': self._check_link(href)
                                        })
                            except:
                                continue
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_knowhow(self, config):
        """장사노하우 추출"""
        items = []
        try:
            knowhow_items = self.driver.find_elements(By.CSS_SELECTOR, config['items_selector'])
            for item in knowhow_items:
                try:
                    text = item.text.strip()
                    href = item.get_attribute('href') or ''
                    
                    if text and len(text) > 3:
                        lines = text.split('\n')
                        title = lines[0] if lines else text
                        
                        items.append({
                            'title': title[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_helpful_news(self, config):
        """장사에 도움되는 요즘 소식 추출"""
        items = []
        try:
            news_links = self.driver.find_elements(By.CSS_SELECTOR, '.styled__SlotWrap-sc-26notz-0.SPRaE .styled__ListWrap-sc-26notz-1 article a')
            
            for link in news_links:
                try:
                    href = link.get_attribute('href') or ''
                    
                    try:
                        title_elem = link.find_element(By.CSS_SELECTOR, '.HorizontalItemstyled__ContentInfoWrap-sc-vn9sod-3 span.Typography_b_9cyf_1bisyd4a')
                        text = title_elem.text.strip()
                    except:
                        text = link.text.strip()
                    
                    if text and len(text) > 3:
                        items.append({
                            'title': text[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_events(self, config):
        """이벤트·혜택 추출"""
        items = []
        try:
            event_items = self.driver.find_elements(By.CSS_SELECTOR, config['items_selector'])
            for event in event_items:
                try:
                    text = event.text.strip()
                    href = event.get_attribute('href') or ''
                    
                    if text and len(text) > 3:
                        lines = text.split('\n')
                        title = ' | '.join(lines).strip()
                        
                        items.append({
                            'title': title[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_shorts(self, config):
        """외식업광장 숏츠 추출"""
        items = []
        try:
            video_links = self.driver.find_elements(By.CSS_SELECTOR, config['items_selector'])
            for link in video_links:
                try:
                    text = link.text.strip()
                    href = link.get_attribute('href') or ''
                    
                    if text and len(text) > 3:
                        items.append({
                            'title': text[:200],
                            'link': href,
                            'link_status': self._check_link(href)
                        })
                except:
                    continue
        except:
            pass
        return items
    
    def _extract_my_banner(self, config):
        """마이영역 배너 추출 (슬라이드 3개)"""
        items = []
        collected_titles = set()
        
        try:
            try:
                my_banner_container = self.driver.find_element(By.CSS_SELECTOR, '.styled__Wrapper-sc-1huixac-0')
                self.driver.execute_script("arguments[0].scrollIntoView(true);", my_banner_container)
                time.sleep(0.5)
            except:
                pass
            
            for slide_idx in range(3):
                banner_items = self.driver.find_elements(By.CSS_SELECTOR, '.styled__Wrapper-sc-1huixac-0 .EmblaCorestyled__Slide-sc-1kd33ib-5 a')
                
                for banner in banner_items:
                    try:
                        title = ''
                        subtitle = ''
                        
                        try:
                            title_elem = banner.find_element(By.CSS_SELECTOR, '.styled__SmallTextBannerTitle-sc-1huixac-3')
                            title = title_elem.text.strip()
                        except:
                            pass
                        
                        try:
                            subtitle_elem = banner.find_element(By.CSS_SELECTOR, '.styled__SmallTextBannerSubTitle-sc-1huixac-4')
                            subtitle = subtitle_elem.text.strip()
                        except:
                            pass
                        
                        href = banner.get_attribute('href') or ''
                        
                        if title or subtitle:
                            full_title = f"{subtitle} - {title}" if subtitle and title else (title or subtitle)
                            
                            if full_title not in collected_titles:
                                collected_titles.add(full_title)
                                items.append({
                                    'title': full_title[:200],
                                    'link': href,
                                    'link_status': self._check_link(href)
                                })
                    except:
                        continue
                
                try:
                    my_banner_next = self.driver.find_element(By.CSS_SELECTOR, '.styled__Wrapper-sc-1huixac-0 .NextButton__AbsoluteNextWrapper-sc-1ld200l-0 button')
                    my_banner_next.click()
                    time.sleep(0.5)
                except:
                    pass
                    
        except:
            pass
        return items
    
    def _extract_placeholder(self, config):
        """플레이스홀더 텍스트 추출"""
        items = []
        try:
            placeholder_input = self.driver.find_element(By.CSS_SELECTOR, config['input_selector'])
            placeholder_text = placeholder_input.get_attribute('placeholder')
            
            if placeholder_text and placeholder_text.strip():
                items.append({
                    'title': placeholder_text.strip(),
                    'link': '',
                    'link_status': '링크없음'
                })
        except Exception as e:
            self.logger.warning(f"플레이스홀더 추출 실패: {e}")
        
        return items
    
    def _check_link(self, url):
        """링크 상태 확인"""
        if not url or url.startswith('javascript:') or url.startswith('#'):
            return '링크없음'
        
        try:
            response = requests.head(
                url,
                timeout=5,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            if response.status_code < 400:
                return '정상'
            else:
                return f'오류({response.status_code})'
                
        except:
            return '확인불가'
    
    def take_screenshot(self):
        """전체 페이지 스크린샷 저장"""
        Config.SCREENSHOTS_DIR.mkdir(exist_ok=True)
        
        now_kst = datetime.now(KST)
        filename = Config.SCREENSHOTS_DIR / f"screenshot_{now_kst.strftime('%Y%m%d_%H%M%S')}.png"
        
        try:
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            self.logger.info(f"📐 페이지 높이: {total_height}px")
            
            self.driver.set_window_size(1920, total_height + 100)
            time.sleep(2)
            
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            self.driver.save_screenshot(str(filename))
            self.logger.info(f"📸 전체 페이지 스크린샷 저장: {filename}")
            self.results['screenshot'] = str(filename)
            
            self.driver.set_window_size(1920, 1080)
            
        except Exception as e:
            self.logger.error(f"❌ 스크린샷 오류: {e}")
            try:
                self.driver.save_screenshot(str(filename))
                self.results['screenshot'] = str(filename)
            except:
                pass
    
    def get_page_info(self):
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
                    self.extract_all_areas()
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
        
        # 알림 먼저 저장
        alerts = results.get('alerts', [])
        for alert in alerts:
            row_data = [
                results['date'],
                results['time'],
                f"🚨 ALERT: {alert.get('area', '')}",
                alert.get('message', ''),
                f"기대: {alert.get('expected', 0)}개 / 실제: {alert.get('actual', 0)}개",
                alert.get('type', '')
            ]
            sheets.append_row(row_data)
        
        items = results.get('items', [])
        
        if not items:
            row_data = [
                results['date'],
                results['time'],
                '-',
                '데이터 없음',
                '-',
                results['status']
            ]
            sheets.append_row(row_data)
        else:
            for item in items:
                row_data = [
                    results['date'],
                    results['time'],
                    item.get('area', ''),
                    item.get('title', '')[:100],
                    item.get('link', ''),
                    item.get('link_status', '')
                ]
                sheets.append_row(row_data)
        
        logger.info(f"✅ Google Sheets 저장 완료 ({len(items)}개 항목, {len(alerts)}개 알림)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Google Sheets 저장 오류: {e}")
        return False


# ============================================================
# GitHub 업로드 (버전 관리 포함)
# ============================================================
class GitHubUploader:
    """GitHub 업로드 클래스 (버전 관리 포함)"""
    
    def __init__(self, token, repo, logger):
        self.token = token
        self.repo = repo
        self.logger = logger
        self.api_base = f"https://api.github.com/repos/{repo}/contents"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_file(self, path):
        """GitHub에서 파일 가져오기"""
        try:
            response = requests.get(f"{self.api_base}/{path}", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def upload_file(self, path, content, message):
        """GitHub에 파일 업로드"""
        try:
            # 기존 파일 SHA 가져오기
            existing = self.get_file(path)
            sha = existing.get('sha') if existing else None
            
            # Base64 인코딩
            content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            data = {
                'message': message,
                'content': content_base64,
                'branch': 'main'
            }
            
            if sha:
                data['sha'] = sha
            
            response = requests.put(
                f"{self.api_base}/{path}",
                headers=self.headers,
                json=data
            )
            
            return response.status_code in [200, 201]
            
        except Exception as e:
            self.logger.error(f"❌ 파일 업로드 오류 ({path}): {e}")
            return False
    
    def get_version_list(self):
        """버전 목록 가져오기"""
        try:
            file_data = self.get_file(Config.VERSIONS_FILE)
            if file_data:
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return json.loads(content)
            return []
        except:
            return []
    
    def save_version_list(self, version_list):
        """버전 목록 저장"""
        content = json.dumps(version_list, ensure_ascii=False, indent=2)
        return self.upload_file(
            Config.VERSIONS_FILE,
            content,
            f'Update version list'
        )
    
    def upload_with_version(self, results, html_content):
        """버전 관리와 함께 업로드"""
        
        # 현재 버전 ID 생성
        version_id = f"{results.get('date', '')}_{results.get('time', '').replace(':', '-')}"
        
        # 버전 목록 가져오기
        version_list = self.get_version_list()
        
        # 새 버전 추가 (최신이 앞에)
        if version_id not in version_list:
            version_list.insert(0, version_id)
        
        # 최대 30개 버전만 유지
        version_list = version_list[:30]
        
        # HTML 생성 (버전 목록 포함)
        html_with_versions = generate_html_report(results, version_list)
        
        # 1. 메인 index.html 업로드
        success = self.upload_file(
            'index.html',
            html_with_versions,
            f'Update dashboard - {version_id}'
        )
        
        if success:
            self.logger.info("✅ index.html 업로드 완료")
        
        # 2. 버전별 HTML 저장
        version_success = self.upload_file(
            f'versions/{version_id}.html',
            html_content,
            f'Add version {version_id}'
        )
        
        if version_success:
            self.logger.info(f"✅ 버전 파일 저장: versions/{version_id}.html")
        
        # 3. 버전 목록 저장
        self.save_version_list(version_list)
        
        # 웹페이지 URL 출력
        page_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/"
        self.logger.info(f"🌐 웹페이지 URL: {page_url}")
        
        return success


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
    
    items = results.get('items', [])
    area_counts = {}
    for item in items:
        area = item.get('area', '기타')
        area_counts[area] = area_counts.get(area, 0) + 1
    
    logger.info(f"\n📦 영역별 수집 현황:")
    for area, count in area_counts.items():
        logger.info(f"  - {area}: {count}개")
    
    logger.info(f"\n📊 총 수집 항목: {len(items)}개")
    
    # 확인 필요 항목 출력
    need_check = [item for item in items if item.get('link_status') != '정상']
    if need_check:
        logger.info(f"\n⚠️ 확인 필요 항목: {len(need_check)}개")
        for item in need_check[:5]:  # 최대 5개만 표시
            logger.info(f"  - [{item.get('area')}] {item.get('title')[:30]}... ({item.get('link_status')})")
    
    if results.get('errors'):
        logger.info("\n❌ 오류:")
        for err in results['errors']:
            logger.info(f"  - {err}")
    
    logger.info("=" * 60 + "\n")


# ============================================================
# 메인
# ============================================================
def main():
    """메인 함수"""
    
    Config.load_config()
    
    logger = setup_logging()
    
    now_kst = datetime.now(KST)
    logger.info("🎯 배민외식업광장 모니터링 시작 (10개 영역) v3")
    logger.info(f"📅 실행 시간 (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🌐 대상 URL: {Config.TARGET_URL}")
    
    monitor = BaeminMonitor(logger)
    results = monitor.run()
    
    print_summary(results, logger)
    save_to_sheets(results, logger)
    
    # HTML 리포트 생성 및 GitHub 업로드 (버전 관리)
    try:
        html_content = generate_html_report(results)
        
        # 로컬에도 저장
        html_path = SCRIPT_DIR / 'report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"📄 HTML 리포트 저장: {html_path}")
        
        # GitHub 업로드 (버전 관리 포함)
        if Config.GITHUB_TOKEN and Config.GITHUB_REPO:
            uploader = GitHubUploader(Config.GITHUB_TOKEN, Config.GITHUB_REPO, logger)
            uploader.upload_with_version(results, html_content)
        else:
            logger.warning("⚠️ GitHub 설정이 없어 업로드를 건너뜁니다.")
        
    except Exception as e:
        logger.error(f"❌ HTML 리포트 생성 오류: {e}")
    
    # JSON 결과 저장
    now_kst = datetime.now(KST)
    results_file = Config.LOGS_DIR / f"results_{now_kst.strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    logger.info(f"📄 결과 저장: {results_file}")
    
    return 0 if results['status'] == 'success' else 1


if __name__ == '__main__':
    exit(main())
