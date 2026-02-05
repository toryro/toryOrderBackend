import requests
import json

# ==========================================
# 👇 main.py에 적어둔 값 그대로 입력하세요
MY_IMP_KEY = "1408482452335854"   
MY_IMP_SECRET = "CmMX0E77ScL5LuntGgE4hUZCzs42C1cC6p4u4GSiEHIpHDvxR8rzWCQ2gtFvjfDNSjYmYXLyzsT5CjyS"
# 👇 로그에 떴던 "찾지 못했다는" 그 결제 번호
TARGET_IMP_UID = "imp_532464090827" 
# ==========================================

def check_payment_direct():
    print(f"🔍 [진단 시작] 결제번호({TARGET_IMP_UID}) 조회 시도")
    
    # 1. 토큰 발급
    token_res = requests.post("https://api.iamport.kr/users/getToken", json={
        "imp_key": MY_IMP_KEY,
        "imp_secret": MY_IMP_SECRET
    })
    
    if token_res.status_code != 200:
        print("❌ [토큰 발급 실패] API Key/Secret이 틀렸습니다.")
        return

    access_token = token_res.json()['response']['access_token']
    print("✅ [토큰 발급 성공] 키 값은 유효합니다.")

    # 2. 결제 내역 단건 조회
    print(f"🚀 포트원 서버에 '{TARGET_IMP_UID}' 내역 요청 중...")
    payment_res = requests.get(f"https://api.iamport.kr/payments/{TARGET_IMP_UID}", headers={
        "Authorization": access_token
    })
    
    payment_data = payment_res.json()
    
    if payment_data['code'] == 0:
        # 조회 성공 (이러면 백엔드 코드가 문제)
        print("\n🎉 [대반전] 결제 내역을 찾았습니다!")
        print(f" - 결제 상태: {payment_data['response']['status']}")
        print(f" - 금액: {payment_data['response']['amount']}")
        print("👉 스크립트에서는 되는데 서버에서 안 된다면, 서버 재시작을 안 했거나 main.py 저장이 안 된 것입니다.")
    else:
        # 조회 실패 (이게 예상되는 결과)
        print("\n🚨 [조회 실패] '존재하지 않는 결제정보입니다'")
        print("👉 증거 확보 완료: 지금 사용 중인 API Key는 이 결제를 만든 가게의 것이 아닙니다.")
        print("👉 결론: '1408...' 키는 사용자님의 키가 아닙니다. 관리자 페이지를 다시 확인해주세요!")

if __name__ == "__main__":
    check_payment_direct()