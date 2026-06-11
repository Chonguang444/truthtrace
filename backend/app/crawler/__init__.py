from app.crawler.base import BaseCrawler
from app.crawler.general import GeneralCrawler
from app.crawler.weibo import WeiboCrawler
from app.crawler.zhihu import ZhihuCrawler
from app.crawler.wechat import WechatCrawler
from app.crawler.resolver import URLResolver
from app.crawler.media_crawler import MediaCrawler, detect_platform, MediaCrawlResult

__all__ = [
    "BaseCrawler",
    "GeneralCrawler",
    "WeiboCrawler",
    "ZhihuCrawler",
    "WechatCrawler",
    "URLResolver",
    "MediaCrawler",
    "detect_platform",
    "MediaCrawlResult",
]
