"""OpenAI-compatible embedding client."""

from __future__ import annotations

from openai import OpenAI

from src.config import Settings, get_settings


class Embedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        key = self.settings.resolved_embedding_key()
        if not key:
            raise RuntimeError(
                "缺少 Embedding API Key：请在 .env 设置 EMBEDDING_API_KEY 或 LLM_API_KEY"
            )
        kwargs: dict = {"api_key": key}
        base = self.settings.resolved_embedding_base_url()
        if base:
            kwargs["base_url"] = base
        self.client = OpenAI(**kwargs)
        self.model = self.settings.embedding_model

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                resp = self.client.embeddings.create(model=self.model, input=batch)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(
                    "Embedding API 调用失败。请检查 .env 中 "
                    "EMBEDDING_API_KEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL "
                    "是否与向量服务匹配（聊天网关和向量网关常常不同）。"
                    f" 原始错误: {e}"
                ) from e
            ordered = sorted(resp.data, key=lambda x: x.index)
            vectors.extend([list(item.embedding) for item in ordered])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
