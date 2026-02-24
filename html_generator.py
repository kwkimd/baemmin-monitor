#!/usr/bin/env python3
"""
HTML 리포트 생성 모듈 v2
- 버전 관리 (날짜별 HTML 저장 + 드롭다운)
- 확인 필요 항목 상세 설명
"""

import unicodedata
import difflib
from datetime import datetime, timezone, timedelta


def _normalize_title(title: str) -> str:
    """제목 정규화: 유니코드 NFC, 연속 공백 단일화"""
    if not title:
        return ''
    title = unicodedata.normalize('NFC', title)
    return ' '.join(title.split())


def _titles_match(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """두 제목의 유사도 비교 (정확 일치 우선, 85% 이상이면 매칭으로 판정)"""
    t1 = _normalize_title(title1)
    t2 = _normalize_title(title2)
    if t1 == t2:
        return True
    ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
    return ratio >= threshold

KST = timezone(timedelta(hours=9))


def generate_html_report(results, version_list=None, ai_suggestions=None, github_repo=None):
    """모니터링 결과를 HTML로 변환 (AI 제안 포함)"""
    
    if version_list is None:
        version_list = []
    
    if ai_suggestions is None:
        ai_suggestions = {}
    
    # 영역별 데이터 정리
    items = results.get('items', [])
    alerts = results.get('alerts', [])  # 미노출 알림
    area_data = {}
    
    for item in items:
        area = item.get('area', '기타')
        if area not in area_data:
            area_data[area] = []
        area_data[area].append(item)
    
    # 통계 계산
    total_items = len(items)
    total_areas = len(area_data)
    # 정상 + 탭메뉴는 OK로 처리
    ok_count = sum(1 for item in items if item.get('link_status') in ['정상', '탭메뉴'])
    need_check_count = total_items - ok_count
    
    # 🚨 미노출/부족 알림 섹션
    alert_html = ""
    if alerts:
        alert_rows = ""
        for alert in alerts:
            alert_type = alert.get('type', '')
            if alert_type == 'missing':
                type_badge = '<span class="alert-badge alert-critical">미노출</span>'
            elif alert_type == 'insufficient':
                type_badge = '<span class="alert-badge alert-warning">부족</span>'
            else:
                type_badge = '<span class="alert-badge alert-error">오류</span>'
            
            alert_rows += f'''
            <tr>
                <td>{type_badge}</td>
                <td><strong>{alert.get('area', '')}</strong></td>
                <td>기대: {alert.get('expected', 0)}개</td>
                <td>실제: {alert.get('actual', 0)}개</td>
            </tr>
            '''
        
        alert_html = f'''
        <div class="alert-section">
            <div class="alert-header">
                <h3>🚨 영역 노출 알림 ({len(alerts)}개)</h3>
            </div>
            <div class="alert-table-wrapper">
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>상태</th>
                            <th>영역</th>
                            <th>기대</th>
                            <th>실제</th>
                        </tr>
                    </thead>
                    <tbody>
                        {alert_rows}
                    </tbody>
                </table>
            </div>
        </div>
        '''
    
    # 확인 필요 항목 상세 목록 (탭메뉴 제외)
    need_check_items = [item for item in items if item.get('link_status') not in ['정상', '탭메뉴']]
    need_check_html = ""
    
    if need_check_items:
        need_check_rows = ""
        for item in need_check_items:
            need_check_rows += f'''
            <tr>
                <td>{item.get('area', '')}</td>
                <td>{item.get('title', '')[:50]}...</td>
                <td><span class="status-badge {get_status_class(item.get('link_status', ''))}">{item.get('link_status', '')}</span></td>
            </tr>
            '''
        
        need_check_html = f'''
        <div class="need-check-section">
            <div class="need-check-header">
                <h3>⚠️ 확인 필요 항목 ({need_check_count}개)
                    <span class="tooltip-icon" data-tooltip="확인 필요 기준:&#10;• 링크없음: 링크가 비어있거나 javascript:, # 으로 시작&#10;• 확인불가: 링크 접속 시 타임아웃 또는 오류&#10;• 오류(4xx/5xx): HTTP 상태 코드 오류&#10;&#10;※ 탭메뉴는 고정값이므로 제외">ⓘ</span>
                </h3>
            </div>
            <div class="need-check-table-wrapper">
                <table class="need-check-table">
                    <thead>
                        <tr>
                            <th>영역</th>
                            <th>제목</th>
                            <th>상태</th>
                        </tr>
                    </thead>
                    <tbody>
                        {need_check_rows}
                    </tbody>
                </table>
            </div>
        </div>
        '''
    
    # GitHub Pages 기본 URL 계산 (버전 이동 시 사용)
    if github_repo and '/' in github_repo:
        owner, repo_name = github_repo.split('/', 1)
        github_pages_base = f"https://{owner}.github.io/{repo_name}/"
    else:
        github_pages_base = ""

    # 버전 선택 드롭다운 HTML
    version_options = ""
    current_version = f"{results.get('date', '')}_{results.get('time', '').replace(':', '-')}"
    
    for v in version_list:
        selected = 'selected' if v == current_version else ''
        display_name = v.replace('_', ' ').replace('-', ':')
        version_options += f'<option value="{v}" {selected}>{display_name}</option>'
    
    version_dropdown_html = f'''
    <div class="version-selector">
        <label for="version-select">📂 버전 선택:</label>
        <select id="version-select" onchange="changeVersion(this.value)">
            {version_options}
        </select>
    </div>
    ''' if version_list else ''
    
    # 영역별 카드 HTML 생성
    area_cards_html = ""
    area_order = [
        '메인배너', '최신외식업소식', '서비스강조배너', '파트너비즈니스팁',
        '최신장사노하우', '장사노하우슬롯', '이벤트혜택', '외식업광장숏츠', '마이영역배너', '플레이스홀더'
    ]
    
    for area in area_order:
        if area in area_data:
            items_list = area_data[area]
            count = len(items_list)
            
            # 아이템 목록 HTML
            items_html = ""
            for item in items_list:
                title = item.get('title', '')
                link = item.get('link', '')
                status = item.get('link_status', '')
                
                status_class = get_status_class(status)
                status_icon = '✅' if status == '정상' else '📑' if status == '탭메뉴' else '⚠️'
                
                # AI 제안 찾기 (유사도 매칭: 정확 일치 우선, 85% 이상이면 매칭)
                ai_html = ""
                if area in ai_suggestions:
                    for ai_item in ai_suggestions[area]:
                        if _titles_match(ai_item.get('original_title', ''), title):
                            analysis = ai_item.get('analysis', {})
                            suggestions = analysis.get('suggestions', [])
                            
                            if suggestions:
                                suggestions_html = ""
                                for i, sug in enumerate(suggestions[:3], 1):
                                    suggestions_html += f'''
                                    <div class="ai-suggestion">
                                        <div class="ai-sug-header">
                                            <span class="ai-badge">AI 제안 {i}</span>
                                            <span class="ai-score">★ {sug.get('score', 0)}</span>
                                        </div>
                                        <div class="ai-title">{sug.get('title', '')}</div>
                                        <div class="ai-reason">{sug.get('reason', '')}</div>
                                    </div>
                                    '''
                                
                                ai_html = f'''
                                <div class="ai-suggestions-container">
                                    <button class="ai-toggle-btn" onclick="toggleAI(this)">💡 AI 제안 보기</button>
                                    <div class="ai-content" style="display:none;">
                                        {suggestions_html}
                                    </div>
                                </div>
                                '''
                            break
                
                if link and link.startswith('http'):
                    items_html += f'''
                    <div class="item">
                        <div class="item-main">
                            <a href="{link}" target="_blank" class="item-title">{title}</a>
                            <span class="item-status {status_class}">{status_icon} {status}</span>
                        </div>
                        {ai_html}
                    </div>
                    '''
                else:
                    items_html += f'''
                    <div class="item">
                        <div class="item-main">
                            <span class="item-title">{title}</span>
                            <span class="item-status {status_class}">{status_icon} {status}</span>
                        </div>
                        {ai_html}
                    </div>
                    '''
            
            area_cards_html += f'''
            <div class="area-card">
                <div class="area-header">
                    <h3>{area}</h3>
                    <span class="count-badge">{count}개</span>
                </div>
                <div class="area-items">
                    {items_html}
                </div>
            </div>
            '''
    
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>배민외식업광장 모니터링 대시보드</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* 헤더 */
        .header {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .header h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .header .update-time {{
            color: #666;
            font-size: 14px;
        }}
        
        .header .status-badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            margin-top: 10px;
        }}
        
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-failed {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        /* 버전 선택 */
        .version-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 10px;
        }}
        
        .version-selector label {{
            font-size: 14px;
            color: #666;
            white-space: nowrap;
        }}
        
        .version-selector select {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            background: white;
            cursor: pointer;
            min-width: 200px;
        }}
        
        .version-selector select:hover {{
            border-color: #667eea;
        }}
        
        /* 🚨 알림 섹션 */
        .alert-section {{
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            color: white;
            box-shadow: 0 5px 20px rgba(238, 90, 90, 0.3);
        }}
        
        .alert-header h3 {{
            color: white;
            font-size: 18px;
            margin-bottom: 15px;
        }}
        
        .alert-table-wrapper {{
            overflow-x: auto;
        }}
        
        .alert-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        
        .alert-table th,
        .alert-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }}
        
        .alert-table th {{
            background: rgba(0,0,0,0.1);
            font-weight: 600;
        }}
        
        .alert-table tr:hover {{
            background: rgba(0,0,0,0.1);
        }}
        
        .alert-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .alert-critical {{
            background: #fff;
            color: #c53030;
        }}
        
        .alert-warning {{
            background: #fef3c7;
            color: #92400e;
        }}
        
        .alert-error {{
            background: #fecaca;
            color: #991b1b;
        }}
        
        /* 확인 필요 섹션 */
        .need-check-section {{
            background: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        
        .need-check-header {{
            margin-bottom: 15px;
        }}
        
        .need-check-header h3 {{
            color: #c53030;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .tooltip-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            background: #c53030;
            color: white;
            border-radius: 50%;
            font-size: 11px;
            cursor: help;
            position: relative;
        }}
        
        .tooltip-icon:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            top: 25px;
            left: 0;
            background: #333;
            color: white;
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 12px;
            white-space: pre-line;
            min-width: 280px;
            z-index: 100;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            line-height: 1.6;
        }}
        
        .need-check-table-wrapper {{
            overflow-x: auto;
        }}
        
        .need-check-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .need-check-table th,
        .need-check-table td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #fed7d7;
        }}
        
        .need-check-table th {{
            background: #feb2b2;
            color: #742a2a;
            font-weight: 500;
        }}
        
        .need-check-table tr:hover {{
            background: #fff0f0;
        }}
        
        /* 통계 카드 */
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        
        .stat-card .number {{
            font-size: 36px;
            font-weight: 700;
            color: #667eea;
        }}
        
        .stat-card .label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        
        .stat-card.warning .number {{
            color: #e53e3e;
        }}
        
        /* 영역 카드 */
        .areas {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }}
        
        .area-card {{
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        
        .area-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .area-header h3 {{
            font-size: 16px;
            font-weight: 500;
        }}
        
        .count-badge {{
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
        }}
        
        .area-items {{
            padding: 15px;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .item {{
            padding: 10px;
            border-bottom: 1px solid #eee;
        }}
        
        .item:last-child {{
            border-bottom: none;
        }}
        
        .item-main {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 5px;
        }}
        
        .item-title {{
            flex: 1;
            font-size: 13px;
            color: #333;
            text-decoration: none;
            line-height: 1.4;
            word-break: break-word;
        }}
        
        .item-title:hover {{
            color: #667eea;
        }}
        
        .item-status {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 10px;
            white-space: nowrap;
        }}
        
        /* AI 제안 스타일 */
        .ai-suggestions-container {{
            margin-top: 8px;
        }}
        
        .ai-toggle-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 11px;
            cursor: pointer;
            font-weight: 500;
            transition: transform 0.2s;
        }}
        
        .ai-toggle-btn:hover {{
            transform: scale(1.05);
        }}
        
        .ai-content {{
            margin-top: 10px;
            padding: 10px;
            background: #f8f9ff;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        
        .ai-suggestion {{
            background: white;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 8px;
        }}
        
        .ai-suggestion:last-child {{
            margin-bottom: 0;
        }}
        
        .ai-sug-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        
        .ai-badge {{
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 600;
        }}
        
        .ai-score {{
            background: #ffd700;
            color: #333;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 600;
        }}
        
        .ai-title {{
            font-size: 12px;
            font-weight: 700;
            color: #333;
            margin-bottom: 4px;
            line-height: 1.4;
        }}
        
        .ai-reason {{
            font-size: 11px;
            color: #666;
            line-height: 1.4;
        }}
        
        .status-ok {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-warn {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-error {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 11px;
        }}
        
        /* 푸터 */
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.8);
            padding: 30px;
            font-size: 13px;
        }}
        
        /* 스크롤바 */
        .area-items::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .area-items::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 3px;
        }}
        
        .area-items::-webkit-scrollbar-thumb {{
            background: #ccc;
            border-radius: 3px;
        }}
        
        /* 반응형 */
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 22px;
            }}
            
            .header-top {{
                flex-direction: column;
            }}
            
            .areas {{
                grid-template-columns: 1fr;
            }}
            
            .stat-card .number {{
                font-size: 28px;
            }}
            
            .version-selector {{
                width: 100%;
            }}
            
            .version-selector select {{
                flex: 1;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 헤더 -->
        <div class="header">
            <div class="header-top">
                <div>
                    <h1>🍽️ 배민외식업광장 모니터링 대시보드</h1>
                    <p class="update-time">📅 마지막 업데이트: {results.get('date', '')} {results.get('time', '')} (KST)</p>
                    <span class="status-badge {'status-success' if results.get('status') == 'success' else 'status-failed'}">
                        {'✅ 정상 수집 완료' if results.get('status') == 'success' else '❌ 수집 실패'}
                    </span>
                </div>
                {version_dropdown_html}
            </div>
        </div>
        
        <!-- 🚨 영역 노출 알림 -->
        {alert_html}
        
        <!-- 확인 필요 항목 -->
        {need_check_html}
        
        <!-- 통계 -->
        <div class="stats">
            <div class="stat-card">
                <div class="number">{total_items}</div>
                <div class="label">총 수집 항목</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_areas}</div>
                <div class="label">모니터링 영역</div>
            </div>
            <div class="stat-card">
                <div class="number">{ok_count}</div>
                <div class="label">정상 링크</div>
            </div>
            <div class="stat-card {'warning' if need_check_count > 0 else ''}">
                <div class="number">{need_check_count}</div>
                <div class="label">확인 필요</div>
            </div>
        </div>
        
        <!-- 영역별 카드 -->
        <div class="areas">
            {area_cards_html}
        </div>
        
        <!-- 푸터 -->
        <div class="footer">
            <p>배민외식업광장 자동 모니터링 시스템</p>
            <p>Powered by Python + Selenium + GitHub Pages</p>
        </div>
    </div>
    
    <script>
        function changeVersion(version) {{
            if (version) {{
                var base = '{github_pages_base}';
                if (base) {{
                    window.location.href = base + 'versions/' + version + '.html';
                }} else {{
                    window.location.href = 'versions/' + version + '.html';
                }}
            }}
        }}
        
        function toggleAI(btn) {{
            const content = btn.nextElementSibling;
            if (content.style.display === 'none') {{
                content.style.display = 'block';
                btn.textContent = '🔼 AI 제안 숨기기';
            }} else {{
                content.style.display = 'none';
                btn.textContent = '💡 AI 제안 보기';
            }}
        }}
    </script>
</body>
</html>
'''
    
    return html


def get_status_class(status):
    """상태에 따른 CSS 클래스 반환"""
    if status == '정상':
        return 'status-ok'
    elif status == '탭메뉴':
        return 'status-warn'
    else:
        return 'status-error'


if __name__ == '__main__':
    # 테스트용
    test_results = {
        'date': '2026-02-11',
        'time': '14:30:00',
        'status': 'success',
        'items': [
            {'area': '메인배너', 'title': '테스트 배너 1', 'link': 'https://example.com', 'link_status': '정상'},
            {'area': '메인배너', 'title': '테스트 배너 2', 'link': '', 'link_status': '링크없음'},
            {'area': '파트너비즈니스팁', 'title': '[탭] 가게 운영 TIP', 'link': '', 'link_status': '탭메뉴'},
        ]
    }
    
    html = generate_html_report(test_results, ['2026-02-11_14-30-00', '2026-02-10_10-00-00'])
    print(html[:1000])
