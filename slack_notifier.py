#!/usr/bin/env python3
"""
Slack 알림 모듈 - 배민 모니터링 결과를 Slack으로 전송
urllib 표준 라이브러리만 사용 (추가 설치 불필요)
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


class SlackNotifier:
    """Slack Incoming Webhook 알림 전송"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url and webhook_url.startswith('https://hooks.slack.com/'))

    def _post(self, payload: dict) -> bool:
        """Slack Webhook에 POST 요청"""
        if not self.enabled:
            return False
        try:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            print(f"⚠️ Slack 전송 실패 (HTTP {e.code}): {e.reason}")
            return False
        except Exception as e:
            print(f"⚠️ Slack 전송 실패: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  ✅ 실행 완료 요약 알림
    # ------------------------------------------------------------------ #
    def notify_summary(self, results: dict, ai_suggestions: dict = None,
                       dashboard_url: str = '') -> bool:
        """매 실행 완료 시 결과 요약 전송"""
        date_str = results.get('date', '')
        time_str = results.get('time', '')
        status    = results.get('status', 'unknown')
        items     = results.get('items', [])
        alerts    = results.get('alerts', [])
        errors    = results.get('errors', [])
        area_counts = results.get('area_counts', {})

        # 상태 이모지·텍스트
        if status == 'success' and not alerts and not errors:
            header_emoji = '✅'
            header_text  = '배민 모니터링 정상 완료'
        elif status == 'success' and (alerts or errors):
            header_emoji = '⚠️'
            header_text  = f'배민 모니터링 완료 — 이상 {len(alerts)}건'
        else:
            header_emoji = '🔴'
            header_text  = f'배민 모니터링 실패 ({status})'

        # 영역별 수집 현황
        area_lines = [f"• {area}: {cnt}개" for area, cnt in area_counts.items()]
        area_text = '\n'.join(area_lines) if area_lines else '수집 데이터 없음'

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{header_emoji} {header_text}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📅 실행 시간*\n{date_str} {time_str} KST"},
                    {"type": "mrkdwn", "text": f"*📦 수집 항목*\n{len(items)}개 ({len(area_counts)}개 영역)"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*영역별 수집 현황*\n{area_text}"}
            }
        ]

        # 이상 감지 목록
        if alerts:
            alert_lines = [f"• {a.get('message', '')}" for a in alerts[:5]]
            if len(alerts) > 5:
                alert_lines.append(f"• ···외 {len(alerts) - 5}건 더")
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ 이상 감지 ({len(alerts)}건)*\n" + '\n'.join(alert_lines)
                }
            })

        # 오류 목록
        if errors:
            error_lines = [f"• {e}" for e in errors[:3]]
            if len(errors) > 3:
                error_lines.append(f"• ···외 {len(errors) - 3}건 더")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔴 오류 ({len(errors)}건)*\n" + '\n'.join(error_lines)
                }
            })

        # AI 제안 요약
        if ai_suggestions:
            total_ai = sum(len(v) for v in ai_suggestions.values())
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🤖 AI 문구 제안*\n{len(ai_suggestions)}개 영역 / {total_ai}개 항목 분석 완료"
                }
            })

        # 대시보드 버튼
        if dashboard_url:
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📊 대시보드 열기"},
                    "url": dashboard_url,
                    "style": "primary"
                }]
            })

        return self._post({"blocks": blocks})

    # ------------------------------------------------------------------ #
    #  ⚠️ 콘텐츠 이상 감지 알림 (즉시)
    # ------------------------------------------------------------------ #
    def notify_alerts(self, alerts: list) -> bool:
        """콘텐츠 미노출/부족 즉시 알림"""
        if not alerts:
            return False

        now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
        alert_lines = [f"• {a.get('message', '')}" for a in alerts]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"⚠️ 콘텐츠 이상 감지 ({len(alerts)}건)"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*감지 시간:* {now_kst} KST"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": '\n'.join(alert_lines)}
            }
        ]

        return self._post({"blocks": blocks})

    # ------------------------------------------------------------------ #
    #  🔴 오류 발생 알림 (즉시)
    # ------------------------------------------------------------------ #
    def notify_error(self, context: str, error_msg: str) -> bool:
        """크롤링/AI 오류 즉시 알림"""
        now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔴 모니터링 오류 발생"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*발생 위치*\n{context}"},
                    {"type": "mrkdwn", "text": f"*시간*\n{now_kst} KST"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*오류 내용*\n```{str(error_msg)[:400]}```"
                }
            }
        ]

        return self._post({"blocks": blocks})
