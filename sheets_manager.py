#!/usr/bin/env python3
"""
Google Sheets 연동 모듈
GitHub Actions 버전 - credentials.json 파일 사용
"""

import os
import json
from datetime import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleSheetsManager:
    """Google Sheets 관리 클래스"""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, spreadsheet_id: str, sheet_name: str = '모니터링로그'):
        """
        초기화
        
        Args:
            spreadsheet_id: Google Sheets ID (URL에서 확인)
            sheet_name: 시트 이름
        """
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Google API 인증"""
        
        credentials_path = Path('credentials.json')
        
        if not credentials_path.exists():
            raise FileNotFoundError(
                "credentials.json 파일을 찾을 수 없습니다. "
                "GitHub Secrets에서 GOOGLE_CREDENTIALS를 설정하세요."
            )
        
        try:
            credentials = Credentials.from_service_account_file(
                str(credentials_path),
                scopes=self.SCOPES
            )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            print("✅ Google Sheets API 인증 성공")
            
        except Exception as e:
            raise RuntimeError(f"Google API 인증 실패: {e}")
    
    def _ensure_sheet_exists(self):
        """시트가 존재하는지 확인하고, 없으면 생성"""
        
        try:
            # 스프레드시트 정보 가져오기
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            # 시트 목록 확인
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            if self.sheet_name not in sheet_names:
                # 시트 생성
                request = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': self.sheet_name
                            }
                        }
                    }]
                }
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=request
                ).execute()
                
                print(f"✅ 시트 '{self.sheet_name}' 생성됨")
                
                # 헤더 추가
                self._add_headers()
            
            return True
            
        except HttpError as e:
            print(f"❌ 시트 확인 오류: {e}")
            return False
    
    def _add_headers(self):
        """헤더 행 추가"""
        
        headers = [
            '날짜', '시간', '페이지제목', '상태',
            '총슬롯수', '총링크수', '깨진링크수',
            '깨진링크목록', '오류',
            'S01_타입', 'S01_내용',
            'S02_타입', 'S02_내용',
            'S03_타입', 'S03_내용',
            'S04_타입', 'S04_내용',
            'S05_타입', 'S05_내용',
            'S06_타입', 'S06_내용',
            'S07_타입', 'S07_내용',
            'S08_타입', 'S08_내용',
            'S09_타입', 'S09_내용',
            'S10_타입', 'S10_내용',
        ]
        
        range_name = f"{self.sheet_name}!A1"
        
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            print("✅ 헤더 추가됨")
            
        except HttpError as e:
            print(f"❌ 헤더 추가 오류: {e}")
    
    def append_row(self, row_data: list):
        """
        새 행 추가
        
        Args:
            row_data: 추가할 데이터 리스트
        """
        
        self._ensure_sheet_exists()
        
        range_name = f"{self.sheet_name}!A:Z"
        
        try:
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            updated_range = result.get('updates', {}).get('updatedRange', '')
            print(f"✅ 데이터 추가됨: {updated_range}")
            
            return True
            
        except HttpError as e:
            print(f"❌ 데이터 추가 오류: {e}")
            return False
    
    def get_last_row(self) -> list:
        """마지막 행 가져오기 (변경 감지용)"""
        
        self._ensure_sheet_exists()
        
        range_name = f"{self.sheet_name}!A:Z"
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if len(values) > 1:
                return values[-1]  # 마지막 행 (헤더 제외)
            
            return []
            
        except HttpError as e:
            print(f"❌ 데이터 읽기 오류: {e}")
            return []
    
    def get_all_data(self) -> list:
        """모든 데이터 가져오기"""
        
        self._ensure_sheet_exists()
        
        range_name = f"{self.sheet_name}!A:Z"
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            return result.get('values', [])
            
        except HttpError as e:
            print(f"❌ 데이터 읽기 오류: {e}")
            return []


# ============================================================
# 테스트 코드
# ============================================================
if __name__ == '__main__':
    # 테스트용
    spreadsheet_id = os.getenv('SPREADSHEET_ID', '')
    
    if not spreadsheet_id:
        print("❌ SPREADSHEET_ID 환경변수를 설정하세요")
        exit(1)
    
    try:
        sheets = GoogleSheetsManager(spreadsheet_id)
        
        # 테스트 데이터 추가
        test_row = [
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%H:%M:%S'),
            '테스트 페이지',
            'test',
            10, 50, 0, '', '',
            'banner', '테스트 배너',
        ]
        
        sheets.append_row(test_row)
        print("✅ 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
