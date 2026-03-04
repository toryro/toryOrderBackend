from locust import HttpUser, task, between

class ToryOrderUser(HttpUser):
    # 유저 한 명이 한 번 요청하고 다음 요청까지 1~3초를 쉰다는 뜻입니다. (실제 사람과 비슷하게)
    wait_time = between(1, 3) 

    @task
    def view_brands(self):
        # 현재 우리가 만든 API 중 로그인 없이 누구나 조회 가능한 /brands/ 주소를 찌릅니다!
        self.client.get("/brands/")