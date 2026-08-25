from werkzeug.exceptions import HTTPException


class SubscriptionRequired(HTTPException):
    """402-equivalent: werkzeug >= 3 dropped native 402 support."""

    code = 402
    description = 'يتطلب الوصول تفعيل الاشتراك.'
