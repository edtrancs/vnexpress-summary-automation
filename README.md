## Problem Statement

I'm a massive fan of VNExpress *Góc nhìn* column, but Reading every article is time-consuming. There is a need for a simple way to capture the essence of multiple articles without manually going through each one.

## Tech Stack

* **Python** for scripting and orchestration
* **BeautifulSoup4** and **Requests** for crawling and parsing
* **Claude API** for summarization
* **Gmail** for email service for delivery
* **launchd** on macOS for job scheduling

![User Flow](docs/images/VNE-thumb.png)

## Implementation

1. Crawling is executed locally on macOS (with scheduling handled by launchd), since VNExpress blocks IPs from outside Vietnam
2. Preprocess text to remove HTML noise and formatting issues
3. Send article text to Claude for summarization
4. Store the summaries in Markdown or JSON for easy reference
5. Format the results into an email digest
6. Schedule the workflow to run daily at 8 AM on Monday using `launchd`

## Results

* Automate the delivery of weekly insights on Monday to my Gmail
* Help me save tons of time compared to reading full articles
