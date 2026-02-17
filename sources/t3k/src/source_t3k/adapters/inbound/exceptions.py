"""T3K API adapter exceptions.

Custom exceptions for T3K API client operations.
"""


class T3KAPIError(Exception):
    """Base exception for T3K API errors.

    Raised when the T3K API returns an error response (4xx, 5xx)
    or when response parsing fails.
    """

    pass


class T3KAuthenticationError(T3KAPIError):
    """Exception raised when T3K API authentication fails.

    Raised when the API returns HTTP 401 (Unauthorized).
    """

    pass


class T3KRateLimitError(T3KAPIError):
    """Exception raised when T3K API rate limit is exceeded.

    Raised when the API returns HTTP 429 (Too Many Requests).
    """

    pass
