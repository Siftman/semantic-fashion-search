import uuid, requests, os, time, requests
from PIL import Image, UnidentifiedImageError
from qdrant_client import QdrantClient, models
from concurrent.futures import ThreadPoolExecutor
from fashion_clip.fashion_clip import FashionCLIP


while True:
    try:
        clip = FashionCLIP("fashion-clip")
        break
    except requests.exceptions.SSLError:
        print("Failed to load fashion clip model (SSL error). Retrying in 5s...")
        time.sleep(5)

qdrant_client = QdrantClient("http://localhost", port=6333, timeout=20.0)


def download_image(url):
    file_path = os.path.join("images", url.split("/")[-1])
    if os.path.exists(file_path):
        print("Skipped:", file_path, "(alreviady downloaded)")
        return
    while True:
        try:
            res = requests.get(url)
            res.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(res.content)
            print("Downloaded:", file_path)
            break
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception as e:
            print(f"Error downloading {url}: {e}. Waiting for 2 seconds to retry...")
            time.sleep(2)
            continue


def download_images(medias):
    urls = [m["url"] for m in medias]
    with ThreadPoolExecutor(max_workers=15) as executor:
        list(executor.map(download_image, urls))


def load_image(item):
    image_name = item["url"].split("/")[-1]
    try:
        image = Image.open(os.path.join("images", image_name))
        image.getexif().get(Image.ExifTags.Base.Orientation)
    except (SyntaxError, UnidentifiedImageError):
        return None
    return image


def load_images(medias):
    with ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(load_image, medias))


def does_image_exist(image_id):
    points, _ = qdrant_client.scroll(
        collection_name="shopino",
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="image_id",
                    match=models.MatchValue(value=image_id),
                )
            ]
        ),
        limit=1,
        with_payload=False,
    )
    return len(points) > 0


def send_ack_ids(ids):
    while True:
        try:
            res = requests.post(
                url="YOUR_API_ENDPOINT/api/v1/ai-search/submit-encoded-medias/",
                headers={"Authorization": "Token YOUR_AUTH_TOKEN"},
                json={"ids": ids},
            )
            res.raise_for_status()
            break
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except Exception as e:
            print("Updating medias in core failed. Waiting for 2 seconds to retry...")
            time.sleep(2)


def embed2point(medias, embeddings):
    points = []
    for i, media in enumerate(medias):
        if does_image_exist(media["id"]):
            continue
        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload={
                    "image_id": media["id"],
                    "url": media["url"],
                    "product_id": media["product_id"],
                    "shop_id": media["product__shop_id"],
                    "title": media["product__title"],
                    "category_id": media["product__category_id"],
                    "price": media["product__discounted_price"]
                    or media["product__price"],
                    "available": media["product__available"],
                    "in_stock": media["product__in_stock"],
                    "probably_out_of_stock": media["product__probably_out_of_stock"],
                },
            )
        )
    if points:
        qdrant_client.upsert(
            collection_name="shopino",
            points=points,
            wait=True,
        )


def fetch_medias_to_encode(count):
    res = requests.get(
        f"YOUR_API_ENDPOINT/api/v1/ai-search/medias-to-encode/?count={count}",
        headers={"Authorization": "Token YOUR_AUTH_TOKEN"},
    )
    res.raise_for_status()
    return res.json()


if __name__ == "__main__":
    print("Fetching medias...")
    medias = fetch_medias_to_encode(1000)
    print("Downloading", len(medias), "images...")
    download_images(medias)
    print("Loading", len(medias), "images...")
    images = load_images(medias)
    for i in range(len(images)):
        if images[i] == None:
            medias[i] = None
    images = [it for it in images if it is not None]
    medias = [it for it in medias if it is not None]
    if not medias:
        print("No media to embed. Waiting for 30s...")
        time.sleep(30)
        exit()
    print("Embedding", len(medias), "images...")
    embeddings = clip.encode_images(images, batch_size=100).tolist()
    for image in images:
        image.close()
    print("Inserting vectors to Qdrant...")
    embed2point(medias, embeddings)
    print("Updating medias in core...")
    send_ack_ids([it["id"] for it in medias])
    print("Done")
