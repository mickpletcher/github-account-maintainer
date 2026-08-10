import threading
from collections.abc import Iterator, Mapping
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from github_account_maintainer.constants import CLI_NAME, GITHUB_API_VERSION


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
        response.raise_for_status()
        return response

    def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> Iterator[dict[str, Any]]:
        next_url: str | None = path
        next_params = params
        while next_url is not None:
            self._validate_url(next_url)
            response = self.get(next_url, params=next_params)
            payload = cast(object, response.json())
            if not isinstance(payload, list):
                raise TypeError("Paginated GitHub response must be a JSON array")
            for item in cast(list[object], payload):
                if not isinstance(item, dict):
                    raise TypeError("Paginated GitHub response items must be JSON objects")
                yield cast(dict[str, Any], item)
            next_url = response.links.get("next", {}).get("url")
            next_params = None

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.netloc and (parsed.scheme, parsed.netloc.lower()) != self._base_origin:
            raise ValueError("GitHub request URL changed origins")


def accepted_permissions(response: httpx.Response) -> str | None:
    return response.headers.get("X-Accepted-GitHub-Permissions")
