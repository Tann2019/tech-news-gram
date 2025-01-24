# Summarize Article
def summarize_article(article_text, summarizer):
    # Limit the input text to prevent excessive memory usage
    max_input_length = 1024  # Adjust based on model's maximum token limit
    if len(article_text) > max_input_length:
        article_text = article_text[:max_input_length]
    
    summary = summarizer(article_text, max_length=120, min_length=35, do_sample=False)
    print(summary)
    return summary[0]['summary_text']