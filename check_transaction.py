# check_transaction.py
import requests

# main.py에 넣은 "새로 발급받은" 키와 시크릿
KEY = "1408482452335854"
SECRET = "3FqFpFpadaj4lWalLiZoZ9pGCSu5jLA1Vzfplm4a6AcNedFxaD6X5QyVwV0Sc2uJN4wtW6Vxakwj6j5d"
TARGET_IMP_UID = "imp_208561282461" # 방금 실패했던 그 영수증 번호

def check():
    # 1. 토큰 발급
    res = requests.post("https://api.iamport.kr/users/getToken", json={"imp_key": KEY, "imp_secret": SECRET})
    if res.status_code != 200:
        print("❌ [로그인 실패] 키/시크릿을 다시 확인하세요.")
        return
    token = res.json()["response"]["access_token"]
    
    # 2. 결제 조회
    res = requests.get(f"https://api.iamport.kr/payments/{TARGET_IMP_UID}", headers={"Authorization": token})
    if res.status_code == 200:
        payment = res.json().get("response")
        if payment:
            print(f"✅ [조회 성공] 찾았습니다! 상태: {payment['status']}, 금액: {payment['amount']}")
            print("👉 백엔드는 정상입니다. 이제 주문 페이지에서 다시 결제하면 됩니다.")
        else:
            print("❓ [조회 성공했으나 데이터 없음] 매우 이상한 상태입니다.")
    else:
        print(f"❌ [조회 실패] 에러코드: {res.status_code}")
        print("👉 결론: 이 영수증은 '내 가게'에서 발행된 게 아닙니다. (캐시 문제 확정)")

if __name__ == "__main__":
    check()