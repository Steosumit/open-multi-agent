"""
This module contains code to manage long term memory using ChromaDB
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import chromadb
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_mistralai import MistralAIEmbeddings
from langchain_core.documents import Document

from core.config import EMBEDDING_MODEL


class LongTermMemory:
    def __init__(self, user_id: str = "default_user"):
        """
        Initialize ChromaDB client and embedding function.
        We use an HttpClient to connect to the docker container.
        """
        self.user_id = user_id

        # Initialize Embeddings
        # self.embedding_function = GoogleGenerativeAIEmbeddings(
        #     model=EMBEDDING_MODEL,
        # )
        self.embedding_function = MistralAIEmbeddings(model=EMBEDDING_MODEL)  # TODO: switch to Mistral when available

        # Initialize Vector Store (HTTP Client)
        # The Chroma server (Docker) handles persistence via volume mount
        self.client = chromadb.HttpClient(host="localhost", port=8000)

        self.vector_store = Chroma(
            client=self.client,
            collection_name=f"long_term_memory_{user_id}",
            embedding_function=self.embedding_function,
        )

    def store(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Embed and save a summary or text chunk to the vector database.
        Returns the ID of the stored document.
        """
        if metadata is None:
            metadata = {}

        # Add timestamp and user_id to metadata
        metadata["timestamp"] = datetime.now(timezone.utc).isoformat()
        metadata["user_id"] = self.user_id

        doc = Document(page_content=text, metadata=metadata)

        # Add to vector store
        ids = self.vector_store.add_documents([doc])  # vector DB id
        logging.info(f"Stored long-term memory with ID: {ids[0]}")
        return ids[0]

    async def store_async(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Async wrapper for store method to run in a background thread.
        """
        import asyncio

        return await asyncio.to_thread(self.store, text, metadata)
        # TODO: review the asyncio working and AIMessage response behavior

    def search(self, query: str, k: int = 3) -> List[Document]:
        """
        Retrieve top k relevant documents for a given query.
        """
        results = self.vector_store.similarity_search(query, k=k)
        logging.info(
            f"Retrieved {len(results)} long-term memories for query: '{query}'"
        )
        return results

    def clear(self):
        """
        Clear the memory for this user.
        """
        try:
            self.vector_store.delete_collection()
        except Exception as e:
            logging.warning(f"Could not delete collection: {e}")

        # Re-initialize to ensure collection exists for future use
        self.vector_store = Chroma(
            client=self.client,
            collection_name=f"long_term_memory_{self.user_id}",
            embedding_function=self.embedding_function,
        )
        logging.info(f"Cleared long-term memory for user: {self.user_id}")
