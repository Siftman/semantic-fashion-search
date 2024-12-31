import requests, time
from qdrant_client import QdrantClient, models

qdrant_client = QdrantClient("http://localhost", port=6333, timeout=20.0)


def fetch_update_logs():
    res = requests.get(
        "YOUR_API_ENDPOINT/api/v1/ai-search/product-update-logs/",
        headers={"Authorization": "Token YOUR_AUTH_TOKEN"},
    )
    res.raise_for_status()
    return res.json()


def sync_logs(logs):
    for log in logs:
        qdrant_client.set_payload(
            collection_name="dbstore",
            payload={
                "title": log["title"],
                "category_id": log["category_id"],
                "price": log["price"],
                "available": log["available"],
                "in_stock": log["in_stock"],
                "probably_out_of_stock": log["probably_out_of_stock"],
            },
            points=models.Filter(
                must=[
                    models.FieldCondition(
                        key="product_id",
                        match=models.MatchValue(value=log["product_id"]),
                    )
                ]
            ),
            wait=True,
        )
    return [log["id"] for log in logs]


def send_ack(synced_logs):
    while True:
        try:
            res = requests.post(
                url="YOUR_API_ENDPOINT/api/v1/ai-search/clear-product-update-logs/",
                headers={"Authorization": "Token YOUR_AUTH_TOKEN"},
                json={"log_ids": synced_logs},
            )
            res.raise_for_status()
            print("Sent resolve logs to the core..")
            break
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception as e:
            print(
                "Sending resolved log ids to core failed. Waiting for 2 seconds to retry..."
            )
            time.sleep(2)


if __name__ == "__main__":
    while True:
        print("Fetching update logs...")
        logs = fetch_update_logs()
        if not logs:
            print("No logs found. Waiting for 30s...")
            time.sleep(30)
            continue
        print("Syncing update logs...")
        synced_logs = sync_logs(logs)
        print("Sending acks...")
        send_ack(synced_logs)
