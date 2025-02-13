import requests
from newspaper.api import Article

# Fetch Tech News with Full Content
def fetch_tech_news(api_key):
    # url = f"https://newsapi.org/v2/everything?q=(programming OR coding OR development) AND (features OR updates OR news) AND (languages OR frameworks) NOT (hiring OR jobs OR careers OR vacancies OR Gold OR economics)&from=2025-01-01&to=2025-01-14&language=en&sortBy=publishedAt&apiKey={api_key}"
    # url for top technology news
    url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching news: {response.status_code}")
        return []
        
    articles = response.json().get("articles", [])
    
    # Sort articles by date, newest first
    valid_articles = []
    for article in articles:
        # Skip removed or empty articles
        if (article.get("title") == "[Removed]" or 
            article.get("content") == "[Removed]" or 
            not article.get("url") or
            not article.get("publishedAt")):
            continue
            
        valid_articles.append(article)
    
    # Sort by publishedAt date descending
    
    full_articles = []
    for article in valid_articles:
        try:
            news_article = Article(article.get("url"))
            news_article.download()
            news_article.parse()
            
            # Validate article has meaningful content
            if not news_article.text or len(news_article.text) < 100 or article.get("urlToImage") is None:
                continue
                
            full_articles.append({
                "title": news_article.title,
                "content": news_article.text,
                "urlToImage": article.get("urlToImage"),
                "publishedAt": article.get("publishedAt")
            })
            
            # Break once we have 3 valid articles
            if len(full_articles) >= 3:
                break
                
        except Exception as e:
            print(f"Failed to fetch article from {article.get('url')}: {e}")
            continue
    
    return full_articles