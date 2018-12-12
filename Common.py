from enum import Enum, auto


class PageType(Enum):
    PRODUCTS = auto()
    CATALOG = auto()
    GOOD = auto()
    NO_GOODS = auto()
    OTHER = auto()


class Names(Enum):
    CAT_TREE_KEY = auto()
    ITEM_ID_KEY = auto()
    ACTIONS_URL_KEY = auto()
    PAGE_ONLY_IN_STORE_STATUS = 'В магазинах Алло'
    PAGE_DELIVERY_STATUS = 'Товар в наличии'
    PAGE_PICK_UP_LABEL = 'Самовывоз из Алло'
    CATALOG_DELIVERY_TO_HOME_STATUS = 'Курьерская доставка'
    CATALOG_DELIVERY_TO_STORE_STATUS = 'Бесплатная доставка в магазины Алло'
    DELIVER_TO_STORE = 'Пикап'
    DELIVER_TO_HOME = 'Доставка'
    DELIVER_ALL = 'Пикап и доставка'
    PAGE_DELIVERY_OTHER_STATUS = auto()

