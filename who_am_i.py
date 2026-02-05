import requests
import json
from datetime import datetime

# ✅ main.py에 적어둔 것과 "완전히 똑같은" 값을 넣으세요.
MY_KEY = "1408482452335854" 
MY_SECRET = "3FqFpFpadaj4lWalLiZoZ9pGCSu5jLA1Vzfplm4a6AcNedFxaD6X5QyVwV0Sc2uJN4wtW6Vxakwj6j5d" 

def reveal_identity():
    print("🕵️‍♂️ [진단 시작] 이 열쇠의 정체를 밝힙니다...")
    
    # 1. 로그인 (토큰 발급)
    res = requests.post("https://api.iamport.kr/users/getToken", json={
        "imp_key": MY_KEY, 
        "imp_secret": MY_SECRET
    })
    
    if res.status_code != 200:
        print(f"❌ [로그인 실패] 응답코드: {res.status_code}")
        print("👉 원인: Key나 Secret이 틀렸습니다. 복사하다가 공백이 들어갔는지 확인하세요.")
        return

    token = res.json()["response"]["access_token"]
    print("✅ [로그인 성공] 일단 키/비번은 유효합니다.")
    
    # 2. 이 열쇠로 보이는 '최근 거래 내역 5개' 가져오기
    print("\n📚 [장부 조회] 이 열쇠로 조회되는 최근 거래 5건:")
    payment_res = requests.get("https://api.iamport.kr/payments/status/all?limit=5&sorting=-started", headers={
        "Authorization": token
    })
    
    if payment_res.status_code == 200:
        payments = payment_res.json()['response']['list']
        if not payments:
            print("📭 [결과] 장부가 텅 비어있습니다! (거래 내역 0건)")
            print("👉 즉, 이 열쇠는 '방금 결제된 내 가게'와 전혀 다른 계정입니다.")
        else:
            for i, p in enumerate(payments):
                pay_time = datetime.fromtimestamp(p['started_at']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{i+1}. [{pay_time}] {p['name']} ({p['amount']}원)")
                print(f"   - UID: {p['imp_uid']}")
                print(f"   - 상태: {p['status']}")
                print("-" * 30)
            
            print("\n🔎 [비교 타임]")
            print("위 리스트에 방금 결제한 'imp_208561282461' 건이 있나요?")
    else:
        print(f"❌ [조회 에러] {payment_res.text}")

if __name__ == "__main__":
    reveal_identity()