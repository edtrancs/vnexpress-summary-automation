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

# Khởi tạo Claude client
client = anthropic.Anthropic(
    api_key=os.environ.get('CLAUDE_API_KEY')
)

# Cấu hình RSS feeds - CHỈ VNEXPRESS
RSS_FEEDS = {
    'VnExpress Góc Nhìn': 'https://vnexpress.net/rss/goc-nhin.rss'
}

def get_article_text(url):
    """Lấy full text từ URL bài báo VnExpress"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # VnExpress specific selectors
        content_parts = []
        
        # 1. Lấy description/summary
        description = soup.find('p', class_='description')
        if description:
            content_parts.append(description.get_text().strip())
        
        # 2. Lấy nội dung chính - VnExpress dùng class 'Normal'
        normal_content = soup.find_all('p', class_='Normal')
        for p in normal_content:
            text = p.get_text().strip()
            if text and len(text) > 20:  # Lọc bỏ đoạn quá ngắn
                content_parts.append(text)
        
        # 3. Fallback: nếu không tìm thấy, thử các selector khác
        if not content_parts:
            # Thử các class khác của VnExpress
            for selector in ['.fck_detail', '.content_detail', 'article p', '.article-content p']:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 20:
                        content_parts.append(text)
                if content_parts:
                    break
        
        # Ghép tất cả lại
        full_text = '\n\n'.join(content_parts)
        
        # Debug log
        print(f"   Lấy được {len(full_text)} ký tự từ {url[:50]}...")
        
        return full_text[:4000]  # Tăng giới hạn lên 4000 ký tự
        
    except Exception as e:
        print(f"   ❌ Lỗi khi lấy text từ {url}: {e}")
        return ""

def summarize_with_claude(title, content, source):
    """Tạo tóm tắt bằng Claude"""
    if not content:
        return f"Không thể truy cập bài viết: {title}"
    
    prompt = f"""Viết tóm tắt chi tiết bài viết theo yêu cầu sau bằng tiếng Việt:

Yêu cầu:
- Bắt đầu ngay bằng quan điểm chính, không viết dòng mở đầu "Tóm tắt bài viết..."
- Bao gồm quan điểm chính và các lập luận ủng hộ
- Các lập luận cần trình bày xuống dòng cho dễ đọc  
- Không quá 200 chữ
- Không lặp lại tiêu đề trong nội dung tóm tắt

Tiêu đề: {title}

Nội dung: {content}

Tóm tắt chi tiết:"""

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
        
    except Exception as e:
        print(f"Lỗi Claude API cho '{title}': {e}")
        return f"Không thể tóm tắt: {title}"

def parse_rss_feed(url, source_name):
    """Parse RSS feed và lấy bài viết mới"""
    try:
        print(f"Đang truy cập RSS: {url}")
        feed = feedparser.parse(url)
        
        if not feed.entries:
            print(f"Không tìm thấy entries trong RSS feed")
            return []
        
        print(f"Tìm thấy {len(feed.entries)} entries trong RSS feed")
        articles = []
        
        for entry in feed.entries:
            try:
                # Xử lý ngày tháng
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()
                
                # Lấy tất cả bài viết trong 7 ngày qua
                if published > datetime.now() - timedelta(days=7):
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': published,
                        'source': source_name
                    })
                    print(f"Thêm bài viết: {entry.title[:50]}...")
                    
            except Exception as e:
                print(f"Lỗi xử lý entry: {e}")
                continue
        
        return articles
        
    except Exception as e:
        print(f"Lỗi parse RSS {url}: {e}")
        return []

def create_email_html(articles):
    """Tạo email HTML"""
    current_date = datetime.now().strftime('%d/%m/%Y')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.4; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #c8102e; color: white; padding: 20px; text-align: center; border-radius: 8px; }}
            .source-section {{ margin: 30px 0; }}
            .article {{ background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #c8102e; }}
            .article-title {{ font-weight: bold; color: #2c3e50; margin-bottom: 10px; font-size: 18px; }}
            .summary {{ 
                    margin-bottom: 15px; 
                    color: #34495e; 
                    line-height: 1.4; 
                    white-space: pre-line;
                    word-wrap: break-word;
                }}
            .read-more {{ color: #c8102e; text-decoration: none; font-weight: bold; }}
            .read-more:hover {{ text-decoration: underline; }}
            .footer {{ text-align: center; margin-top: 40px; color: #7f8c8d; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📰 Tóm Tắt VnExpress Góc Nhìn</h1>
            <p>Tuần {current_date}</p>
        </div>
        <div class="source-section">
            <h2 style="color: #c8102e;">VnExpress Góc Nhìn</h2>
    """

    for article in articles:
        # Xử lý format để hiển thị đẹp hơn
        formatted_summary = article['summary'].replace('**', '<strong>').replace('</strong><strong>', '</strong> <strong>')

        html += f"""
        <div class="article">
            <div class="article-title">{article['title']}</div>
            <div class="summary">{formatted_summary}</div>
            <a href="{article['link']}" class="read-more" target="_blank">Đọc bài gốc →</a>
        </div>
        """
    html += """
            </div>
            <div class="footer">
                <p>Tạo tự động bởi Claude AI • VnExpress Góc Nhìn</p>
            </div>
        </body>
        </html>
        """
    return html

def send_email(html_content):
    """Gửi email"""
    sender_email = os.environ.get('GMAIL_EMAIL')
    sender_password = os.environ.get('GMAIL_APP_PASSWORD')
    recipient_email = os.environ.get('RECIPIENT_EMAIL')
    
    # Kiểm tra có đủ thông tin không
    if not all([sender_email, sender_password, recipient_email]):
        print("❌ Thiếu thông tin email trong environment variables")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"📰 VnExpress Góc Nhìn - Tuần {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("✅ Email gửi thành công!")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")
        return False

def main():
    """Hàm chính"""
    print(f"🚀 Bắt đầu tóm tắt VnExpress Góc Nhìn - {datetime.now()}")
    
    # Kiểm tra API key
    if not os.environ.get('CLAUDE_API_KEY'):
        print("❌ Thiếu CLAUDE_API_KEY trong environment variables")
        return
    
    all_articles = []
    
    # Lấy bài viết từ VnExpress
    for source_name, rss_url in RSS_FEEDS.items():
        print(f"📡 Đang lấy bài từ {source_name}...")
        articles = parse_rss_feed(rss_url, source_name)
        all_articles.extend(articles)
        print(f"   Tìm thấy {len(articles)} bài viết mới")
    
    if not all_articles:
        print("❌ Không tìm thấy bài viết mới nào")
        return
    
    print(f"📝 Đang xử lý {len(all_articles)} bài viết với Claude...")
    
    # Tạo tóm tắt với Claude
    processed_articles = []
    for i, article in enumerate(all_articles):
        print(f"   Xử lý bài {i+1}/{len(all_articles)}: {article['title'][:50]}...")
        
        full_text = get_article_text(article['link'])
        summary = summarize_with_claude(article['title'], full_text, article['source'])
        
        processed_articles.append({
            'title': article['title'],
            'summary': summary,
            'link': article['link'],
            'source': article['source']
        })
        
        time.sleep(1)  # Tránh spam Claude API
    
    # Tạo và gửi email
    if processed_articles:
        print("📧 Đang tạo email...")
        email_content = create_email_html(processed_articles)
        
        success = send_email(email_content)
        if success:
            print(f"✅ Đã gửi tóm tắt với {len(processed_articles)} bài viết!")
        else:
            print("❌ Gửi email thất bại")
    else:
        print("❌ Không có bài viết để xử lý")

if __name__ == "__main__":
    main()
