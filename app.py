import time, torch, json, requests, pickle, io, sentry_sdk
from typing import List
from werkzeug.datastructures import FileStorage
from fashion_clip.fashion_clip import FashionCLIP
from flask import Flask, request
from flask_cors import CORS
from flask_httpauth import HTTPTokenAuth
from qdrant_client import QdrantClient, models
from langchain_openai import ChatOpenAI
from redis import Redis
from PIL import Image
from flask import Flask
from sentry_sdk import capture_exception
from sentry_sdk.integrations.flask import FlaskIntegration


while True:
    try:
        clip = FashionCLIP("fashion-clip")
        break
    except requests.exceptions.SSLError:
        print("Failed to load fashion clip model (SSL error). Retrying in 5s...")
        time.sleep(5)

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0,
)
llm = ChatOpenAI(
    model="gpt-4",
    base_url="YOUR_API_BASE_URL",
    api_key="YOUR_API_KEY",
)
redis = Redis(host="localhost", port=6379)
qdrant_client = QdrantClient("http://localhost", port=6333, timeout=100.0)


def check_translation_schema(translation):
    return (
        isinstance(translation, dict)
        and "query" in translation
        and isinstance(translation["query"], str)
        and "prices" in translation
        and (
            (
                isinstance(translation["prices"], list)
                and all(
                    isinstance(price, int) or price is None
                    for price in translation["prices"]
                )
            )
            or translation["prices"] is None
        )
        and "color" in translation
        and (isinstance(translation["color"], str) or translation["color"] is None)
    )


def gpt_translate(search_text):
    data = redis.get(f"translation:{search_text}")
    if data:
        data = json.loads(data)
        if check_translation_schema(data):
            return data
    try:
        res = llm.invoke(
            f'convert the term "{search_text}" to json: {{"query": the term translated to english, "prices": pair of given price limits. null otherwise, "color": color of product. null otherwise}}. "مانتو" translates to "manto" and "مقنعه" translates to "maghnae". dont say anything else'
        ).content
        res = res.replace("```json", "")
        res = res.replace("```", "")
        try:
            data = json.loads(res)
        except:
            raise Exception("Wrong GPT response: " + res)
        if not check_translation_schema(data):
            raise Exception("Wrong GPT response: " + json.dumps(data))
        redis.set(f"translation:{search_text}", json.dumps(data))

        return data

    except Exception as e:
        print(f"GPT Error: {search_text} -> {e}")
        return None


def point_to_dict(point):
    return {
        "product_id": point.payload["product_id"],
        "image_id": point.payload["image_id"],
        "url": point.payload["url"],
        "score": point.score,
    }


def encode_image(image: FileStorage):
    if isinstance(image, io.BytesIO):
        file = Image.open(image).convert("RGBA")
    else:
        file = Image.open(image.stream).convert("RGBA")

    encoded_input = clip.preprocess(images=file, return_tensors="pt")
    encoded_input = {k: v.to(clip.device) for k, v in encoded_input.items()}
    with torch.no_grad():
        return (clip.model.get_image_features(**encoded_input).detach().cpu().numpy())[
            0
        ].tolist()


def encode_text(text: str):
    cached_embedding = redis.get(f"embedding:{text}")
    if cached_embedding:
        return pickle.loads(cached_embedding)
    encoded_input = clip.preprocess(
        text=text,
        return_tensors="pt",
        max_length=77,
        padding="max_length",
        truncation=True,
    )
    encoded_input = {k: v.to(clip.device) for k, v in encoded_input.items()}
    with torch.no_grad():
        embedding = (
            clip.model.get_text_features(**encoded_input).detach().cpu().numpy()
        )[0]
    redis.set(f"embedding:{text}", pickle.dumps(embedding))
    return embedding


def qdrant_search(
    *,
    embedding: List[float],
    limit: int,
    category_ids: List[int],
    price_from: int,
    price_to: int,
    score_threshold: float,
    in_title: str,
    shop_id: int,
):
    must_conditions = []
    if category_ids is not None:
        must_conditions.append(
            models.FieldCondition(
                key="category_id", match=models.MatchAny(any=category_ids)
            )
        )
    must_conditions.append(
        models.FieldCondition(key="available", match=models.MatchValue(value=True))
    )
    price_range = {}
    if price_from is not None:
        price_range["gte"] = price_from
    if price_to is not None:
        price_range["lte"] = price_to
    if price_range:
        must_conditions.append(
            models.FieldCondition(key="price", range=models.Range(**price_range))
        )
    if in_title:
        must_conditions.append(
            models.FieldCondition(key="title", match=models.MatchText(text=in_title))
        )
    if shop_id:
        must_conditions.append(
            models.FieldCondition(key="shop_id", match=models.MatchValue(value=shop_id))
        )

    s = time.time()
    hits = qdrant_client.search(
        collection_name="shopino",
        query_vector=embedding,
        limit=limit,
        query_filter=models.Filter(must=must_conditions),
        score_threshold=score_threshold,
    )
    print("Queried in:", time.time() - s)
    return hits


app = Flask(__name__)
CORS(
    app,
    resources={
        r"*": {"origins": ["http://localhost:3000", "https://your-production-domain.com"]}
    },
)

auth = HTTPTokenAuth(scheme="Bearer")
AUTH_TOKEN = "YOUR_AUTH_TOKEN"


@auth.verify_token
def verify_token(token):
    if token == AUTH_TOKEN:
        return True
    return False


@app.route("/api/v1/similar-image-search/", methods=["POST"])
@auth.login_required
def api_v1_similar_image_search():
    data = request.get_json()

    points, _ = qdrant_client.scroll(
        collection_name="shopino",
        with_vectors=True,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="url",
                    match=models.MatchValue(value=data["url"]),
                )
            ]
        ),
        limit=1,
    )

    if points:
        embedding = points[0].vector
    else:
        try:
            res = requests.get(data["url"])
            res.raise_for_status()
        except Exception as err:
            capture_exception(err)
            return {"products": []}
        img = Image.open(io.BytesIO(res.content))
        embedding = clip.encode_images([img], batch_size=1).tolist()[0]

    category_ids = []
    if data["category_id"]:
        category_ids = [data["category_id"]]

    points = qdrant_search(
        embedding=embedding,
        limit=data["limit"],
        category_ids=category_ids,
        price_from=None,
        price_to=None,
        score_threshold=0.3,
        in_title=None,
        shop_id=None,
    )

    return {
        "products": [point_to_dict(point) for point in points],
    }


@app.route("/api/v1/image-search/encode/", methods=["POST"])
@auth.login_required
def api_v1_image_search_encode():
    return encode_image(request.files["image"])


def sort_scored_points(points):
    def sorting_key(point):
        return (
            point.payload.get("in_stock", False),
            not point.payload.get("probably_out_of_stock", False),
            point.payload.get("probably_out_of_stock", False),
            not point.payload.get("in_stock", True),
        )

    return sorted(points, key=sorting_key, reverse=True)


@app.route("/search", methods=["POST"])
@auth.login_required
def api_search():
    data = request.get_json()

    limit = data.get("limit") or data.get("count")
    if not isinstance(limit, int):
        raise Exception("Invalid data type for 'limit'. Expected an integer.")

    offset = data.get("offset", 0)
    if not isinstance(offset, int):
        raise Exception("Invalid data type for 'offset'. Expected an integer.")

    category_ids = data.get("categories")
    if category_ids:
        if not isinstance(category_ids, list) or not all(
            isinstance(cat_id, int) for cat_id in category_ids
        ):
            raise Exception(
                "Invalid data type for 'category_ids'. Expected a list of integers."
            )

    price_from = data.get("price_from")
    if price_from:
        if not isinstance(price_from, int):
            raise Exception("Invalid data type for 'price_from'. Expected an integer.")

    price_to = data.get("price_to")
    if price_to:
        if not isinstance(price_to, int):
            raise Exception("Invalid data type for 'price_to'. Expected an integer.")

    shop_id = data.get("shop_id")
    if shop_id:
        if not isinstance(shop_id, int):
            raise Exception("Invalid data type for 'shop_id'. Expected an integer.")

    if "embedding" in data:
        search_query = {}
        embedding = data["embedding"]
        score_threshold = 0.5
    else:
        search = data["search"]
        if not isinstance(search, str):
            raise Exception("Invalid data type for 'search'. Expected a string.")
        s = time.time()
        search_query = gpt_translate(search)

        if "prices" in search_query and search_query["prices"] is not None:
            price_from, price_to = search_query["prices"]
        else:
            price_from, price_to = None, None

        if search_query == None:
            return {
                "query": "",
                "prices": [None, None],
                "color": None,
                "products": [],
                "next_offset": None,
            }
        print("Translated in:", time.time() - s)
        print("Translated to:", search_query)
        s = time.time()
        embedding = encode_text(
            search_query["query"].replace("manto", "").replace("maghnae", "")
        )
        print("Text embedded in", time.time() - s)
        score_threshold = 0.2

    in_title = ""
    if "query" in search_query:
        if "manto" in search_query["query"]:
            in_title = "مانتو"
        if "maghnae" in search_query["query"]:
            in_title = "مقنعه"

    points = qdrant_search(
        embedding=embedding,
        limit=1000,
        category_ids=category_ids,
        price_from=price_from,
        price_to=price_to,
        score_threshold=score_threshold,
        in_title=in_title,
        shop_id=shop_id,
    )
    products = [point_to_dict(point) for point in sort_scored_points(points)]

    return {
        **search_query,
        "products": products[offset : offset + limit],
        "next_offset": offset + limit if offset + limit < 1000 else None,
    }


@app.route("/ping", methods=["GET"])
def ping():
    return "pong"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port="8000")

print("App started")
