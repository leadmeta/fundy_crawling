BOT_NAME = "fundy_crawler"

SPIDER_MODULES = ["fundy_crawler.spiders"]
NEWSPIDER_MODULE = "fundy_crawler.spiders"

# Browser Emulation (Playwright) Configure
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Crawl responsibly by identifying yourself on the user-agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 16

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = 1.5
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 8
# CONCURRENT_REQUESTS_PER_IP = 8

# 강제 종료 제어 로직 설정 (각 스파이더 단위로 안전 종료 보장. 1,000건 제한)
CLOSESPIDER_ITEMCOUNT = 1000
CLOSESPIDER_TIMEOUT = 3600  # 비상 1시간 런타임 제어

# Enable and configure HTTP caching (disabled by default)
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"

# Item Pipelines configuration
ITEM_PIPELINES = {
    "fundy_crawler.pipelines.NoticeFilterPipeline": 200,
    "fundy_crawler.pipelines.AttachmentTextExtractionPipeline": 250,
    "fundy_crawler.pipelines.RegexFallbackExtractionPipeline": 270,
    "fundy_crawler.pipelines.SQLitePipeline": 300,
    "fundy_crawler.pipelines.MeilisearchPipeline": 400,
}

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"
