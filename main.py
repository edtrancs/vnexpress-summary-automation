import os
import feedparser
import requests
from bs4 import BeautifulSoup
import anthropic
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import time
import re

# Khởi tạo Claude client
client = anthropic.Anthropic(
    api_key=os.environ.get('CLAUDE_API_KEY')
)

# Cấu hình RSS feeds - CHỈ VNEXPRESS
RSS_FEEDS = {
    'VnExpress Góc Nhìn': 'https://vnexpress.net/rss/goc-nhin.rss'
}

def clean_html(html_content):
    """Làm sạch HTML content"""
    if not html_content:
        return ""
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Xóa các thẻ không cần thiết
    for element in soup(['script', 'style', 'img', 'a', 'br', 'div', 'span']):
        element.decompose()
    
    # Lấy text và làm sạch
    text = soup.get_text()
    
    # Làm sạch whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def get_article_content_from_rss(entry):
    """Lấy content từ RSS entry thay vì crawl website"""
    print(f"   📡 [DEBUG] Extracting content from RSS entry...")
    
    content_parts = []
    
    # 1. Lấy summary từ RSS (thường có sẵn trong VnExpress RSS)
    if hasattr(entry, 'summary') and entry.summary:
        summary_text = clean_html(entry.summary)
        if summary_text and len(summary_text) > 20:
            content_parts.append(summary_text)
            print(f"   ✅ [DEBUG] RSS summary: {len(summary_text)} ký tự")
            print(f"   📝 [DEBUG] Summary preview: {summary_text[:100]}...")
    
    # 2. Lấy description nếu có
    if hasattr(entry, 'description') and entry.description:
        desc_text = clean_html(entry.description)
        if desc_text and len(desc_text) > 20 and desc_text not in content_parts:
            content_parts.append(desc_text)
            print(f"   ✅ [DEBUG] RSS description: {len(desc_text)} ký tự")
    
    # 3. Lấy content từ RSS content fields
    if hasattr(entry, 'content') and entry.content:
        for content_item in entry.content:
            if hasattr(content_item, 'value') and content_item.value:
                content_text = clean_html(content_item.value)
                if content_text and len(content_text) > 20:
                    content_parts.append(content_text)
                    print(f"   ✅ [DEBUG] RSS content: {len(content_text)} ký tự")
                    break
    
    # 4. Fallback: sử dụng title extended nếu có
    if not content_parts and hasattr(entry, 'title_detail') and entry.title_detail:
        title_content = clean_html(str(entry.title_detail))
        if title_content and len(title_content) > 20:
            content_parts.append(title_content)
            print(f"   🆘 [DEBUG] Using title detail as fallback")
    
    # 5. Final fallback: tạo content từ title
    if not content_parts:
        print(f"   ⚠️  [DEBUG] No RSS content found, using title only")
        return f"Bài viết: {entry.title}. Không thể lấy nội dung chi tiết từ RSS feed."
    
    # Ghép tất cả content lại
    full_content = '\n\n'.join(content_parts)
    
    print(f"   📊 [DEBUG] RSS EXTRACTION RESULT:")
    print(f"   📝 [DEBUG] - Total content parts: {len(content_parts)}")
    print(f"   📏 [DEBUG] - Full content length: {len(full_content)} ký tự")
    print(f"   📋 [DEBUG] - Content preview: {full_content[:200]}...")
    
    # Giới hạn độ dài
    return full_content[:3000]

def get_article_text_fallback(url):
    """Fallback method - vẫn thử crawl nhưng không fail nếu bị block"""
    print(f"   🌐 [DEBUG] Fallback crawl attempt: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.8,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   📊 [DEBUG] Fallback response: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Thử lấy content
            content_parts = []
            
            # VnExpress selectors
            for selector in ['p.description', 'p.Normal', '.fck_detail p', 'article p']:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 30:
                        content_parts.append(text)
                        if len(content_parts) >= 3:  # Đủ 3 đoạn là OK
                            break
                if content_parts:
                    break
            
            if content_parts:
                result = '\n\n'.join(content_parts[:5])  # Lấy 5 đoạn đầu
                print(f"   ✅ [DEBUG] Fallback crawl success: {len(result)} ký tự")
                return result[:3000]
        
        print(f"   ❌ [DEBUG] Fallback crawl failed: status {response.status_code}")
        return None
        
    except Exception as e:
        print(f"   ❌ [DEBUG] Fallback crawl exception: {e}")
        return None

def summarize_with_claude(title, content, source):
    """Tạo tóm tắt bằng Claude - VỚI RSS CONTENT"""
    print(f"   🤖 [DEBUG] Bắt đầu gọi Claude API...")
    print(f"   📄 [DEBUG] Input content length: {len(content)} ký tự")
    print(f"   📋 [DEBUG] Content preview: {content[:150]}...")
    
    if not content or len(content.strip()) < 30:
        print(f"   ❌ [DEBUG] Content quá ngắn: {len(content)} ký tự")
        return f"Không thể lấy nội dung chi tiết: {title}"
    
    prompt = f"""Hãy viết tóm tắt bài báo theo yêu cầu sau bằng tiếng Việt:

QUAN TRỌNG:
- Bắt đầu ngay bằng nội dung chính, KHÔNG viết "Tóm tắt bài viết" hay dòng mở đầu
- Tập trung vào quan điểm và lập luận của tác giả
- Trình bày rõ ràng, dễ hiểu
- Không quá 200 từ
- Không lặp lại tiêu đề

Tiêu đề: {title}

Nội dung bài viết: {content}

Tóm tắt:"""

    try:
        print(f"   📡 [DEBUG] Gửi request tới Claude API...")
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        summary = message.content[0].text.strip()
        print(f"   ✅ [DEBUG] Claude API success!")
        print(f"   📝 [DEBUG] Summary length: {len(summary)} ký tự")
        print(f"   📋 [DEBUG] Summary preview: {summary[:100]}...")
        return summary
        
    except Exception as e:
        print(f"   💥 [DEBUG] Claude API error: {e}")
        return f"Lỗi tạo tóm tắt cho '{title}': {str(e)}"

def parse_rss_feed(url, source_name):
    """Par
