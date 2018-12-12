# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html
import scrapy
import re
from scrapy.loader.processors import TakeFirst, Identity
from competitors_parser.Common import *


def field(input_processor):
    return scrapy.Field(input_processor=input_processor)


class AlloLoader(scrapy.loader.ItemLoader):
    default_output_processor = TakeFirst()


class AlloCatalogProduct(scrapy.Item):
    cat_tree_fields = {'cat_1', 'cat_2', 'cat_3', 'cat_4'}

    @staticmethod
    def get_name(items):
        def is_cut_short(name):
            return name[-3:] == '...'

        def merge_name(start, end):
            start = start[:-3]
            for i in range(min(len(start), len(end)), 0, -1):
                if start[-i:] == end[:i]:
                    return start[:-i] + end

        name = items[0].xpath('normalize-space(.//a[@class="product-name"]/text())').extract_first()
        if is_cut_short(name):
            short_name = items[0].xpath('normalize-space(.//a[@class="product-name"]/@title)').extract_first()
            merged_name = merge_name(name, short_name)
            return merged_name if merged_name is not None else name
        else:
            return name

    @staticmethod
    def get_old_price(items):
        price_selector = items[0].xpath('.//div[@class="old-price-box"]//span[contains(@class,"sum")]')
        if len(price_selector) == 1:
            return int(re.sub(r'\D', '', price_selector.xpath('normalize-space(./text())').extract_first()))

    @staticmethod
    def get_reviews_count(items):
        reviews_count = items[0].xpath('.//div[@class="ratings"]//span[@class="hidden-link amount" and text()[contains(.,"отзыв")]]/text()')
        return int(re.sub(r'\D', '', reviews_count.extract_first())) if len(reviews_count) == 1 else 0

    @staticmethod
    def get_rating(items):
        reviews_rating = items[0].xpath('.//div[@class="ratings"]//div[@class="rating-box"]//span[@class="no-display"]/text()')
        if len(reviews_rating) == 1:
            return float(reviews_rating.extract_first())

    @staticmethod
    def get_delivery_method(items):
        delivery_methods = items[0].xpath('.//div[@class="delivery-period"]//div[@class="delivery-icon"]//span/@title').extract()
        if Names.CATALOG_DELIVERY_TO_HOME_STATUS.value in delivery_methods and \
            Names.CATALOG_DELIVERY_TO_STORE_STATUS.value in delivery_methods:
            return Names.DELIVER_ALL.value
        elif Names.CATALOG_DELIVERY_TO_HOME_STATUS.value in delivery_methods:
            return Names.DELIVER_TO_HOME.value
        elif Names.CATALOG_DELIVERY_TO_STORE_STATUS.value in delivery_methods:
            return Names.DELIVER_TO_STORE.value
        else:
            raise ValueError("Can't parse delivery method")

    @staticmethod
    def get_item_actions(actions):
        actions = actions[0]
        result = ''
        if actions['label_text'] is not None:
            result += actions['label_text']
        if actions['label_url_credit'] is not None:
            result += (' ' if len(result) > 0 else '') + actions['label_url_credit']
        return result

    name = field(get_name.__func__)
    price = field(lambda item: int(re.sub(r'\D', '', item[0].xpath('normalize-space(.//div[@class="price-box"]//span[contains(@class,"sum")]/text())').extract_first())))
    old_price = field(get_old_price.__func__)
    delivery_method = field(get_delivery_method.__func__)
    actions = field(get_item_actions.__func__)
    status = field(lambda item: item[0].xpath('normalize-space(.//div[@class="buy-box"]//div[@class="button"]/button//text()[string-length(normalize-space(.))>=2])').extract_first())
    reviews_count = field(get_reviews_count.__func__)
    rating = field(get_rating.__func__)
    url = field(lambda item: re.sub(r'^.*allo.ua', 'https://allo.ua', item[0].xpath('.//a[@class="product-name"]/@href').extract_first()))
    attributes = field(lambda resps: "".join(resps[0].xpath('.//div[@class="attr-content"]//span[@class="span1" or @class="span2"]//text()').extract()))
    cat_1 = field(lambda cat_tree: (cat_tree + [''] * 3)[0])
    cat_2 = field(lambda cat_tree: (cat_tree + [''] * 3)[1])
    cat_3 = field(lambda cat_tree: (cat_tree + [''] * 3)[2])
    cat_4 = field(lambda cat_tree: ' | '.join(cat_tree[3:]) if len(cat_tree) >= 4 else '')
    site_id = field(lambda item: re.search(r'код товара: *([^ ].+[^ ]) *$', item[0].xpath('.//div[@class="grid"]//p[@class="sku"]/text()').extract_first()).group(1))
    source_url = field(lambda requests: requests[0].url)


class AlloPageProduct(scrapy.Item):
    @staticmethod
    def get_delivery_methods(responses):
        pickup_only = len(responses[0].xpath('//div[@class="product-shop"]//div[@class="in-stock" and text()[contains(.,"' + Names.PAGE_ONLY_IN_STORE_STATUS.value + '")]]').extract()) > 0
        if pickup_only:
            return Names.DELIVER_TO_STORE.value

    @staticmethod
    def get_actions(responses):
        actions = responses[0].xpath('//div[@class="product-img-box"]/div[contains(@class,"product-image")]/span')
        result = []
        for action in actions:
            text = action.xpath('./text()').extract_first()
            if text != '':
                result.append(text)
            else:
                image_url_dirty = action.xpath('./@style').extract_first()
                result.append(re.search(r'url\("(.*)"\)', image_url_dirty))
        if (len(result) > 0):
            return result

    @staticmethod
    def get_reviews_count(responses):
        reviews_count = responses[0].xpath('//div[@class="ratings"]//a[text()[contains(.,"отзыв")]]/text()')
        return int(re.sub(r'\D', '', reviews_count.extract_first())) if len(reviews_count) == 1 else 0

    @staticmethod
    def get_rating(responses):
        reviews_rating = responses[0].xpath('//span[@class="rating-value"]/text()')
        if len(reviews_rating) == 1:
            return float(reviews_rating.extract_first())

    @staticmethod
    def get_old_price(responses):
        old_price = responses[0].xpath('//div[@class="product-shop"]//div[@class="old-price-box"]//span[@class="sum"]/text()')
        if len(old_price) == 1:
            return int(re.sub(r'\D', '', old_price.extract_first()))

    name = field(lambda resps: resps[0].xpath('normalize-space(//div[@class="title-additional"]/h1[contains(@class,"product-title")]/text())').extract_first())
    price = field(lambda resps: int(re.sub(r'\D', '', resps[0].xpath('//div[@class="product-shop"]//span[@class="price"]/text()').extract_first())))
    old_price = field(get_old_price.__func__)
    delivery_method = field(Identity())
    actions = field(Identity())
    status = field(lambda resps: resps[0].xpath('normalize-space(//td[contains(@class,"two-col")]//button//text()[string-length(normalize-space(.))>3])').extract_first())
    reviews_count = field(get_reviews_count.__func__)
    rating = field(get_rating.__func__)
    url = field(lambda resps: resps[0].url)
    attributes = field(lambda resps: "".join(resps[0].xpath('//div[@class="attr-content"]//span[@class="span1" or @class="span2"]//text()').extract()))
    cat_1 = field(lambda resps: (resps[0].meta.get(Names.CAT_TREE_KEY) + [''] * 3)[0])
    cat_2 = field(lambda resps: (resps[0].meta.get(Names.CAT_TREE_KEY) + [''] * 3)[1])
    cat_3 = field(lambda resps: (resps[0].meta.get(Names.CAT_TREE_KEY) + [''] * 3)[2])
    cat_4 = field(lambda resps: ' | '.join(resps[0].meta.get(Names.CAT_TREE_KEY)[3:]) if len(resps[0].meta.get(Names.CAT_TREE_KEY)) >= 4 else '')
    site_id = field(lambda resps: re.search(r'Код товара: *([^ ].+[^ ]) *$', resps[0].xpath('//div[@class="title-additional"]/p[@class="product-ids"]/text()').extract_first()).group((1)))
    source_url = field(lambda requests: requests[0].url)
