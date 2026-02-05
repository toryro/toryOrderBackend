import requests
import json
import base64

# main.py에 있는 "성공한" 키 세트
MY_KEY = "1408482452335854"
MY_SECRET = "CmMX0E77ScL5LuntGgE4hUZCzs42C1cC6p4u4GSiEHIpHDvxR8rzWCQ2gtFvjfDNSjYmYXLyzsT5CjyS"

def find_real_owner():
    print("🕵️‍♂️ [진단 시작] 토큰의 진짜 주인을 찾습니다...")
    
    # 1. 토큰 발급
    res = requests.post("https://api.iamport.kr/users/getToken", json={
        "imp_key": MY_KEY, 
        "imp_secret": MY_SECRET
    })
    
    if res.status_code != 200:
        print("❌ 인증 실패! 키 값을 다시 확인해주세요.")
        return

    token = res.json()["response"]["access_token"]
    print("✅ 토큰 발급 성공!")
    
    # 2. 토큰(JWT) 해독
    try:
        # JWT는 '헤더.내용.서명' 구조입니다. 가운데 '내용'을 뜯어봅니다.
        payload_part = token.split('.')[1]
        # Base64 패딩 맞추기
        payload_part += '=' * (-len(payload_part) % 4)
        payload_data = base64.b64decode(payload_part).decode('utf-8')
        payload_json = json.loads(payload_data)
        
        print("\n📄 [토큰 내용물 공개]")
        print(f"👉 사용자 식별코드 (uni): {payload_json.get('uni')}")
        print(f"👉 가게 ID (store_id): {payload_json.get('store_id')}")
        
        real_code = payload_json.get('uni')
        print(f"\n📢 [결론] OrderPage.jsx에는 무조건 '{real_code}' 를 넣어야 합니다!")
        
    except Exception as e:
        print(f"⚠️ 토큰 해독 중 에러: {e}")

if __name__ == "__main__":
    find_real_owner()