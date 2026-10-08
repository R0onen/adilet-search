"""Qdrant access. BE-01: connectivity and alias resolution; collection building comes in BE-02."""

from qdrant_client import AsyncQdrantClient


class QdrantStore:
    def __init__(self, client: AsyncQdrantClient, alias: str) -> None:
        self.client = client
        self.alias = alias

    @classmethod
    def from_url(
        cls, url: str, alias: str, timeout_s: float, api_key: str | None = None
    ) -> "QdrantStore":
        client = AsyncQdrantClient(
            url=url, api_key=api_key, timeout=int(max(1, timeout_s)), check_compatibility=False
        )
        return cls(client, alias)

    async def aclose(self) -> None:
        await self.client.close()

    async def ping(self) -> None:
        await self.client.get_collections()

    async def alias_target(self) -> str | None:
        """The collection the alias points to, or None if the alias does not exist yet."""
        response = await self.client.get_aliases()
        for alias in response.aliases:
            if alias.alias_name == self.alias:
                return alias.collection_name
        return None
