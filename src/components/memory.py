from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma, Pinecone
import chromadb
from chromadb.config import Settings
import pinecone
import os

# Mimics long-term memory using vectordb
# Can store, augment, and retrieve long-term memory
os.environ["PINECONE_API_KEY"] = "5c37abab-6352-4786-8b57-377a06b3c51d"
os.environ["PINECONE_ENV"] = "gcp-starter"


# pinecone vector database: easy-to-use, scalable, expensive
class PineconeMemory:

    def __init__(self):
        self.db = self.setup_memory()
        self.retriever = self.db.as_retriever(search_kwargs={"k": 3})

    # set up a persistent pinecone vectordb
    def setup_memory(self):
        # initialize database
        pinecone.init(api_key=os.getenv("PINECONE_API_KEY"),
                      environment=os.getenv("PINECONE_ENV")
                      )

        index_name = "user-pool"
        if index_name not in pinecone.list_indexes():
            pinecone.create_index(name=index_name, metric="cosine", dimension=1536)
        index = pinecone.Index(index_name=index_name)

        embedding_function = OpenAIEmbeddings()

        vectordb = Pinecone(index, embedding_function.embed_query, "text")

        return vectordb

    # signature: query (string) --> context (string)
    # searches a given collection's memory for context
    def search_memory(self, collection_id, query):
        results = self.db.max_marginal_relevance_search(query=query, k=3, namespace=str(collection_id))
        context = [document.page_content for document in results]
        return context

    # signature: memory (tuple) --> status (Boolean)
    # save memory to vectordb
    def save_memory(self, collection_id, memory):
        try:
            self.db.add_texts(memory, namespace=str(collection_id))
            return True
        except Exception as e:
            print(f'MemoryError: {e}')
            return False

    # writes current database to db.txt (for viewing)
    # for debugging
    def save_database_txt(self):
        data = self.db.get()
        with open('../db.txt', 'w', encoding="utf-8") as file:
            for index, chunk in enumerate(data['documents']):
                file.write(f'\nchunk #{index + 1}\n')
                file.write(chunk)


# persistent db: self-hosted, more complexity, cheaper
class ChromaMemory:

    def __init__(self):
        self.db = self.setup_memory()
        self.retriever = self.db.as_retriever(search_kwargs={"k": 3})

    # set up a persistent chroma vectordb
    def setup_memory(self):
        # initialize database
        path = '../db'
        settings = Settings(
            persist_directory=path,
            anonymized_telemetry=False
        )
        client = chromadb.PersistentClient(settings=settings, path=path)
        collection = client.get_or_create_collection("User1")

        # load the vector database
        embedding_function = OpenAIEmbeddings()
        vectordb = Chroma(
            client=client,
            collection_name="User1",
            embedding_function=embedding_function,
        )

        return vectordb

    # signature: query (string) --> context (string)
    # searches memory for context
    def search_memory(self, query):
        results = self.db.max_marginal_relevance_search(query=query, k=3)
        context = [document.page_content for document in results]
        return context

    # signature: memory (tuple) --> status (Boolean)
    # save memory to vectordb
    def save_memory(self, memory):
        try:
            self.db.add_texts(memory)
            return True
        except Exception as e:
            print(f'MemoryError: {e}')
            return False

    # writes current database to db.txt (for viewing)
    def save_database_txt(self):
        data = self.db.get()
        with open('../db.txt', 'w', encoding="utf-8") as file:
            for index, chunk in enumerate(data['documents']):
                file.write(f'\nchunk #{index + 1}\n')
                file.write(chunk)


long_term_memory = PineconeMemory()
