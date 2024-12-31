# 🔍 Semantic Fashion Search

A Flask-based API that powers semantic search for fashion products using CLIP embeddings and vector search. Built with Python, it lets you search products using both text and images, with support for multi-language queries.

## 🚀 Tech Stack

- **Flask** - Web framework
- **Fashion-CLIP** - For text/image embeddings
- **Qdrant** - Vector database for similarity search
- **Redis** - Caching embeddings and translations
- **GPT-4** - Query translation and understanding
- **Sentry** - Error tracking

## 🛠️ Setup

1. First, make sure you have Redis and Qdrant running:
```bash
# Redis (default port 6379)
redis-server

# Qdrant (default port 6333)
docker run -p 6333:6333 qdrant/qdrant
```

2. Install the dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables:
```bash
export OPENAI_API_KEY="your-key"
export AUTH_TOKEN="your-auth-token"
export SENTRY_DSN="your-sentry-dsn"
```

4. Fire up the server:
```bash
python app.py
```

## 🔌 API Endpoints

### POST `/search`
Search products using text queries. Handles multi-language input (including Persian).

```json
{
  "search": "blue مانتو under 100k",
  "limit": 20,
  "offset": 0,
  "categories": [1, 2],
  "price_from": 0,
  "price_to": 100000,
  "shop_id": 123
}
```

### POST `/api/v1/similar-image-search/`
Find similar products using an image URL.

```json
{
  "url": "https://example.com/image.jpg",
  "limit": 20,
  "category_id": 1
}
```

### POST `/api/v1/image-search/encode/`
Encode an image file to get its embedding vector.

## 🔑 Authentication

All endpoints (except `/ping`) require Bearer token authentication:
```bash
curl -H "Authorization: Bearer YOUR_AUTH_TOKEN" ...
```

## 🧠 How It Works

1. **Text Search Flow:**
   - Query gets translated/understood by GPT-4
   - Text is embedded using Fashion-CLIP
   - Vector similarity search in Qdrant
   - Results filtered by category/price/availability

2. **Image Search Flow:**
   - Image gets preprocessed and embedded
   - Direct vector similarity search
   - Optional category filtering

## 💡 Features

- Multi-language support (English/Persian)
- Text & image-based search
- Price range filtering
- Category filtering
- Shop-specific search
- Result pagination
- Availability status sorting
- Embedding caching
- Query translation caching

## 🤔 Common Issues

- If Fashion-CLIP fails to load (SSL error), the app will retry automatically
- Large image files might need compression before processing
- Default vector similarity threshold is 0.2 for text and 0.3 for images

## 📝 Notes

- The app runs on `localhost:8000` by default
- CORS is enabled for `localhost:3000` and your production domain
- Redis caches embeddings and translations to speed up repeated queries
- Qdrant timeout is set to 100s for handling large result sets

## 🛟 Support

Check Sentry for error tracking and debugging. For issues, feel free to open a ticket in the repo.

## 🤝 Contributing

1. Fork it
2. Create your feature branch (`git checkout -b feature/cool-new-thing`)
3. Commit your changes (`git commit -am 'Add cool new thing'`)
4. Push to the branch (`git push origin feature/cool-new-thing`)
5. Create a Pull Request 