"""
포장 주문 알림 서비스 (알림톡 / SMS)

채널 우선순위: 가게 자체(OWN) > 브랜드(BRAND) > 플랫폼 공용(PLATFORM)
1단계: 플랫폼 공용 채널로 발송. 향후 OWN/BRAND 채널 키를 DB에 등록하면 자동 전환.
"""

import os
import hmac
import hashlib
import uuid
import requests
from datetime import datetime, timezone

SOLAPI_API_KEY = os.getenv("SOLAPI_API_KEY", "")
SOLAPI_API_SECRET = os.getenv("SOLAPI_API_SECRET", "")
PLATFORM_SENDER_NUMBER = os.getenv("PLATFORM_SENDER_NUMBER", "")
PLATFORM_KAKAO_PROFILE_KEY = os.getenv("PLATFORM_KAKAO_PROFILE_KEY", "")
TEMPLATE_ORDER_RECEIVED = os.getenv("SOLAPI_TEMPLATE_ORDER_RECEIVED", "")
TEMPLATE_ORDER_READY = os.getenv("SOLAPI_TEMPLATE_ORDER_READY", "")

SOLAPI_ENDPOINT = "https://api.solapi.com/messages/v4/send"


def _make_auth_header() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt = uuid.uuid4().hex
    signature = hmac.new(
        SOLAPI_API_SECRET.encode("utf-8"),
        (date + salt).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"HMAC-SHA256 ApiKey={SOLAPI_API_KEY}, Date={date}, Salt={salt}, Signature={signature}"


def _resolve_sender(store) -> dict:
    """채널 우선순위에 따라 발신 정보를 결정한다."""
    ntype = getattr(store, "notification_type", "PLATFORM") or "PLATFORM"

    if ntype == "OWN" and getattr(store, "kakao_profile_key", None):
        return {
            "profile_key": store.kakao_profile_key,
            "sender_number": store.sms_sender_number or PLATFORM_SENDER_NUMBER,
        }

    if ntype == "BRAND":
        brand = getattr(store, "brand", None)
        if brand and getattr(brand, "kakao_profile_key", None):
            return {
                "profile_key": brand.kakao_profile_key,
                "sender_number": brand.sms_sender_number or PLATFORM_SENDER_NUMBER,
            }

    # PLATFORM (기본값) 또는 폴백
    return {
        "profile_key": PLATFORM_KAKAO_PROFILE_KEY,
        "sender_number": PLATFORM_SENDER_NUMBER,
    }


def _normalize_phone(phone: str) -> str:
    return phone.replace("-", "").replace(" ", "")


def _send(phone: str, sender: dict, template_id: str, variables: dict, sms_text: str) -> None:
    """
    알림톡 발송 시도.
    - 카카오 채널 키와 템플릿이 있으면 알림톡 (disableSms=False → 카카오 미설치 시 SMS 자동 폴백)
    - 채널 키 없으면 SMS 직접 발송
    실패해도 예외를 올리지 않아 주문 흐름에 영향 없음.
    """
    if not SOLAPI_API_KEY or not SOLAPI_API_SECRET or not sender["sender_number"]:
        return

    to = _normalize_phone(phone)
    headers = {
        "Authorization": _make_auth_header(),
        "Content-Type": "application/json",
    }

    if sender["profile_key"] and template_id:
        body = {
            "message": {
                "to": to,
                "from": sender["sender_number"],
                "kakaoOptions": {
                    "pfId": sender["profile_key"],
                    "templateId": template_id,
                    "variables": variables,
                    "disableSms": False,  # 카카오 미설치 시 SMS 자동 전환
                },
            }
        }
    else:
        body = {
            "message": {
                "to": to,
                "from": sender["sender_number"],
                "type": "SMS",
                "text": sms_text,
            }
        }

    try:
        res = requests.post(SOLAPI_ENDPOINT, json=body, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"[알림] Solapi 응답 오류 {res.status_code}: {res.text[:200]}")
    except Exception as e:
        print(f"[알림] 발송 요청 실패: {e}")


def send_order_received(order, store) -> None:
    """주문 접수 알림 — 포장 주문 + 전화번호 있을 때만 발송"""
    if order.order_type != "TAKEOUT":
        return
    if not order.customer_phone:
        return
    ntype = getattr(store, "notification_type", "PLATFORM") or "PLATFORM"
    if ntype == "DISABLED":
        return

    sender = _resolve_sender(store)
    variables = {
        "#{매장명}": store.name,
        "#{주문번호}": str(order.daily_number),
    }
    sms_text = (
        f"[{store.name}] 포장 주문 {order.daily_number}번이 접수됐습니다.\n"
        "준비 완료 시 별도 안내드립니다."
    )

    _send(order.customer_phone, sender, TEMPLATE_ORDER_RECEIVED, variables, sms_text)


def send_order_ready(order, store) -> None:
    """포장 완료 알림 — 포장 주문 + 전화번호 있을 때만 발송"""
    if order.order_type != "TAKEOUT":
        return
    if not order.customer_phone:
        return
    ntype = getattr(store, "notification_type", "PLATFORM") or "PLATFORM"
    if ntype == "DISABLED":
        return

    sender = _resolve_sender(store)
    variables = {
        "#{매장명}": store.name,
        "#{주문번호}": str(order.daily_number),
    }
    sms_text = (
        f"[{store.name}] 포장 주문 {order.daily_number}번 준비가 완료됐습니다.\n"
        "카운터에서 수령해 주세요."
    )

    _send(order.customer_phone, sender, TEMPLATE_ORDER_READY, variables, sms_text)
