import json
from qdrant_client import QdrantClient, models


FIELD = "probably_out_of_stock"

qdrant_client = QdrantClient("http://localhost", port=6333, timeout=20.0)

with open(FIELD + ".json", "r") as f:
    value_by_pid = json.loads(f.read())
points_by_value = {}
i = 0
count = len(value_by_pid)
for pid in value_by_pid:
    if i % 100 == 0:
        print(i, "/", count)
    i += 1
    value = value_by_pid[pid]
    pid = int(pid)
    points, _ = qdrant_client.scroll(
        collection_name="your_company_name",
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="product_id",
                    match=models.MatchValue(value=pid),
                )
            ]
        ),
        limit=999_999,
    )
    for point in points:
        if FIELD not in point.payload or point.payload[FIELD] != value:
            if value not in points_by_value:
                points_by_value[value] = []
            points_by_value[value].append(point.id)
    if len(points_by_value) == 1000:
        for value in points_by_value:
            points = points_by_value[value]
            print("Setting", len(points), "payloads to", value)
            qdrant_client.set_payload(
                collection_name="your_company_name",
                points=points,
                payload={FIELD: value},
                wait=True,
            )
        points_by_value = {}

for value in points_by_value:
    points = points_by_value[value]
    print("Setting", len(points), "payloads to", value)
    qdrant_client.set_payload(
        collection_name="your_company_name",
        points=points,
        payload={FIELD: value},
        wait=True,
    )
