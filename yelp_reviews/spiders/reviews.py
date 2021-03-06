# -*- coding: utf-8 -*-
import blaze as bz
import scrapy
from urllib.parse import parse_qs
from yelp_reviews.items import ReviewItem


class ReviewsSpider(scrapy.Spider):
    name = "reviews"
    allowed_domains = ["yelp.com"]
    no_item_count = 0

    def start_requests(self):
        biz_path = getattr(self, 'biz_json', 'data/biz.json')
        biz = bz.data(biz_path)
        biz = bz.compute(biz[['id', 'url']])
        self.logger.info("%s start urls for ReviewsSpider", str(len(biz)))
        for biz_id, url in biz:
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True, meta={'id': biz_id})

    def parse_review(self, rev, response):
        try:
            rev_item = ReviewItem()
            rev_item['user_id'] = parse_qs(rev.css('.user-display-name::attr(href)').extract_first().split('?')[-1])['userid']
            rev_item['biz_id'] = response.meta['id']
            rev_item['yelp_stars'] = float(rev.css('.star-img::attr(title)').extract_first().split(' ')[0])
            rev_item['date'] = rev.css('.rating-qualifier::text').extract_first().strip()
            rev_item['review'] = ''.join(rev.css('p')[0].css('::text').extract())
            rev_item['useful_count'] = int(rev.css('a.useful .count::text').extract_first() or 0)
            rev_item['funny_count'] = int(rev.css('a.funny .count::text').extract_first() or 0)
            rev_item['cool_count'] = int(rev.css('a.cool .count::text').extract_first() or 0)
            return rev_item
        except Exception as e:
            self.logger.error("Error parsing review: %s", response.meta['id'], exc_info=True)
        return None

    def parse(self, response):
        if not response.css('#logo a::text').extract_first():
            self.logger.warning('Retrying url: {}'.format(response.url))
            yield Request(url=response.url, dont_filter=True)

        reviews = response.css('div.review')[1:]  # skip first review as its for writing your own

        if 'visit_captcha' in response.url:
            self.logger.warning("Captcha hit: {}".format(response.url))
            raise scrapy.exceptions.CloseSpider("Exiting spider due to captcha...")

        if not reviews:
            self.logger.warning("No reviews found in %s", str(response.url))
            if self.no_item_count == 5:
                raise scrapy.exceptions.CloseSpider("Too many pages crawled with no items, exiting...")
            self.no_item_count += 1

        for rev in reviews: 
            rev_item = self.parse_review(rev, response)
            if rev_item:
                yield rev_item

        next_url = response.css('a.next::attr(href)').extract_first()
        if next_url:
            next_page = response.urljoin(next_url)
            yield scrapy.Request(next_page, callback=self.parse, dont_filter=True,
                                 meta={'id': response.meta['id']})
