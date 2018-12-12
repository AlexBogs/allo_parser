import scrapy
import competitors_parser.items as items
from competitors_parser.Common import *
import re, json, io, logging


class AlloSpider(scrapy.Spider):
    name = 'allo'
    cat_1_exceptions = ['Samsung', 'Xiaomi', 'Apple', 'Рассрочка до 25 месяцев', 'ЦЕНЫ: ЯД!', 'Акции']
    cat_2_exceptions = ['Домашний проводной интернет', 'Дополнительная страховка', 'Алло гарант', 'Каталог LEGO']

    def __init__(self):
        def set_stream_log():
            self.logstream = io.StringIO()
            handler = logging.StreamHandler(self.logstream)
            handler.setLevel(logging.INFO)
            logging.getLogger().addHandler(handler)

        scrapy.Spider.__init__(self)
        set_stream_log()

    def start_requests(self):
         yield scrapy.Request(url='https://allo.ua/ru/', callback=self.parse_main)

    def parse_main(self, response: scrapy.http.Response):
        def fake_request_to_set_default_sorting():
            return response.follow(url='https://allo.ua/ru/products/mobile/dir-asc/klass-kommunikator_smartfon/order-price/0', callback=self.fake_parser)

        yield fake_request_to_set_default_sorting()
        categories = response.xpath('//a[@class="level-top"]')
        assert len(categories) in range(14, 17)
        for category in categories:
            cat_name = category.xpath('./span/text()').extract_first()
            if cat_name in self.cat_1_exceptions:
                continue
            url = category.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            yield response.follow(url, meta={Names.CAT_TREE_KEY: [cat_name]})

    def parse(self, response: scrapy.http.Response):
        def contains_exceptions(cat_tree):
            return bool(set(cat_tree) & set(self.cat_2_exceptions))

        page_type = AlloSpider.get_page_type(response)
        if page_type == PageType.OTHER:
            self.logger.info('Skipping page (unknown type) ' + response.url)
            return
        elif page_type == PageType.NO_GOODS:
            self.logger.info('Skipping page (no goods) ' + response.url)
            return
        if contains_exceptions(response.meta.get(Names.CAT_TREE_KEY)):
            self.logger.info('Skipping page (Exception) ' + response.url)
            return

        parser = MainAlloParser(self, response.copy())
        if page_type == PageType.PRODUCTS:
            return parser.yield_products()
        elif page_type == PageType.CATALOG:
            return parser.yield_catalog()
        elif page_type == PageType.GOOD:
            return parser.yield_item()

    def add_actions_and_yield_products(self, response: scrapy.http.Response):
        data = json.loads(response.body)
        for item in response.meta['result']:
            il = item['item loader']
            il.add_value('actions', data[str(item[Names.ITEM_ID_KEY])])
            yield il.load_item()

    def parse_delivery_method(self, response: scrapy.http.Response):
        data = json.loads(response.body)
        data = data['result']['forceGet']['shipping_methods']['data']
        method_names = {elem['delivery_block_label'] for elem in data}
        il = response.meta.get('item loader')
        if len(method_names) > 1 and Names.PAGE_PICK_UP_LABEL.value in method_names:
            il.add_value('delivery_method', Names.DELIVER_ALL.value)
        elif Names.PAGE_PICK_UP_LABEL.value in method_names:
            il.add_value('delivery_method', Names.DELIVER_TO_STORE.value)
        else:
            il.add_value('delivery_method', Names.DELIVER_TO_HOME.value)
        yield response.follow(url=response.meta[Names.ACTIONS_URL_KEY], callback=self.parse_actions, meta=response.meta)

    def parse_actions(self, response: scrapy.http.Response):
        data = json.loads(response.body)
        actions = data[str(response.meta[Names.ITEM_ID_KEY])]
        il = response.meta['item loader']
        result = actions['label_text']
        if actions['label_url_credit'] is not None:
            result += ' ' + actions['label_url_credit']
        il.add_value('actions', result)
        yield il.load_item()

    @staticmethod
    def get_page_type(response: scrapy.http.Response) -> PageType:
        if len(response.xpath('//ul[@class="products-grid"]')) > 0:
            return PageType.PRODUCTS
        elif len(response.xpath('//div[@class="portal-group"]')) > 0:
            return PageType.CATALOG
        elif len(response.xpath('//h1[contains(@class,"product-title")]')) > 0:
            return PageType.GOOD
        elif len(response.xpath('//h2[contains(@class,"no-products")]')) > 0:
            return PageType.NO_GOODS
        else:
            return PageType.OTHER

    def fake_parser(self, response: scrapy.http.Response):
        pass

class MainAlloParser:
    def __init__(self, spider: AlloSpider, response: scrapy.http.Response):
        self.response = response
        self.spider = spider

    def yield_catalog(self):
        cat_tree = self.response.meta.get(Names.CAT_TREE_KEY)
        self.spider.logger.info('parsing catalog ' + self.response.url + str(cat_tree))

        main_element = self.response.xpath('//div[@class="portal-group"]')
        if len(main_element) != 1:
            self.spider.logger.warning('main element is not present/multiple ones ' + self.response.url + ' ' + str(self.response.meta[Names.CAT_TREE_KEY]))
            return

        for primary_elem in main_element.xpath('.//div[@class="primary"]'):
            for request in self.parse_primary(primary_elem):
                yield request
        if self.page_is_lego():
            url = 'https://allo.ua/ru/konstruktory-lego/'
            yield self.response.follow(url=url, meta={Names.CAT_TREE_KEY: cat_tree + ['Все товары']})

        for secondary_elem in main_element.xpath('.//ul[@class="secondary"]/li[contains(@class,"group-content")]'):
            for request in self.parse_secondary(secondary_elem):
                yield request

    def page_is_lego(self):
        return self.response.url == 'https://allo.ua/ru/lego/'

    def parse_primary(self, elem: scrapy.selector.Selector):
        def parse_header():
            header = elem.xpath('./h2/a')
            assert len(header) == 1, 'problem parsing primary group header ' + self.response.url
            header = header[0]
            url = header.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            name = header.xpath('normalize-space(./text())').extract_first()
            new_cat_tree = self.response.meta.get(Names.CAT_TREE_KEY) + [name]
            return new_cat_tree, self.response.follow(url=url, meta={Names.CAT_TREE_KEY: new_cat_tree})

        def parse_all_goods(cat_tree):
            all_goods = elem.xpath('./p[@class="see-all-container"]/a')
            assert len(all_goods) == 1, 'problem parsing primary group all goods element ' + self.response.url
            all_goods = all_goods[0]
            url = all_goods.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            name = all_goods.xpath('normalize-space(./span/text())').extract_first().replace('→', '')
            new_cat_tree = cat_tree + [name]
            return self.response.follow(url=url, meta={Names.CAT_TREE_KEY: new_cat_tree})

        cat_tree, header_request = parse_header()

        sub_categories = elem.xpath('.//div[@class="entry-points-wrapper"]//a')
        assert len(sub_categories) > 0 or self.page_is_lego(), 'problem parsing primary group ' + self.response.url
        for link_elem in sub_categories:
            url = link_elem.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            parent_name = link_elem.xpath('normalize-space(./../../li[@class="entry-point-title"]//text())').extract_first()
            name = link_elem.xpath('normalize-space(./text())').extract_first()
            yield self.response.follow(url=url, meta={Names.CAT_TREE_KEY: cat_tree + [parent_name, name]})

        if not self.page_is_lego():
            yield parse_all_goods(cat_tree)
        yield header_request

    def parse_secondary(self, elem: scrapy.selector.Selector):
        def parse_header():
            header = elem.xpath('./h2/a')
            if len(header) == 0:
                name = elem.xpath('normalize-space(./h2/text())').extract_first()
                return self.response.meta.get(Names.CAT_TREE_KEY) + [name], None
            header = header[0]
            url = header.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            name = header.xpath('normalize-space(./text())').extract_first()
            new_cat_tree = self.response.meta.get(Names.CAT_TREE_KEY) + [name]
            return new_cat_tree, self.response.follow(url=url, meta={Names.CAT_TREE_KEY: new_cat_tree})

        def parse_all_goods(cat_tree):
            all_goods = elem.xpath('.//a[@class="see-all"]')
            if len(all_goods) == 0:
                return None
            assert len(all_goods) == cat_count, 'problem parsing secondary group all goods element ' + self.response.url
            all_goods = all_goods[0]
            url = all_goods.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            name = all_goods.xpath('normalize-space(./span/text())').extract_first().replace('→', '')
            new_cat_tree = cat_tree + [name]
            return self.response.follow(url=url, meta={Names.CAT_TREE_KEY: new_cat_tree})

        cat_tree, header_request = parse_header()

        sub_categories = elem.xpath('.//ul[contains(@class,"entry-point")]')
        cat_count = len(sub_categories)
        for link_elem in sub_categories.xpath('.//a[not(@class="see-all")]'):
            url = link_elem.xpath('./@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/')
            name = link_elem.xpath('normalize-space(./text())').extract_first()
            if cat_count == 1:
                new_cat_tree = cat_tree + [name]
            else:  # applicable for https://allo.ua/ru/progulka-i-otduh/ where there are 2 subgroups per top level group
                parent_name = link_elem.xpath('normalize-space(./../..//h3/text())').extract_first()
                new_cat_tree = cat_tree + [parent_name, name]
            yield self.response.follow(url=url, meta={Names.CAT_TREE_KEY: new_cat_tree})

        all_goods_request = parse_all_goods(cat_tree)
        if all_goods_request is not None:
            yield all_goods_request

        if header_request is not None:
            yield header_request
        else:
            self.spider.logger.warning('secondary no header ' + self.response.url)

    def yield_products(self):
        def item_is_available(item):
            return len(item.xpath('.//button[contains(@class, "button") and contains(@class, "btn-alert") and contains(@class, "availability")]')) == 0
        def is_last_page():
            return len(result) != len(items)

        def get_actions_request():
            actions_url = 'https://allo.ua/ru/catalog/product/getProductLabelData/?product_ids=%5B%22' + \
                          '%22%2C%22'.join([str(item[Names.ITEM_ID_KEY]) for item in result]) + \
                          '%22%5D&currentTheme=main'
            return self.response.follow(url=actions_url, meta={'result': result}, callback=self.spider.add_actions_and_yield_products)

        self.spider.logger.info('parsing products ' + self.response.url + str(self.response.meta[Names.CAT_TREE_KEY]))
        items = self.response.xpath('//ul[@class="products-grid"]/li[@class="item" and not(.//div[contains(@class,"preorder no-price")])]')
        result = [{'item loader': self.parse_product(item),
                   Names.ITEM_ID_KEY: int(re.sub(r'\D', '', item.xpath('./div[@class="item-inner"]/@id').extract_first()))}
                  for item in items if item_is_available(item)]

        yield get_actions_request()

        next_page_elem = self.response.xpath('//div[@class="toolbar-bottom"]//div[@class="pages"]//li[contains(@class,"i-next") and not(contains(@class,"disabled"))]')
        if len(next_page_elem) > 0 and not is_last_page():
            assert len(next_page_elem) == 1, 'problem with next element ' + self.response.url
            yield self.response.follow(next_page_elem[0].xpath('./a/@href').extract_first().replace('allo.ua/ua/', 'allo.ua/ru/'), meta=self.response.meta)

    def yield_item(self):
        def get_locations_status():
            pickup_only = len(self.response.xpath(
                '//div[@class="product-shop"]//div[@class="in-stock" and text()[contains(.,"' + Names.PAGE_ONLY_IN_STORE_STATUS.value + '")]]').extract()) > 0
            if pickup_only:
                return Names.DELIVER_TO_STORE
            elif len(self.response.xpath(
                '//div[@class="product-shop"]//div[@class="in-stock" and text()[contains(.,"' + Names.PAGE_DELIVERY_STATUS.value + '")]]').extract()) > 0:
                return Names.PAGE_DELIVERY_OTHER_STATUS

        def get_item_id():
            script = self.response.xpath('//script[@type="text/javascript" and text()[contains(.,"document.addEventListener(\'gaLoaded\'")]]/text()').extract_first()
            return int(re.search(r':{"id":"(\d*)","name":"', script).groups(0)[0])

        if len(self.response.xpath('//td[contains(@class,"two-col")]//button[@template="buy_card" or contains(@class,"buy")]')) == 0:
            self.spider.logger.info('Skipping item page (not available) ' + str(self.response.url))
            return
        self.response.meta[Names.ITEM_ID_KEY] = get_item_id()
        self.response.meta[Names.ACTIONS_URL_KEY] = 'https://allo.ua/ru/catalog/product/getProductLabelData/?product_ids=%5B%22' + str(self.response.meta[Names.ITEM_ID_KEY]) + '%22%5D&currentTheme=main'
        il = items.AlloLoader(item=items.AlloPageProduct())
        for key in set(il.item.fields.keys()) - {'actions', 'delivery_method', 'source_url'}:
            # print('adding ' + key)
            il.add_value(key, self.response)
        il.add_value('source_url', self.response)

        self.response.meta['item loader'] = il
        status = get_locations_status()
        if status == Names.PAGE_DELIVERY_OTHER_STATUS:
            url = 'https://allo.ua/ru/ajax/block/get?collection=%5B%7B%22conteinerId%22%3A%20%22forceGet%22%2C%20%22type%22%3A%20%22ajax%22%2C%20%22request%22%3A%20%22oggetto_cshipping%2Fshipping%2Fdata%22%2C%20%22data%22%3A%20%7B%22productId%22%3A%20' + \
                  str(self.response.meta[Names.ITEM_ID_KEY]) + '%2C%20%22cityId%22%3A%20null%7D%7D%5D&currentTheme=main'
            yield self.response.follow(url=url, callback=self.spider.parse_delivery_method, meta=self.response.meta)
        else:
            if get_locations_status() == Names.DELIVER_TO_STORE:
                il.add_value('delivery_method', Names.DELIVER_TO_STORE.value)
            yield self.response.follow(url=self.response.meta[Names.ACTIONS_URL_KEY], callback=self.spider.parse_actions, meta=self.response.meta)

    def parse_product(self, item):
        il = items.AlloLoader(item=items.AlloCatalogProduct())
        cat_tree_fields = items.AlloCatalogProduct.cat_tree_fields
        for key in set(il.item.fields.keys()) - {'actions', 'source_url'} - cat_tree_fields:
            # print('adding ' + key)
            il.add_value(key, item)
        for key in cat_tree_fields:
            # print('adding ' + key)
            il.add_value(key, self.response.meta.get(Names.CAT_TREE_KEY))
        il.add_value('source_url', self.response)
        return il
