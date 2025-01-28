import chromadb
import hashlib
import json
import logging
import os
import time

from datetime import datetime
from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader

from investment_chat_app.models import UserData

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("edgar_processing.log")],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up ChromaDB with persistent storage
db_path = os.path.join(settings.BASE_DIR, "chromadb_data")
os.makedirs(db_path, exist_ok=True)

# Initialize ChromaDB client and collection
try:
    chroma_client = chromadb.PersistentClient(path=db_path)
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name="edgar_documents", embedding_function=sentence_transformer_ef
    )
    logger.info("ChromaDB initialized successfully with persistent storage")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {str(e)}")
    raise


def calculate_file_hash(file_path):
    """Calculate MD5 hash of a file to detect changes"""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        buf = f.read(65536)  # Read in 64kb chunks
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()


def get_all_documents_summary():
    """Get a summary of all documents in the collection"""
    try:
        all_docs = collection.get()
        unique_files = set()
        file_details = {}

        for metadata in all_docs.get("metadatas", []):
            if metadata and "source" in metadata:
                filename = metadata["source"]
                if filename not in unique_files:
                    unique_files.add(filename)
                    file_details[filename] = {
                        "processed_date": metadata.get("processed_date", "Unknown"),
                        "total_pages": max(
                            [
                                m.get("page", 0)
                                for m in all_docs.get("metadatas", [])
                                if m and m.get("source") == filename
                            ]
                        ),
                    }

        logger.info(f"Found {len(unique_files)} unique documents in collection")
        for file in file_details:
            logger.info(f"Document: {file}, Pages: {file_details[file]['total_pages']}")

        return file_details
    except Exception as e:
        logger.error(f"Error getting documents summary: {str(e)}")
        return {}


def process_pdf_in_batches(file_path, filename):
    """Process a single PDF file and yield chunks of text"""
    try:
        with open(file_path, "rb") as file:
            pdf_reader = PdfReader(file)
            total_pages = len(pdf_reader.pages)
            logger.info(f"Processing {filename} - {total_pages} pages")

            current_chunk = ""
            chunk_size = 1000
            chunk_counter = 0

            for page_num in range(total_pages):
                try:
                    page_text = pdf_reader.pages[page_num].extract_text()
                    current_chunk += page_text + "\n"

                    while len(current_chunk) >= chunk_size:
                        break_point = current_chunk[:chunk_size].rfind(".")
                        if break_point == -1:
                            break_point = chunk_size

                        chunk_to_yield = current_chunk[: break_point + 1].strip()
                        if chunk_to_yield:
                            yield {
                                "text": chunk_to_yield,
                                "id": f"{filename}-chunk-{chunk_counter}",
                                "metadata": {
                                    "source": filename,
                                    "chunk": chunk_counter,
                                    "page": page_num + 1,
                                    "processed_date": datetime.now().isoformat(),
                                    "file_hash": calculate_file_hash(file_path),
                                },
                            }
                            chunk_counter += 1

                        current_chunk = current_chunk[break_point + 1 :]

                except Exception as e:
                    logger.error(
                        f"Error processing page {page_num + 1} of {filename}: {str(e)}"
                    )
                    continue

            if current_chunk.strip():
                yield {
                    "text": current_chunk.strip(),
                    "id": f"{filename}-chunk-{chunk_counter}",
                    "metadata": {
                        "source": filename,
                        "chunk": chunk_counter,
                        "page": total_pages,
                        "processed_date": datetime.now().isoformat(),
                        "file_hash": calculate_file_hash(file_path),
                    },
                }

    except Exception as e:
        logger.error(f"Error processing file {filename}: {str(e)}")


def get_file_metadata(filename):
    """Get metadata for a processed file"""
    try:
        results = collection.get(where={"source": filename}, limit=1)
        if results and results["metadatas"]:
            return results["metadatas"][0]
        return None
    except Exception as e:
        logger.error(f"Error getting file metadata: {str(e)}")
        return None


def get_processed_files():
    """Get list of files that have already been processed"""
    try:
        existing_docs = collection.get()
        processed_files = {}
        for metadata in existing_docs.get("metadatas", []):
            if metadata:
                processed_files[metadata["source"]] = {
                    "hash": metadata.get("file_hash"),
                    "processed_date": metadata.get("processed_date"),
                }
        return processed_files
    except Exception as e:
        logger.error(f"Error getting processed files: {str(e)}")
        return {}


def remove_file_from_collection(filename):
    """Remove all chunks of a specific file from the collection"""
    try:
        results = collection.get(where={"source": filename})
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"Removed {filename} from collection")
            return True
    except Exception as e:
        logger.error(f"Error removing file {filename}: {str(e)}")
    return False


def load_documents_to_chromadb():
    """Load documents into ChromaDB, processing only new or modified files"""
    try:
        edgar_dir = os.path.join(
            settings.BASE_DIR, "investment_chat_app", "edgar_files"
        )
        if not os.path.exists(edgar_dir):
            logger.error(f"Directory not found: {edgar_dir}")
            return False

        # Get current files in directory
        current_files = {
            f: calculate_file_hash(os.path.join(edgar_dir, f))
            for f in os.listdir(edgar_dir)
            if f.endswith(".pdf")
        }

        # Get processed files from database
        processed_files = get_processed_files()

        # Identify new and modified files
        files_to_process = []
        for filename, current_hash in current_files.items():
            if filename not in processed_files:
                logger.info(f"New file found: {filename}")
                files_to_process.append(filename)
            elif processed_files[filename]["hash"] != current_hash:
                logger.info(f"Modified file found: {filename}")
                files_to_process.append(filename)

        # Identify deleted files
        for filename in processed_files:
            if filename not in current_files:
                logger.info(f"Removing deleted file from database: {filename}")
                remove_file_from_collection(filename)

        if not files_to_process:
            logger.info("No new or modified files to process")
            return True

        logger.info(f"Processing {len(files_to_process)} files")

        # Process files
        for filename in files_to_process:
            if filename in processed_files:
                # Remove old version if file was modified
                remove_file_from_collection(filename)

            file_path = os.path.join(edgar_dir, filename)
            chunk_batch = {"ids": [], "documents": [], "metadatas": []}
            batch_size = 20

            logger.info(f"Processing {filename}")
            for chunk in process_pdf_in_batches(file_path, filename):
                chunk_batch["ids"].append(chunk["id"])
                chunk_batch["documents"].append(chunk["text"])
                chunk_batch["metadatas"].append(chunk["metadata"])

                if len(chunk_batch["ids"]) >= batch_size:
                    try:
                        collection.add(
                            ids=chunk_batch["ids"],
                            documents=chunk_batch["documents"],
                            metadatas=chunk_batch["metadatas"],
                        )
                        logger.info(
                            f"Added batch of {batch_size} chunks from {filename}"
                        )
                        chunk_batch = {"ids": [], "documents": [], "metadatas": []}
                        time.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Error adding batch to ChromaDB: {str(e)}")
                        continue

            if chunk_batch["ids"]:
                try:
                    collection.add(
                        ids=chunk_batch["ids"],
                        documents=chunk_batch["documents"],
                        metadatas=chunk_batch["metadatas"],
                    )
                    logger.info(
                        f"Added final batch of {len(chunk_batch['ids'])} chunks from {filename}"
                    )
                except Exception as e:
                    logger.error(f"Error adding final batch to ChromaDB: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"Error in load_documents_to_chromadb: {str(e)}")
        return False


def get_relevant_context(query, n_results=8):
    """Get relevant document chunks based on the query"""
    try:
        # If asking about available documents, return all document info
        if any(
            keyword in query.lower()
            for keyword in [
                "what documents",
                "which reports",
                "available files",
                "what files",
            ]
        ):
            all_docs = get_all_documents_summary()
            return "\n".join(
                [
                    f"Document: {filename}\nPages: {details['total_pages']}\nProcessed: {details['processed_date']}\n"
                    for filename, details in all_docs.items()
                ]
            )

        results = collection.query(query_texts=[query], n_results=n_results)

        contexts = []
        for i, doc in enumerate(results["documents"][0]):
            source = results["metadatas"][0][i]["source"]
            page = results["metadatas"][0][i]["page"]
            process_date = results["metadatas"][0][i].get(
                "processed_date", "Unknown date"
            )
            contexts.append(
                f"From {source} (Page {page}, Processed: {process_date}):\n{doc}\n"
            )

        return "\n".join(contexts)
    except Exception as e:
        logger.error(f"Error getting relevant context: {str(e)}")
        return ""


def generate_gpt_response(user_message, context):
    """Generate a response using GPT based on the relevant context"""
    try:
        # Get summary of all available documents
        all_docs = get_all_documents_summary()
        docs_summary = "\n".join(
            [
                f"- {filename} ({details['total_pages']} pages, processed: {details['processed_date']})"
                for filename, details in all_docs.items()
            ]
        )

        # Enhanced system prompt with document inventory
        system_prompt = f"""You are a helpful assistant analyzing EDGAR financial documents.
        You have access to the following documents:
        {docs_summary}

        Provide detailed, accurate responses based on the context provided.
        When discussing document availability, always refer to the complete list above.
        If the information isn't in the immediate context, say so but mention if it might be available in one of the listed documents."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {user_message}\n\nProvide a detailed answer based on the context above and your knowledge of available documents:",
            },
        ]

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating GPT response: {str(e)}")
        print("###", e)
        return "I'm sorry, but I encountered an error while processing your request."


def verify_document_loading():
    """Verify all documents were loaded correctly"""
    try:
        all_docs = get_all_documents_summary()
        logger.info("=== Document Loading Verification ===")
        logger.info(f"Total unique documents in collection: {len(all_docs)}")
        for filename, details in all_docs.items():
            logger.info(f"Document: {filename}")
            logger.info(f"  Pages: {details['total_pages']}")
            logger.info(f"  Processed: {details['processed_date']}")
        logger.info("=== End Verification ===")
        return len(all_docs)
    except Exception as e:
        logger.error(f"Error in verification: {str(e)}")
        return 0


def home(request):
    return render(request, "investment_chat_app/home.html")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def process_message(request):
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "")

        if not user_message:
            return Response(
                {"error": "No message provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create user data for the current user
        user_data, created = UserData.objects.get_or_create(user=request.user)

        # Update user chat sent count
        user_data.total_chats_sent += 1
        user_data.save()

        # Check for and process any new documents
        load_documents_to_chromadb()

        # Get relevant context based on the user's question
        context = get_relevant_context(user_message)

        # print(context)

        # Generate response using GPT
        gpt_response = generate_gpt_response(user_message, context)

        # Update user chat received count
        user_data.total_chats_received += 1
        user_data.save()

        return Response({"response": gpt_response}, status=status.HTTP_201_CREATED)
    except json.JSONDecodeError:
        logger.error("Invalid JSON received")
        return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error in process_message: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Initial document load and verification when server starts
logger.info("Starting initial document check and verification...")
load_documents_to_chromadb()
doc_count = verify_document_loading()
if doc_count == 0:
    logger.error("No documents found in collection! Check document loading process.")
elif doc_count < 10:  # Assuming you expect 10 documents
    logger.warning(f"Only {doc_count} documents found. Expected 10 documents.")
else:
    logger.info(f"Successfully verified {doc_count} documents in collection.")
