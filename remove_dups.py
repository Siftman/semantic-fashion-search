from qdrant_client import QdrantClient


qdrant_client = QdrantClient("http://localhost", port=6333, timeout=20.0)

ids = set()

offset = None
checked = 0
to_remove = []
while True:
    print(f"Checked {checked:,}\tRemoved {checked-len(ids):,}")
    points, offset = qdrant_client.scroll(
        collection_name="dbstore",
        limit=10_000,
        offset=offset,
    )
    for point in points:
        if point.payload["image_id"] in ids:
            to_remove.append(point.id)
            if len(to_remove) == 1000:
                qdrant_client.delete(
                    collection_name="dbstore",
                    points_selector=to_remove,
                )
                to_remove = []
        else:
            ids.add(point.payload["image_id"])
    checked += len(points)
    if not offset:
        break

if to_remove:
    qdrant_client.delete(
        collection_name="dbstore",
        points_selector=to_remove,
    )

print(f"Checked {checked:,}\tRemoved {checked-len(ids):,}")

f = open("embedded_ids.txt", "w")
f.write("\n".join(ids))
f.close()
print("Wrote embedded ids to `embedded_ids.txt`")
