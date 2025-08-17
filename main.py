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
    """Lấy full text từ URL bài báo VnExpress - VỚI DEBUG LOGS"""
    print(f"   🌐 [DEBUG] Bắt đầu crawl: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print(f"   📡 [DEBUG] Gửi request...")
        response = requests.get(url, headers=headers, timeout=20)
        print(f"   📊 [DEBUG] Response status: {response.status_code}")
        print(f"   📄 [DEBUG] HTML length: {len(response.content)} bytes")
        print(f"   🔤 [DEBUG] Encoding: {response.encoding}")
        
        if response.status_code != 200:
            print(f"   ❌ [DEBUG] HTTP Error: {response.status_code}")
            return f"HTTP Error {response.status_code} khi truy cập {url}"
        
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        print(f"   🍲 [DEBUG] BeautifulSoup parsed successfully")
        
        # VnExpress specific selectors
        content_parts = []
        
        # 1. Lấy description/summary
        print(f"   🔍 [DEBUG] Tìm description...")
        description = soup.find('p', class_='description')
        if description:
            desc_text = description.get_text().strip()
            content_parts.append(desc_text)
            print(f"   ✅ [DEBUG] Tìm thấy description: {len(desc_text)} ký tự")
            print(f"   📝 [DEBUG] Description preview: {desc_text[:100]}...")
        else:
            print(f"   ❌ [DEBUG] Không tìm thấy description")
        
        # 2. Lấy nội dung chính - VnExpress dùng class 'Normal'
        print(f"   🔍 [DEBUG] Tìm class Normal...")
        normal_content = soup.find_all('p', class_='Normal')
        if normal_content:
            print(f"   ✅ [DEBUG] Tìm thấy {len(normal_content)} đoạn Normal")
            for i, p in enumerate(normal_content):
                text = p.get_text().strip()
                if text and len(text) > 20:
                    content_parts.append(text)
                    if i < 3:  # Chỉ log 3 đoạn đầu
                        print(f"   📝 [DEBUG] Normal {i+1}: {text[:80]}...")
        else:
            print(f"   ❌ [DEBUG] Không tìm thấy class Normal")
        
        # 3. Fallback: thử các selector khác
        if len(content_parts) < 2:
            print("   🆘 [DEBUG] Fallback - thử các selector khác...")
            selectors = [
                'article.fck_detail p',
                '.content_detail p', 
                '.article-content p',
                '.content-detail p',
                'div.fck_detail p',
                '.Normal',
                'p'
            ]
            
            for selector in selectors:
                print(f"   🔍 [DEBUG] Thử selector: {selector}")
                elements = soup.select(selector)
                if elements:
                    print(f"   ✅ [DEBUG] Tìm thấy {len(elements)} elements với {selector}")
                    temp_parts = []
                    for i, elem in enumerate(elements[:5]):  # Chỉ test 5 elements đầu
                        text = elem.get_text().strip()
                        if text and len(text) > 30:
                            temp_parts.append(text)
                            if i < 2:
                                print(f"   📝 [DEBUG] Element {i+1}: {text[:80]}...")
                    
                    if len(temp_parts) > len(content_parts):
                        content_parts = temp_parts
                        print(f"   🎯 [DEBUG] Chọn selector {selector} với {len(temp_parts)} đoạn")
                        break
                else:
                    print(f"   ❌ [DEBUG] Không tìm thấy với {selector}")
        
        # 4. Final fallback
        if not content_parts:
            print("   🆘 [DEBUG] Final fallback - lấy tất cả text")
            # Xóa các thẻ không cần thiết
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                element.decompose()
            
            all_text = soup.get_text()
            paragraphs = [p.strip() for p in all_text.split('\n') if p.strip() and len(p.strip()) > 50]
            content_parts = paragraphs[:10]
            print(f"   📄 [DEBUG] Fallback lấy được {len(content_parts)} đoạn")
        
        # Ghép tất cả lại
        full_text = '\n\n'.join(content_parts)
        
        print(f"   📊 [DEBUG] FINAL RESULT:")
        print(f"   📝 [DEBUG] - Tổng content parts: {len(content_parts)}")
        print(f"   📏 [DEBUG] - Độ dài full text: {len(full_text)} ký tự")
        print(f"   📋 [DEBUG] - Preview: {full_text[:200]}...")
        
        # Kiểm tra content có đủ dài không
        if len(full_text) < 100:
            print(f"   ⚠️  [DEBUG] Content quá ngắn ({len(full_text)} ký tự)")
            return f"Content quá ngắn từ {url}. Có thể bị block hoặc structure thay đổi."
        
        print(f"   ✅ [DEBUG] Successfully crawled {len(full_text)} characters")
        return full_text[:4000]
        
    except Exception as e:
        print(f"   💥 [DEBUG] EXCEPTION occurred: {type(e).__name__}")
        print(f"   💥 [DEBUG] Exception message: {str(e)}")
        import traceback
        print(f"   💥 [DEBUG] Traceback: {traceback.format_exc()}")
        return f"Exception khi crawl {url}: {str(e)}"

def summarize_with_claude(title, content, source):
    """Tạo tóm tắt bằng Claude - VỚI DEBUG LOGS"""
    print(f"   🤖 [DEBUG] Bắt đầu gọi Claude API...")
    print(f"   📄 [DEBUG] Input content length: {len(content)} ký tự")
    print(f"   📋 [DEBUG] Content preview: {content[:150]}...")
    
    if not content or len(content.strip()) < 50:
        print(f"   ❌ [DEBUG] Content quá ngắn hoặc empty: {len(content)} ký tự")
        return f"Không thể truy cập bài viết: {title}"
    
    prompt = f"""Viết tóm tắt chi tiết bài viết theo yêu cầu sau bằng tiếng Việt:

Yêu cầu:
- Bắt đầu ngay bằng quan điểm chính, không viết dòng mở đầu "Tóm tắt bài viết..."
- Bao gồm quan điểm chính và các lập luận ủng hộ
- Các lập luận cần trình bày xuống dòng cho dễ đọc  
- Không quá 250 chữ
- Không lặp lại tiêu đề trong nội dung tóm tắt
- Tập trung vào những thông tin quan trọng và ý kiến của tác giả

Tiêu đề: {title}

Nội dung: {content}

Tóm tắt chi tiết:"""

    try:
        print(f"   📡 [DEBUG] Gửi request tới Claude API...")
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=600,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        
        summary = message.content[0].text.strip()
        print(f"   ✅ [DEBUG] Claude API success!")
        print(f"   📝 [DEBUG] Summary length: {len(summary)} ký tự")
        print(f"   📋 [DEBUG] Summary preview: {summary[:100]}...")
        return summary
        
    except Exception as e:
        print(f"   💥 [DEBUG] Claude API EXCEPTION: {type(e).__name__}")
        print(f"   💥 [DEBUG] Claude error message: {str(e)}")
        return f"Lỗi Claude API cho '{title}': {str(e)}"

def parse_rss_feed(url, source_name):
    """Parse RSS feed và lấy bài viết mới"""
    try:
        print(f"📡 [DEBUG] Truy cập RSS: {url}")
        feed = feedparser.parse(url)
        
        if not feed.entries:
            print(f"❌ [DEBUG] Không tìm thấy entries trong RSS feed")
            return []
        
        print(f"✅ [DEBUG] Tìm thấy {len(feed.entries)} entries trong RSS feed")
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
                    print(f"➕ [DEBUG] Thêm bài viết: {entry.title[:50]}...")
                    
            except Exception as e:
                print(f"❌ [DEBUG] Lỗi xử lý entry: {e}")
                continue
        
        print(f"✅ [DEBUG] Tổng cộng {len(articles)} bài viết trong 7 ngày qua")
        return articles
        
    except Exception as e:
        print(f"💥 [DEBUG] Lỗi parse RSS {url}: {e}")
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
                    line-height: 1.6; 
                    white-space: pre-line;
                    word-wrap: break-word;
                }}
            .read-more {{ color: #c8102e; text-decoration: none; font-weight: bold; }}
            .read-more:hover {{ text-decoration: underline; }}
            .footer {{ text-align: center; margin-top: 40px; color: #7f8c8d; font-size: 14px; }}
            .debug-info {{ color: #888; font-size: 12px; margin-top: 10px; }}
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
        formatted_summary = article['summary'].replace('**', '<strong>').replace('</strong><strong>', '</strong> <strong>')

        html += f"""
        <div class="article">
            <div class="article-title">{article['title']}</div>
            <div class="summary">{formatted_summary}</div>
            <a href="{article['link']}" class="read-more" target="_blank">Đọc bài gốc →</a>
        </div>
        """
    html += f"""
            <div class="debug-info">
                <p>DEBUG: Đã xử lý {len(articles)} bài viết • Tạo lúc {datetime.now().strftime('%H:%M %d/%m/%Y')}</p>
            </div>
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
    
    print(f"📧 [DEBUG] Preparing to send email...")
    print(f"📧 [DEBUG] From: {sender_email}")
    print(f"📧 [DEBUG] To: {recipient_email}")
    
    # Kiểm tra có đủ thông tin không
    if not all([sender_email, sender_password, recipient_email]):
        print("❌ [DEBUG] Thiếu thông tin email trong environment variables")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"📰 VnExpress Góc Nhìn - Tuần {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    try:
        print(f"📧 [DEBUG] Connecting to SMTP server...")
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            print(f"📧 [DEBUG] Logging in...")
            server.login(sender_email, sender_password)
            print(f"📧 [DEBUG] Sending email...")
            server.send_message(msg)
        print("✅ [DEBUG] Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ [DEBUG] Email error: {e}")
        return False

def main():
    """Hàm chính"""
    print(f"🚀 [DEBUG] =====  BẮT ĐẦU CHƯƠNG TRÌNH ===== {datetime.now()}")
    
    # Kiểm tra API key
    api_key = os.environ.get('CLAUDE_API_KEY')
    if not api_key:
        print("❌ [DEBUG] Thiếu CLAUDE_API_KEY trong environment variables")
        return
    else:
        print(f"✅ [DEBUG] Claude API key found: {api_key[:20]}...")
    
    all_articles = []
    
    # Lấy bài viết từ VnExpress
    for source_name, rss_url in RSS_FEEDS.items():
        print(f"📡 [DEBUG] Đang lấy bài từ {source_name}...")
        articles = parse_rss_feed(rss_url, source_name)
        all_articles.extend(articles)
        print(f"✅ [DEBUG] Tìm thấy {len(articles)} bài viết mới từ {source_name}")
    
    if not all_articles:
        print("❌ [DEBUG] Không tìm thấy bài viết mới nào")
        return
    
    print(f"📝 [DEBUG] ===== PROCESSING {len(all_articles)} ARTICLES =====")
    
    # Tạo tóm tắt với Claude
    processed_articles = []
    for i, article in enumerate(all_articles):
        print(f"\n🔄 [DEBUG] ===== PROCESSING ARTICLE {i+1}/{len(all_articles)} =====")
        print(f"📰 [DEBUG] Title: {article['title']}")
        print(f"🔗 [DEBUG] URL: {article['link']}")
        
        # Step 1: Get article content
        full_text = get_article_text(article['link'])
        
        # Step 2: Summarize with Claude
        summary = summarize_with_claude(article['title'], full_text, article['source'])
        
        processed_articles.append({
            'title': article['title'],
            'summary': summary,
            'link': article['link'],
            'source': article['source']
        })
        
        print(f"✅ [DEBUG] Article {i+1} processed successfully")
        print(f"⏳ [DEBUG] Waiting 2 seconds...")
        time.sleep(2)
    
    # Tạo và gửi email
    if processed_articles:
        print(f"\n📧 [DEBUG] ===== CREATING EMAIL =====")
        email_content = create_email_html(processed_articles)
        
        print(f"📧 [DEBUG] ===== SENDING EMAIL =====")
        success = send_email(email_content)
        if success:
            print(f"✅ [DEBUG] ===== SUCCESS! Đã gửi tóm tắt với {len(processed_articles)} bài viết! =====")
        else:
            print("❌ [DEBUG] ===== FAILED! Gửi email thất bại =====")
    else:
        print("❌ [DEBUG] ===== NO ARTICLES TO PROCESS =====")

if __name__ == "__main__":
    main()
