
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

subject_files = [
    ("معلم الفيزياء", "book-alfizya-1.pdf", "db_physics"),
    ("معلم الكيمياء", "book-kimya2-1.pdf", "db_chemistry"),
    ("معلم الأحياء", "book-alahya-1.pdf", "db_biology"),
]

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/distiluse-base-multilingual-cased-v1"
)

for subject, pdf_path, folder_name in subject_files:
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    for doc in documents:
        doc.metadata["subject"] = subject

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["subject"] = subject

    db = FAISS.from_documents(chunks, embedding_model)

    os.makedirs(folder_name, exist_ok=True)
    db.save_local(folder_name)
    print(f"{subject} Vector DB built and saved to ./{folder_name}")

print("Vector DB built and saved to ./subjects_faiss_db")