#!/usr/bin/env python3
"""
Google Sheets 연동 모듈
로컬 PC 버전 - 9개 영역 모니터링용
"""

import json
from datetime import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 스크립트 위치 기준
SCRIPT_DIR = Path(__file__).parent.absolute()


class GoogleSheetsManager:
    """Google Sheets 관리 클래스"""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, spreadsheet_id: str, sheet_name: str = '모니터링로그'):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Google API 인증"""
        
        credentials_path = SCRIPT_DIR / 'credentials.json'
        
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"credentials.json 파일을 찾을 수 없습니다.\n"
                f"경로: {credentials_path}"
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
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            if self.sheet_name not in sheet_names:
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
                self._add_headers()
            
            return True
            
        except HttpError as e:
            print(f"❌ 시트 확인 오류: {e}")
            return False
    
    def _add_headers(self):
        """헤더 행 추가 (새로운 형식)"""
        
        headers = [
            '날짜',
            '시간', 
            '영역',
            '제목',
            '링크',
            '링크상태'
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
        """새 행 추가"""
        
        self._ensure_sheet_exists()
        
        range_name = f"{self.sheet_name}!A:F"
        
        try:
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"❌ 데이터 추가 오류: {e}")
            return False
    
    def get_all_data(self) -> list:
        """모든 데이터 가져오기"""

        self._ensure_sheet_exists()

        range_name = f"{self.sheet_name}!A:F"

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            return result.get('values', [])

        except HttpError as e:
            print(f"❌ 데이터 읽기 오류: {e}")
            return []

    def read_range(self, spreadsheet_id: str, range_name: str = 'A1:Z1000') -> list:
        """
        스프레드시트에서 범위 데이터 읽기

        Args:
            spreadsheet_id: 스프레드시트 ID
            range_name: 읽을 범위 (기본: A1:Z1000)

        Returns:
            2차원 리스트 (행x열)
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()

            return result.get('values', [])
        except Exception as e:
            print(f"❌ 데이터 읽기 오류: {e}")
            return []


if __name__ == '__main__':
    print("sheets_manager.py - Google Sheets 연동 모듈")
