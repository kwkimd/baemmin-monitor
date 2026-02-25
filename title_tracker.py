#!/usr/bin/env python3
"""
제목 변경 추적 모듈 - 동일 제목이 오래 유지되면 '교체 필요' 감지
- 3일 이상 동일 → 교체 필요 (주의)
- 7일 이상 동일 → 교체 필요 (경고)
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))


class TitleTracker:
    """수집된 제목의 최초 노출일을 추적하여 장기 미변경 항목 감지"""

    WARN_DAYS  = 3   # 3일 이상 → 교체 필요 (주의)
    ALERT_DAYS = 7   # 7일 이상 → 교체 필요 (경고)

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._data: dict = {}
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                print(f"  📖 제목 히스토리 로드: {len(self._data)}개 항목")
            except Exception as e:
                print(f"  ⚠️ 히스토리 로드 실패: {e}")
                self._data = {}

    def _save(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ 히스토리 저장 실패: {e}")

    def update(self, items: list) -> set:
        """
        현재 수집된 items 목록으로 히스토리 업데이트.
        items: [{'area': ..., 'title': ..., ...}, ...]
        반환: 이번 실행에서 발견된 key 집합
        """
        now_kst   = datetime.now(KST)
        today_str = now_kst.strftime('%Y-%m-%d')
        now_str   = now_kst.isoformat()
        seen_keys = set()

        for item in items:
            area  = item.get('area', '')
            title = item.get('title', '')
            if not title or '[탭]' in title:
                continue

            key = f"{area}::{title}"
            seen_keys.add(key)

            if key not in self._data:
                # 최초 발견
                self._data[key] = {
                    'area':            area,
                    'title':           title,
                    'first_seen_date': today_str,
                    'first_seen':      now_str,
                    'last_seen_date':  today_str,
                    'last_seen':       now_str,
                }
            else:
                # 기존 항목 마지막 확인 시각 갱신
                self._data[key]['last_seen_date'] = today_str
                self._data[key]['last_seen']      = now_str

        self._save()
        return seen_keys

    def get_stale_alerts(self, seen_keys: set) -> list:
        """
        현재 노출 중이면서 WARN_DAYS 이상 동일한 제목 목록 반환.
        seen_keys: update() 반환값 (이번 실행에서 발견된 키)
        """
        today  = datetime.now(KST).date()
        alerts = []

        for key, entry in self._data.items():
            # 이번 실행에서 보이지 않은 항목(이미 제거된 콘텐츠)은 제외
            if key not in seen_keys:
                continue

            try:
                first_date   = datetime.strptime(entry['first_seen_date'], '%Y-%m-%d').date()
                days_elapsed = (today - first_date).days
            except Exception:
                continue

            if days_elapsed < self.WARN_DAYS:
                continue  # 3일 미만은 정상

            level = 'alert_week' if days_elapsed >= self.ALERT_DAYS else 'warn_3days'
            label = '1주일+' if days_elapsed >= self.ALERT_DAYS else '3일+'
            emoji = '🔴' if days_elapsed >= self.ALERT_DAYS else '⚠️'

            short_title = (entry['title'][:28] + '…') if len(entry['title']) > 28 else entry['title']

            alerts.append({
                'area':    entry['area'],
                'title':   entry['title'],
                'days':    days_elapsed,
                'level':   level,
                'type':    'stale',
                'message': (
                    f"{emoji} [{entry['area']}] 교체 필요 ({label}) — "
                    f"\"{short_title}\" {days_elapsed}일째 동일"
                )
            })

        # 오래된 순으로 정렬
        alerts.sort(key=lambda x: x['days'], reverse=True)
        return alerts
