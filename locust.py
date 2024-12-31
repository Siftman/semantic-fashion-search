from locust import HttpUser, task, between
import random

class AISearchUser(HttpUser):
    wait_time = between(1, 3)  
    host = "https://search.shopino.app"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_terms = [
            "لباس راه راه مناسب تابستون", "لباس مناسب استخر", "شلوارک جین", "شرت کالوین کلین", 
            "لباس آبی عنکبوتی سیاه", "اکسسوری پسر نوجوان", "کاشلکشن پاییزه"
        ]
        self.shop_ids = [1057, 192, 1319, 607]  
    
    @task(3)  
    def test_ai_search(self):
        data = {
            "search": random.choice(self.search_terms),
            "limit": 100
        }
        if random.random() < 0.3:  
            data["shop_id"] = random.choice(self.shop_ids)
        
        if random.random() < 0.2:  
            data["price_from"] = random.randint(10, 100)
            data["price_to"] = random.randint(200, 500)
        
        with self.client.post(
            "/search", 
            json=data, 
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed with status {response.status_code}")