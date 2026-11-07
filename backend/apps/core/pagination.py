"""Page-number pagination with `?page=&pageSize=` (max 100).

Page numbers rather than cursors because recruiters jump between result pages and the frontend
shows "page 3 of 8"; our tables are small enough that OFFSET is cheap.
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    # CamelCaseMiddleWare has already turned ?pageSize= into page_size by the time we read it.
    page_size_query_param = "page_size"
    max_page_size = 100
