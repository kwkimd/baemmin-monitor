#!/usr/bin/env python3
"""
샘플 AI 제안 데이터 생성
- API 할당량이 없어도 테스트 가능
- 실제와 동일한 형식의 샘플 데이터
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).parent.absolute()

# 샘플 AI 제안 데이터
sample_suggestions = {
    "메인배너": [
        {
            "original_title": "배민상회 쌀 사는 날! - 엄선한 고품질 쌀 상품 특별한 가격으로 만나보세요!",
            "analysis": {
                "analysis": "혜택은 있지만 긴급성과 구체적 할인율이 부족합니다.",
                "suggestions": [
                    {
                        "title": "🔥 지금 50% 할인! 프리미엄 쌀 특가",
                        "reason": "구체적 할인율과 긴급성으로 클릭 유도",
                        "score": 8.5
                    },
                    {
                        "title": "사장님 필수템! 고품질 쌀 최저가 보장",
                        "reason": "타겟 직접 호명 + 최저가 강조",
                        "score": 8.0
                    },
                    {
                        "title": "월 30만원 절감! 대용량 쌀 단독 특가",
                        "reason": "구체적 절감액으로 ROI 명확화",
                        "score": 7.8
                    }
                ]
            }
        },
        {
            "original_title": "배민파트너어워즈가 궁금하다면? - 수상기준부터 성장전략까지 지금 바로 확인하세요!",
            "analysis": {
                "analysis": "정보성 강하나 혜택이나 긴급성 부족합니다.",
                "suggestions": [
                    {
                        "title": "어워즈 수상하면 매출 2배! 지금 확인",
                        "reason": "구체적 결과로 동기 부여",
                        "score": 8.3
                    },
                    {
                        "title": "상위 10% 비밀 공개! 어워즈 전략",
                        "reason": "호기심 + 독점 정보 느낌",
                        "score": 7.9
                    },
                    {
                        "title": "마감 임박! 어워즈 신청 놓치지 마세요",
                        "reason": "긴급성으로 즉시 행동 유도",
                        "score": 7.5
                    }
                ]
            }
        },
        {
            "original_title": "스타벅스 커피 쿠폰도 받고 - 인기 프랜차이즈 브랜드 창업지원비 받아보세요!",
            "analysis": {
                "analysis": "혜택은 좋으나 타겟과 조건이 불명확합니다.",
                "suggestions": [
                    {
                        "title": "창업비 최대 500만원! 스벅 쿠폰 덤",
                        "reason": "금액 구체화 + 추가 혜택 강조",
                        "score": 8.7
                    },
                    {
                        "title": "지금 신청하면 스타벅스 1년 무료!",
                        "reason": "시간 + 파격 혜택으로 주목도 상승",
                        "score": 8.2
                    },
                    {
                        "title": "한정 50명! 프랜차이즈 창업 지원",
                        "reason": "희소성으로 빠른 결정 유도",
                        "score": 7.6
                    }
                ]
            }
        }
    ],
    "최신외식업소식": [
        {
            "original_title": "소식 2월 셋째 주 배민소식 (영수증 QR 생성, 배민앱 다국어 지원, 고객주문알림 추가)",
            "analysis": {
                "analysis": "정보는 많으나 핵심 메시지가 분산되어 있습니다.",
                "suggestions": [
                    {
                        "title": "📱 영수증 QR로 고객 만족도 UP!",
                        "reason": "핵심 기능 하나로 집중 + 결과 제시",
                        "score": 8.1
                    },
                    {
                        "title": "신기능 3가지! 사장님 업무 30% 단축",
                        "reason": "구체적 효율성 강조",
                        "score": 7.8
                    },
                    {
                        "title": "외국인 고객 잡는 법! 다국어 지원 시작",
                        "reason": "새로운 고객층 확보 어필",
                        "score": 7.5
                    }
                ]
            }
        }
    ],
    "이벤트혜택": [
        {
            "original_title": "배민상회 | 장사 꿀템인 배달 아이디어 제품! 100원에 구매하세요 | ~ 02. 28까지",
            "analysis": {
                "analysis": "파격 가격은 있으나 제품 설명이 모호합니다.",
                "suggestions": [
                    {
                        "title": "🎁 100원 기적! 배달용품 10종 세트",
                        "reason": "구체적 구성으로 가치 명확화",
                        "score": 8.9
                    },
                    {
                        "title": "D-9 마감! 배달 필수템 100원에 가져가세요",
                        "reason": "마감일 카운트다운으로 긴급성",
                        "score": 8.4
                    },
                    {
                        "title": "월 10만원 절약! 배달용품 100원 특가",
                        "reason": "장기 절감 효과 강조",
                        "score": 8.0
                    }
                ]
            }
        }
    ]
}

def main():
    print("=" * 60)
    print("샘플 AI 제안 데이터 생성")
    print("=" * 60)
    
    # ai_suggestions 폴더 생성
    ai_dir = SCRIPT_DIR / 'ai_suggestions'
    ai_dir.mkdir(exist_ok=True)
    
    # 현재 시간
    now = datetime.now(KST)
    filename = f"suggestions_{now.strftime('%Y%m%d_%H%M%S')}.json"
    filepath = ai_dir / filename
    
    # JSON 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(sample_suggestions, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 샘플 데이터 생성: {filepath}")
    print(f"\n📊 포함된 데이터:")
    for area, items in sample_suggestions.items():
        print(f"  - {area}: {len(items)}개")
    
    print("\n" + "=" * 60)
    print("다음 단계:")
    print("  1. integrate_ai.bat 실행")
    print("  2. report.html에서 💡 버튼 확인")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    exit(main())
