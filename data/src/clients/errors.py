from errors import CryptoTaxesError


class PriceClientError(CryptoTaxesError):
    """Base for operational failures raised by a low-level price API client.

    Signals that a lookup could not be completed (network error, HTTP 4xx/5xx after
    retries, malformed payload, bad credentials) rather than that a price is genuinely
    unavailable. These must propagate as hard failures and never be treated as a missing
    price.
    """
