from ai import AIProvider


class WebProvider:
    def __init__(self, ai: AIProvider | None = None):
        self.ai = ai or AIProvider()

    async def search(self, query: str) -> list[dict]:
        text = await self.ai.chat(
            f"Search the web for this query and give a concise answer with the most useful current facts and source names/links when available:\n{query}",
            web_search=True,
        )
        return [{"title": "Web search result", "snippet": text, "url": ""}]
