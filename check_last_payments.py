import requests
import json
from datetime import datetime

# main.py에 있는 "로그인 성공한" 키 세트
MY_KEY = "1408482452335854"
MY_SECRET = "CmMX0E77ScL5LuntGgE4hUZCzs42C1cC6p4u4GSiEHIpHDvxR8rzWCQ2gtFvjfDNSjYmYXLyzsT5CjyS"

def check_ledger():
    print("🔍 [진단 시작] 이 열쇠로 볼 수 있는 '최근 장부'를 펼칩니다...")
    
    # 1. 토큰 발급
    res = requests.post("https://api.iamport.kr/users/getToken", json={
        "imp_key": MY_KEY, 
        "imp_secret": MY_SECRET
    })
    
    if res.status_code != 200:
        print("❌ 인증 실패! 키 값을 다시 확인해주세요.")
        return

    token = res.json()["response"]["access_token"]
    print("✅ 로그인 성공! (토큰 획득)")
    
    # 2. 최근 결제 내역 조회 (최신순 3개)
    print("\n📚 최근 결제 내역을 조회합니다...")
    payment_res = requests.get("https://api.iamport.kr/payments/status/all?limit=3&sorting=-started", headers={
        "Authorization": token
    })
    
    if payment_res.status_code != 200:
        print(f"❌ 조회 실패: {payment_res.text}")
        return

    payments = payment_res.json()['response']['list']
    
    if not payments:
        print("\n📭 [결과] 장부가 '텅 비어' 있습니다!")
        print("👉 즉, 이 열쇠(1408...)는 결제가 발생한 가게(imp75163120)와 전혀 다른 계정입니다.")
        print("👉 관리자 페이지의 계정이 여러 개이거나, 'V2 API' 키를 써야 할 수도 있습니다.")
    else:
        print(f"\n📝 [결과] 총 {len(payments)}개의 내역이 보입니다.")
        for p in payments:
            pay_time = datetime.fromtimestamp(p['started_at']).strftime('%Y-%m-%d %H:%M:%S')
            print(f" - [{pay_time}] {p['name']} ({p['amount']}원) | 상태: {p['status']}")
            print(f"   ㄴ 영수증번호(imp_uid): {p['imp_uid']}")
            print(f"   ㄴ 주문번호(merchant_uid): {p['merchant_uid']}")
            print("-" * 40)
            
        print("\n🔎 [비교해 보세요]")
        print("위 리스트에 방금 사용자님이 결제한 내역이 있나요?")
        print("1. 있다 👉 그렇다면 백엔드 코드는 정상입니다. 일시적 오류였을 수 있습니다.")
        print("2. 없다 👉 이 열쇠는 '다른 가게'의 열쇠입니다. 내 가게 키를 다시 찾아야 합니다.")

if __name__ == "__main__":
    check_ledger()