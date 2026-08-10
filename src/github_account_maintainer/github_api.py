import threading
from collections.abc import Iterator, Mapping
from typing import cast
from urllib.parse import urlparse

import httpx

from github_account_maintainer.constants import CLI_NAME, GITHUB_API_VERSION


class GitHubApiError(RuntimeError):
    def __init__(self, response: httpx.Response) -> None:
        self.status_code = response.status_code
        self.retry_after = response.headers.get("Retry-After")
        self.rate_limit_reset = response.headers.get("X-RateLimit-Reset")
        self.accepted_permissions = response.headers.get("X-Accepted-GitHub-Permissions")
        self.kind = self._classify(response)
        super().__init__(f"GitHub API request failed: {self.kind} ({self.status_code})")

    @staticmethod
    def _classify(response: httpx.Response) -> str:
        if response.status_code == 401:
            return "authentication"
        if response.status_code == 429 or (
            response.status_code == 403
            and (response.headers.get("Retry-After") or response.headers.get("X-RateLimit-Remaining") == "0")
        ):
            return "rate_limit"
        if response.status_code == 403:
            return "authorization"
        if response.status_code == 404:
            return "not_found"
        if response.status_code >= 500:
            return "server"
        return "api_error"


class GitHubTransportError(RuntimeError):
    pass


class GitHubApiClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.github.com",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        parsed_base_url = urlparse(self._base_url)
        self._base_origin = (parsed_base_url.scheme, parsed_base_url.netloc.lower())
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": CLI_NAME,
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
            follow_redirects=False,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "GitHubApiClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, *, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        self._validate_url(path)
        try:
            with self._lock:
                response = self._client.get(path, params=params)
                for _redirect in range(5):
                    if not response.is_redirect:
                        break
                    location = response.headers.get("Location")
                    if location is None:
                        raise ValueError("GitHub redirect response did not include a location")
                    redirect_url = str(response.url.join(location))
                    self._validate_url(redirect_url)
                    response = self._client.get(redirect_url)
                else:
                    raise ValueError("GitHub response exceeded the redirect limit")
        except httpx.RequestError as error:
            raise GitHubTransportError(f"GitHub transport failed: {type(error).__name__}") from None
        if response.is_error:
            raise GitHubApiError(response)
        return response

    def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> Iterator[dict[str, object]]:
        for _response, items in self.paginate_pages(path, params=params):
            yield from items

    def paginate_pages(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> Iterator[tuple[httpx.Response, tuple[dict[str, object], ...]]]:
        next_url: str | None = path
        next_params = params
        while next_url is not None:
            self._validate_url(next_url)
            response = self.get(next_url, params=next_params)
            payload = cast(object, response.json())
            if not isinstance(payload, list):
                raise TypeError("Paginated GitHub response must be a JSON array")
            items: list[dict[str, object]] = []
            for item in cast(list[object], payload):
                if not isinstance(item, dict):
                    raise TypeError("Paginated GitHub response items must be JSON objects")
                items.append(cast(dict[str, object], item))
            yield response, tuple(items)
            next_url = response.links.get("next", {}).get("url")
            next_params = None

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.netloc and (parsed.scheme, parsed.netloc.lower()) != self._base_origin:
            raise ValueError("GitHub request URL changed origins")


def accepted_permissions(response: httpx.Response) -> str | None:
    return response.headers.get("X-Accepted-GitHub-Permissions")
