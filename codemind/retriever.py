import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import logging

class CodeRetriever:
    """Handles vector embedding and semantic search of code snippets."""
    
    def __init__(self, db_path="./codemind_data/chroma"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        # Using a standard sentence-transformer model for embeddings
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="code_snippets",
            embedding_function=self.emb_fn
        )

    def index_codebase(self, parsed_data_map: dict, root_path: str):
        """
        Index code snippets from the parsed data map.
        parsed_data_map: { file_path: { "functions": [...], "classes": [...] } }
        """
        ids = []
        documents = []
        metadatas = []

        for file_path, data in parsed_data_map.items():
            relative_path = str(Path(file_path).relative_to(root_path))
            
            # Index functions
            for func in data.get("functions", []):
                snippet_id = f"{relative_path}:{func['name']}"
                # Construct a searchable string including docstring and params
                doc = f"Function: {func['name']}\nParams: {func['params']}\nDocstring: {func['docstring']}"
                
                ids.append(snippet_id)
                documents.append(doc)
                metadatas.append({
                    "file_path": relative_path,
                    "name": func["name"],
                    "type": "function",
                    "start_line": func["start_line"]
                })

            # Index classes
            for cls in data.get("classes", []):
                snippet_id = f"{relative_path}:{cls['name']}"
                ids.append(snippet_id)
                documents.append(f"Class: {cls['name']}")
                metadatas.append({
                    "file_path": relative_path,
                    "name": cls["name"],
                    "type": "class"
                })

        if ids:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            logging.info(f"Indexed {len(ids)} snippets into ChromaDB.")

    def search(self, query: str, top_k: int = 5):
        """Perform semantic search for code snippets."""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        # Reformat results for easier consumption
        formatted = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                formatted.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                })
        return formatted
