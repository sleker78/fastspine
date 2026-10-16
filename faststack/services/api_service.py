import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError


class APIAuthConfig(BaseModel):
    """Base config for API authentication."""

    pass


class APIKeyConfig(APIAuthConfig):
    """API Key authentication."""

    api_key: str
    key_header: str = "X-API-KEY"


class APIKeySecretConfig(APIAuthConfig):
    """API Key + Secret authentication."""

    api_key_id: str
    api_key_secret: str
    key_id_header: str = "X-API-KEY-ID"
    key_secret_header: str = ""


class BearerTokenConfig(APIAuthConfig):
    """Bearer token authentication."""

    token: str
    header: str = "Authorization"


class BasicAuthConfig(APIAuthConfig):
    """Basic authentication."""

    username: str
    password: str


class CustomAuthConfig(APIAuthConfig):
    """Custom headers authentication."""

    headers: dict[str, str]


class APIError(Exception):
    """Base API error."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message)


class APIValidationError(APIError):
    """API response validation error."""

    pass


class AbstractAPIService(ABC):
    """Abstract base class for external API services.

    Provides common functionality for:
    - HTTP client management
    - Authentication handling
    - Response parsing to Pydantic models
    - Error handling and retries
    - Logging
    """

    def __init__(
        self,
        base_url: str,
        auth_config: APIAuthConfig,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = client
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            headers = self._build_auth_headers()
            headers.update(self._get_default_headers())

            self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self._client

    def _build_auth_headers(self) -> dict[str, str]:
        """Build authentication headers based on auth config."""
        headers = {}

        if isinstance(self.auth_config, APIKeyConfig):
            headers[self.auth_config.key_header] = self.auth_config.api_key

        elif isinstance(self.auth_config, APIKeySecretConfig):
            headers[self.auth_config.key_id_header] = self.auth_config.api_key_id
            headers[self.auth_config.key_secret_header] = self.auth_config.api_key_secret

        elif isinstance(self.auth_config, BearerTokenConfig):
            headers[self.auth_config.header] = f"Bearer {self.auth_config.token}"

        elif isinstance(self.auth_config, BasicAuthConfig):
            import base64

            credentials = base64.b64encode(f"{self.auth_config.username}:{self.auth_config.password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif isinstance(self.auth_config, CustomAuthConfig):
            headers.update(self.auth_config.headers)

        return headers

    @abstractmethod
    def _get_default_headers(self) -> dict[str, str]:
        """Override to provide service-specific default headers."""
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        url = self._build_url(endpoint)
        request_headers = headers or {}

        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(
                    method=method, url=url, json=data, params=params, headers=request_headers
                )

                if response.status_code < 500:  # Don't retry client errors
                    return response

                # Server error - retry
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue

                return response

            except httpx.TimeoutException as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                raise APIError(f"Request timeout after {self.max_retries} attempts", response_data=None) from e

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                raise APIError(f"Request failed: {str(e)}", response_data=None) from e

        return httpx.Response(status_code=500)  # Fallback, should not reach here

    def _parse_response[T: BaseModel](self, response: httpx.Response, model_class: type[T]) -> T:
        """Parse HTTP response to Pydantic model."""
        try:
            # Check for HTTP errors
            if not response.is_success:
                error_data = None
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {"detail": response.text}

                raise APIError(
                    f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    response_data=error_data,
                )

            # Parse response data
            response_data = response.json()
            return model_class(**response_data)

        except ValidationError as e:
            raise APIValidationError(
                f"Invalid response format: {str(e)}",
                status_code=response.status_code,
                response_data=response_data if "response_data" in locals() else None,
            ) from e
        except Exception as e:
            raise APIError(f"Response parsing failed: {str(e)}") from e

    async def _get[T: BaseModel](
        self, endpoint: str, params: dict | None = None, response_model: type[T] | None = None
    ) -> dict | T:
        """Make GET request."""
        response = await self._make_request("GET", endpoint, params=params)

        if response_model:
            return self._parse_response(response, response_model)

        response.raise_for_status()
        return response.json()

    async def _post[T: BaseModel](
        self, endpoint: str, data: dict | None = None, response_model: type[T] | None = None
    ) -> dict | T:
        """Make POST request."""
        response = await self._make_request("POST", endpoint, data=data)

        if response_model:
            return self._parse_response(response, response_model)

        response.raise_for_status()
        return response.json()

    async def _post_model[T: BaseModel](
        self,
        endpoint: str,
        response_model: type[T],
        data: dict[str, Any] | None = None,
    ) -> T:
        """Make POST request."""
        response = await self._make_request("POST", endpoint, data=data)

        return self._parse_response(response, response_model)

    async def _put[T: BaseModel](
        self, endpoint: str, data: dict | None = None, response_model: type[T] | None = None
    ) -> dict | T:
        """Make PUT request."""
        response = await self._make_request("PUT", endpoint, data=data)

        if response_model:
            return self._parse_response(response, response_model)

        response.raise_for_status()
        return response.json()

    async def _delete[T: BaseModel](self, endpoint: str, response_model: type[T] | None = None) -> dict | T | None:
        """Make DELETE request."""
        response = await self._make_request("DELETE", endpoint)

        if response.status_code == 204:  # No content
            return None

        if response_model:
            return self._parse_response(response, response_model)

        response.raise_for_status()
        return response.json()

    @classmethod
    def dependency(cls, *args, **kwargs):
        """Create a FastAPI dependency that returns a default instance of this service."""

        def factory() -> "AbstractAPIService":
            return cls(*args, **kwargs)

        return factory

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, *args):
        """Context manager exit."""
        await self.close()
