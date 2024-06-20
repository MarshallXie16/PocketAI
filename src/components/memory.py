import os
from uuid import uuid4
from pinecone import Pinecone
import chromadb
from chromadb.config import Settings
# from langchain.embeddings.openai import OpenAIEmbeddings
# from langchain.vectorstores import Chroma

from src.utils.AI_model_client import openai_client

'''
    Represents the long-term memory of the AI
    
    LongTermMemory: wrapper class for memory

    Available Memory Types
    - PineconeMemory: cloud-based
    - ChromaMemory: self-hosted
    - OpenAI: vectorstore

    Current Features
    - setup_memory: initializes at start of program
    - search_memory: searches memory for context
    - save_memory: saves memory to vectordb
    - save_database_txt: writes current database to db.txt (for viewing)

'''


# wrapper class for memory
class LongTermMemory:
    def __init__(self) -> None:
        self.memory = PineconeMemory() # swap out for other memory models if needed

    def setup_memory(self):
        return self.memory.setup_memory()
    
    def search_memory(self, collection_id, query):
        return self.memory.search_memory(collection_id, query)
    
    def save_memory(self, collection_id, memory):
        return self.memory.save_memory(collection_id, memory)
    
    def save_database_txt(self):
        return self.memory.save_database_txt()
    
# pinecone vector database: easy-to-use, scalable, expensive
class PineconeMemory:

    def __init__(self):
        self.embedding_model = "text-embedding-3-small"
        self.index_name = "user-pool"
        self.db = self.setup_memory()

    # Purpose: initializes Pinecone client w/ user index
    # Input: None
    # Output: index (pinecone index object)
    def setup_memory(self):
        
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

        # if index_name not in pinecone.list_indexes():
        #     pinecone.create_index(name=index_name, metric="cosine", dimension=1536)

        index = pc.Index(self.index_name)

        return index

    # Purpose: return embeddings of the given text
    # Input: text (str)
    # Output: response (dict)
    def get_embedding(self, text):
        response = openai_client.embeddings.create(input=text, model=self.embedding_model)
        print(f"Total Tokens (embeddings): {response.usage.total_tokens}")
        return response.data[0].embedding

    # Purpose: searches vectordb for similar text to the query and returns it
    # Input: collection_id (str), query (str)
    # Output: context (list of string)
    def search_memory(self, namespace, query):
        # vectorize the query
        query_vector = self.get_embedding(query)
        with open("save.txt", "w") as f:
            f.write(str(query_vector))

        # query vectordb
        results = self.db.query(
            namespace=str(namespace),
            vector=query_vector,
            top_k=3,
            include_values=False,
            include_metadata=True,
        )
        
        context = [match['metadata']['text'] for match in results['matches']]

        return context

    # Purpose: saves memory to vectordb
    # Input: namespace (int), memory (string)
    # Output: status (boolean)
    def save_memory(self, namespace, memory):
        try:
            vectors = [{"id": str(uuid4()), "values": self.get_embedding(memory), "metadata": {"text": memory}}]
            self.db.upsert(vectors=vectors, 
                           namespace=str(namespace))
            return True
        except Exception as e:
            print(f'MemoryError: {e}')
            return False

# # persistent db: self-hosted, more complexity, cheaper
# class ChromaMemory:

#     def __init__(self):
#         self.db = self.setup_memory()
#         self.retriever = self.db.as_retriever(search_kwargs={"k": 3})

#     # set up a persistent chroma vectordb
#     def setup_memory(self):
#         # initialize database
#         path = '../db'
#         settings = Settings(
#             persist_directory=path,
#             anonymized_telemetry=False
#         )
#         client = chromadb.PersistentClient(settings=settings, path=path)
#         collection = client.get_or_create_collection("User1")

#         # load the vector database
#         embedding_function = OpenAIEmbeddings()
#         vectordb = Chroma(
#             client=client,
#             collection_name="User1",
#             embedding_function=embedding_function,
#         )

#         return vectordb

#     # signature: query (string) --> context (string)
#     # searches memory for context
#     def search_memory(self, query):
#         results = self.db.max_marginal_relevance_search(query=query, k=3)
#         context = [document.page_content for document in results]
#         return context

#     # signature: memory (tuple) --> status (Boolean)
#     # save memory to vectordb
#     def save_memory(self, memory):
#         try:
#             self.db.add_texts(memory)
#             return True
#         except Exception as e:
#             print(f'MemoryError: {e}')
#             return False

#     # writes current database to db.txt (for viewing)
#     def save_database_txt(self):
#         data = self.db.get()
#         with open('../db.txt', 'w', encoding="utf-8") as file:
#             for index, chunk in enumerate(data['documents']):
#                 file.write(f'\nchunk #{index + 1}\n')
#                 file.write(chunk)

# TODO: implement OpenAI memory
class OpenAIMemory:
    pass


long_term_memory = LongTermMemory()