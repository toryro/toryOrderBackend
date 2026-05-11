import requests
from typing import Optional

PORTONE_V2_BASE = "https://api.portone.io"

# v1 → v2 필드 변환 매핑
_IDENTITY_TYPE_MAP = {
    "phone": "PHONE_NUMBER",
    "card": "CARD",
    "business": "BUSINESS_REG_NUM",
}
_TRADE_TYPE_MAP = {
    "PERSONAL": "PERSONAL",
    "BUSINESS": "CORPORATE",
}


class PortOneV2Client:
    """PortOne v2 API 클라이언트. 가게별 api_secret으로 초기화합니다."""

    def __init__(self, api_secret: str, store_id: str):
        self.store_id = store_id
        self._headers = {
            "Authorization": f"PortOne {api_secret}",
            "Content-Type": "application/json",
        }

    def get_payment(self, payment_id: str) -> dict:
        """결제 단건 조회"""
        res = requests.get(
            f"{PORTONE_V2_BASE}/payments/{payment_id}",
            headers=self._headers,
            timeout=10,
        )
        if res.status_code != 200:
            raise Exception(f"결제 조회 실패: {res.text}")
        return res.json()

    def cancel_payment(
        self,
        payment_id: str,
        reason: str,
        amount: Optional[int] = None,
        current_cancellable_amount: Optional[int] = None,
    ) -> dict:
        """결제 취소 (전체 또는 부분)"""
        body: dict = {"reason": reason, "storeId": self.store_id}
        if amount is not None:
            body["amount"] = amount
        if current_cancellable_amount is not None:
            body["currentCancellableAmount"] = current_cancellable_amount

        res = requests.post(
            f"{PORTONE_V2_BASE}/payments/{payment_id}/cancel",
            headers=self._headers,
            json=body,
            timeout=10,
        )
        data = res.json()
        if res.status_code not in (200, 201):
            raise Exception(f"결제 취소 실패: {data.get('message', res.text)}")
        return data

    def issue_cash_receipt(
        self,
        payment_id: str,
        channel_key: str,
        trade_type: str,
        identity_type: str,
        identity: str,
        amount: int,
        tax_free: int = 0,
    ) -> dict:
        """외부 현금영수증 발급 (현금 결제 후 별도 발급)"""
        v2_type = _TRADE_TYPE_MAP.get(trade_type, "PERSONAL")
        v2_id_type = _IDENTITY_TYPE_MAP.get(identity_type, "PHONE_NUMBER")
        vat = round((amount - tax_free) / 11)

        body = {
            "storeId": self.store_id,
            "paymentId": payment_id,
            "channelKey": channel_key,
            "type": v2_type,
            "customerIdentity": {
                "type": v2_id_type,
                "number": identity,
            },
            "amount": amount,
            "vatAmount": vat,
            "taxFreeAmount": tax_free,
            "productType": "REAL_WORLD",
        }
        res = requests.post(
            f"{PORTONE_V2_BASE}/cash-receipts",
            headers=self._headers,
            json=body,
            timeout=10,
        )
        data = res.json()
        if res.status_code not in (200, 201):
            raise Exception(f"현금영수증 발급 실패: {data.get('message', res.text)}")
        return data

    def cancel_cash_receipt(self, cash_receipt_id: str) -> dict:
        """현금영수증 취소"""
        res = requests.delete(
            f"{PORTONE_V2_BASE}/cash-receipts/{cash_receipt_id}",
            headers=self._headers,
            params={"storeId": self.store_id},
            timeout=10,
        )
        data = res.json()
        if res.status_code not in (200, 201):
            raise Exception(f"현금영수증 취소 실패: {data.get('message', res.text)}")
        return data
