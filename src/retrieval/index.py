from __future__ import annotations

from dataclasses import dataclass

import chromadb
import pandas as pd

from core.config import Settings
from retrieval.embeddings import MiniLMEmbeddings


NON_SCALAR_METADATA_COLUMNS = ["authors", "categories"]


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict


class LocalEmbeddingIndex:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = chromadb.PersistentClient(
            path=str(settings.paths.chroma_dir)
        )
        self.embedder = MiniLMEmbeddings(settings.embedding_model)

    def build_from_dataframe(
        self,
        df: pd.DataFrame,
        collection_name: str,
    ) -> chromadb.Collection:
        """
        Tao hoac ghi de mot collection tu dataframe sach.
        """
        existing = [c.name for c in self.client.list_collections()]
        if collection_name in existing:
            self.client.delete_collection(collection_name)

        collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        texts = df["text_for_embedding"].tolist()
        paper_ids = df["paper_id"].astype(str).tolist()

        # ChromaDB requires unique IDs.
        # Duplicate rows are kept but receive unique Chroma IDs.
        seen_ids: dict[str, int] = {}
        ids: list[str] = []

        for paper_id in paper_ids:
            count = seen_ids.get(paper_id, 0)

            if count == 0:
                ids.append(paper_id)
            else:
                ids.append(f"{paper_id}__duplicate_{count}")

            seen_ids[paper_id] = count + 1

        embeddings = self.embedder.embed_documents(texts)

        metadata_df = df.drop(
            columns=["text_for_embedding"] + NON_SCALAR_METADATA_COLUMNS
        )
        metadatas = metadata_df.to_dict(orient="records")

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return collection

    def _get_collection(
        self,
        collection_name: str | None = None,
    ) -> chromadb.Collection:
        name = collection_name or self.settings.baseline_collection_name
        return self.client.get_collection(name=name)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        collection_name: str | None = None,
    ) -> list[SearchResult]:
        collection = self._get_collection(collection_name)
        k = top_k or self.settings.top_k

        query_embedding = self.embedder.embed_query(query)

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        results: list[SearchResult] = []

        for paper_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}

            results.append(
                SearchResult(
                    paper_id=str(paper_id),
                    title=str(metadata.get("title", "")),
                    score=1.0 - float(distance),
                    content=str(document or ""),
                    metadata=metadata,
                )
            )

        return results

    def lookup(
        self,
        title: str,
        collection_name: str | None = None,
    ) -> dict | None:
        collection = self._get_collection(collection_name)

        result = collection.get(
            where={"title": title},
            include=["documents", "metadatas"],
            limit=1,
        )

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        if not ids:
            return None

        metadata = metadatas[0] or {}

        return {
            "paper_id": str(ids[0]),
            "title": str(metadata.get("title", title)),
            "content": str(documents[0] or ""),
            "metadata": metadata,
        }