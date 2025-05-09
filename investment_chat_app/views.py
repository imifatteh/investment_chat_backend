import chromadb
import hashlib
import json
import logging
import os
import time
import re

from datetime import datetime
from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader

from investment_chat_app.models import UserData, SECFilings
from django.core.cache import cache

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

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

# Initialize sentence transformer model
sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")


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

        if (
            gpt_response.find(
                "I'm sorry, but I encountered an error while processing your request."
            )
            != -1
        ):
            return Response(
                {
                    "error": "I'm sorry but I encountered an error while processing your request."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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


class SECFilingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            ticker = request.query_params.get("ticker", None)
            year = request.query_params.get("year", None)

            # Query the database for SECFilings based on filters
            queryset = SECFilings.objects.all()
            if ticker:
                queryset = queryset.filter(ticker__iexact=ticker)
            if year:
                queryset = queryset.filter(filing_date__year=year)

            filings = []
            for filing in queryset.values(
                "ticker", "form_type", "filing_date", "path_to_doc"
            ):
                filing_data = {
                    "ticker": filing["ticker"],
                    "form_type": filing["form_type"],
                    "filing_date": filing["filing_date"],
                    "path_to_doc": filing["path_to_doc"],
                }

                # Generate or retrieve summary for each filing
                cache_key = f"summary_{filing['ticker']}_{filing['filing_date']}"
                cached_summary = cache.get(cache_key)

                if cached_summary:
                    filing_data["summary"] = cached_summary
                else:
                    # Generate summary if not cached
                    summary = self.generate_quick_summary(filing)
                    filing_data["summary"] = summary
                    # Cache the summary for future requests
                    cache.set(
                        cache_key, summary, timeout=60 * 60 * 24 * 7
                    )  # Cache for 7 days

                filings.append(filing_data)

            return Response({"filings": filings}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching SECFilings: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def extract_relevant_sentences(self, text, query_embeddings, threshold=0.7):
        """Extract sentences that are most relevant to the query using sentence transformers"""
        # Split text into sentences
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]

        # Get embeddings for all sentences
        sentence_embeddings = sentence_transformer.encode(sentences)

        # Calculate similarity scores
        similarities = cosine_similarity(query_embeddings, sentence_embeddings)

        # Get top relevant sentences
        relevant_indices = np.where(similarities[0] > threshold)[0]
        relevant_sentences = [sentences[i] for i in relevant_indices]

        return relevant_sentences

    def extract_pdf_text(self, file_path):
        """Extract and clean text from PDF with improved error handling"""
        try:
            reader = PdfReader(file_path)
            text = ""

            # First pass: Extract text from all pages with error handling
            for i in range(len(reader.pages)):
                try:
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        # Clean page text before adding
                        page_text = self.clean_text(page_text)
                        text += page_text + "\n\n"
                except Exception as e:
                    logger.warning(f"Error extracting text from page {i + 1}: {str(e)}")
                    continue

            if not text.strip():
                return None

            # Remove common PDF artifacts
            text = re.sub(
                r"(?i)(page|table of contents|sec filing|form \d+-\w+).*?\n", "", text
            )
            text = re.sub(r"\s{2,}", " ", text)
            text = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", text)
            text = re.sub(r"\.{2,}", ".", text)

            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return None

    def extract_section_alternative(self, text, section_name):
        """Alternative method to extract sections when standard method fails"""
        try:
            patterns = {
                "financial_highlights": [
                    r"(?i)(revenue|net income|earnings per share|eps).*?\$?\d+",
                    r"(?i)(total revenue|net income|diluted earnings per share).*?\$?\d+",
                    r"(?i)(consolidated statements of operations).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "business_overview": [
                    r"(?i)(business overview|company overview|executive summary).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(our business|company description).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(management's discussion and analysis).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "risk_factors": [
                    r"(?i)(risk factors|principal risks).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(risks and uncertainties).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 1a\. risk factors).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "financial_condition": [
                    r"(?i)(financial condition|results of operations).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(liquidity and capital resources).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 7\. management's discussion and analysis).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "legal_proceedings": [
                    r"(?i)(legal proceedings|legal matters).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 3\. legal proceedings).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "market_risk": [
                    r"(?i)(market risk|financial instruments).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 7a\. quantitative and qualitative disclosures about market risk).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "controls": [
                    r"(?i)(controls and procedures|internal control).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 9a\. controls and procedures).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "executive_compensation": [
                    r"(?i)(executive compensation|compensation discussion and analysis).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 11\. executive compensation).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "security_ownership": [
                    r"(?i)(security ownership|beneficial ownership).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 12\. security ownership).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
                "related_party_transactions": [
                    r"(?i)(related party transactions|transactions with related persons).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                    r"(?i)(item 13\. related party transactions).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                ],
            }

            if section_name in patterns:
                for pattern in patterns[section_name]:
                    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                    if match:
                        return match.group(0).strip()

            return None
        except Exception as e:
            logger.error(f"Error in alternative section extraction: {str(e)}")
            return None

    def generate_quick_summary(self, filing):
        """Generate a quick summary using sentence transformers and GPT"""
        try:
            file_path = filing["path_to_doc"]
            if not os.path.exists(file_path):
                return f"Cannot generate summary: File does not exist at {file_path}"

            # Extract and clean text from PDF
            text = self.extract_pdf_text(file_path)
            if not text:
                return "Summary generation failed: Could not extract text from the document"

            # For 10-K filings, try to extract information even if sections are not properly formatted
            if filing["form_type"] == "10-K":
                # Try to find financial data using direct patterns
                financial_data = self.extract_financial_data(text)
                if financial_data:
                    text = financial_data + "\n\n" + text

            # Extract key sections using section headers
            sections = {
                "financial_highlights": self.extract_section(
                    text,
                    r"(?i)(financial highlights|selected financial data|consolidated statements of operations|item 6\. selected financial data|item 8\. financial statements)",
                ),
                "business_overview": self.extract_section(
                    text,
                    r"(?i)(business overview|management's discussion|executive summary|item 1\. business|item 7\. management's discussion and analysis)",
                ),
                "risk_factors": self.extract_section(
                    text,
                    r"(?i)(risk factors|risk and uncertainties|item 1a\. risk factors)",
                ),
                "financial_condition": self.extract_section(
                    text,
                    r"(?i)(financial condition|results of operations|liquidity and capital resources|item 7\. management's discussion and analysis)",
                ),
                "legal_proceedings": self.extract_section(
                    text, r"(?i)(legal proceedings|item 3\. legal proceedings)"
                ),
                "market_risk": self.extract_section(
                    text,
                    r"(?i)(market risk|item 7a\. quantitative and qualitative disclosures about market risk)",
                ),
                "controls": self.extract_section(
                    text,
                    r"(?i)(controls and procedures|item 9a\. controls and procedures)",
                ),
                "executive_compensation": self.extract_section(
                    text,
                    r"(?i)(executive compensation|item 11\. executive compensation)",
                ),
                "security_ownership": self.extract_section(
                    text, r"(?i)(security ownership|item 12\. security ownership)"
                ),
                "related_party_transactions": self.extract_section(
                    text,
                    r"(?i)(related party transactions|item 13\. related party transactions)",
                ),
            }

            # For 10-K filings, ensure we have all required sections
            if filing["form_type"] == "10-K":
                missing_sections = [k for k, v in sections.items() if not v]
                if missing_sections:
                    logger.warning(f"Missing sections in 10-K: {missing_sections}")
                    # Try alternative extraction for missing sections
                    for section in missing_sections:
                        if not sections[section]:
                            sections[section] = self.extract_section_alternative(
                                text, section
                            )

            # Combine sections with priority
            key_info = ""
            for section_name, section_text in sections.items():
                if section_text:
                    key_info += f"=== {section_name.replace('_', ' ').title()} ===\n{section_text}\n\n"

            # If no sections found, try to extract any relevant information
            if not key_info.strip():
                key_info = self.extract_any_relevant_info(text)

            # Generate GPT prompt
            prompt = (
                f"This is a {filing['form_type']} SEC filing for {filing['ticker']} dated {filing['filing_date']}.\n\n"
                f"Please provide a comprehensive summary covering:\n"
                f"1. Key financial figures and performance metrics (revenue, net income, EPS, etc.)\n"
                f"2. Business highlights and notable developments\n"
                f"3. Significant risks and legal issues\n"
                f"4. Major changes compared to previous periods\n\n"
                f"Focus on specific numbers, facts, and important changes. Be analytical and concise.\n\n"
                f"--- Filing Content Start ---\n\n{key_info}\n\n--- Filing Content End ---"
            )

            print("#########################")
            print(prompt)
            print("#########################")

            # Generate summary with OpenAI
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-16k",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,  # Lower temperature for more factual responses
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"

    def extract_financial_data(self, text):
        """Extract financial data using direct patterns"""
        try:
            financial_data = []

            # Revenue patterns
            revenue_patterns = [
                r"(?i)(total revenue|revenue|net revenue).*?\$?\s*[\d,]+\.?\d*\s*(million|billion|thousand)?",
                r"(?i)(revenue|net revenue).*?(increased|decreased|grew|rose|declined|fell).*?\$?\s*[\d,]+\.?\d*\s*(million|billion|thousand)?",
            ]

            # Net income patterns
            income_patterns = [
                r"(?i)(net income|net loss|net earnings).*?\$?\s*[\d,]+\.?\d*\s*(million|billion|thousand)?",
                r"(?i)(net income|net loss|net earnings).*?(increased|decreased|grew|rose|declined|fell).*?\$?\s*[\d,]+\.?\d*\s*(million|billion|thousand)?",
            ]

            # EPS patterns
            eps_patterns = [
                r"(?i)(earnings per share|eps|diluted eps).*?\$?\s*[\d,]+\.?\d*",
                r"(?i)(earnings per share|eps|diluted eps).*?(increased|decreased|grew|rose|declined|fell).*?\$?\s*[\d,]+\.?\d*",
            ]

            # Extract data using patterns
            for pattern in revenue_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        financial_data.append(" ".join(match))
                    else:
                        financial_data.append(match)

            for pattern in income_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        financial_data.append(" ".join(match))
                    else:
                        financial_data.append(match)

            for pattern in eps_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        financial_data.append(" ".join(match))
                    else:
                        financial_data.append(match)

            if financial_data:
                return "=== Financial Data ===\n" + "\n".join(financial_data)
            return None
        except Exception as e:
            logger.error(f"Error extracting financial data: {str(e)}")
            return None

    def extract_any_relevant_info(self, text):
        """Extract any relevant information when no sections are found"""
        try:
            relevant_info = []

            # Look for any financial data
            financial_data = self.extract_financial_data(text)
            if financial_data:
                relevant_info.append(financial_data)

            # Look for business highlights
            business_patterns = [
                r"(?i)(business highlights|key developments|strategic initiatives).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                r"(?i)(acquisition|merger|partnership|agreement).*?\$?\s*[\d,]+\.?\d*\s*(million|billion|thousand)?",
            ]

            for pattern in business_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        relevant_info.append(" ".join(match))
                    else:
                        relevant_info.append(match)

            # Look for risk factors
            risk_patterns = [
                r"(?i)(risk factors|principal risks).*?\n(.*?)(?=\n[A-Z]|\n\n)",
                r"(?i)(risks and uncertainties).*?\n(.*?)(?=\n[A-Z]|\n\n)",
            ]

            for pattern in risk_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        relevant_info.append(" ".join(match))
                    else:
                        relevant_info.append(match)

            if relevant_info:
                return "\n\n".join(relevant_info)
            return text[:5000]  # Return first 5000 chars if no relevant info found
        except Exception as e:
            logger.error(f"Error extracting relevant info: {str(e)}")
            return text[:5000]

    def extract_section(self, text, pattern):
        """Extract a section of text based on a header pattern"""
        try:
            # First try to find the section header
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if not match:
                return None

            # Find the start of the section
            start_pos = match.start()

            # Look for the next major section header
            next_section_patterns = [
                r"(?i)(financial highlights|selected financial data|consolidated statements of operations)",
                r"(?i)(business overview|management's discussion|executive summary)",
                r"(?i)(risk factors|risk and uncertainties)",
                r"(?i)(financial condition|results of operations|liquidity and capital resources)",
                r"(?i)(legal proceedings)",
                r"(?i)(market risk)",
                r"(?i)(controls and procedures)",
                r"(?i)(executive compensation)",
                r"(?i)(security ownership)",
                r"(?i)(related party transactions)",
            ]

            # Find the next section header
            next_section_pos = len(text)
            for pattern in next_section_patterns:
                next_match = re.search(pattern, text[start_pos + 1 :], re.IGNORECASE)
                if next_match and next_match.start() < next_section_pos:
                    next_section_pos = next_match.start()

            # Extract the section text
            if next_section_pos < len(text):
                section_text = text[start_pos : start_pos + next_section_pos].strip()
            else:
                section_text = text[start_pos:].strip()

            # Clean up the section text
            section_text = self.clean_text(section_text)

            return section_text
        except Exception as e:
            logger.error(f"Error extracting section: {str(e)}")
            return None

    def clean_text(self, raw):
        """Clean and normalize text"""
        try:
            # Remove headers and footers
            cleaned = re.sub(
                r"(?i)(page|table of contents|sec filing|form \d+-\w+).*?\n", "", raw
            )

            # Remove multiple spaces and newlines
            cleaned = re.sub(r"\s{2,}", " ", cleaned)

            # Remove control characters
            cleaned = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", cleaned)

            # Remove repeated dots
            cleaned = re.sub(r"\.{2,}", ".", cleaned)

            # Remove URLs and email addresses
            cleaned = re.sub(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                "",
                cleaned,
            )
            cleaned = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", cleaned)

            # Remove page numbers and form numbers
            cleaned = re.sub(r"(?i)page \d+", "", cleaned)
            cleaned = re.sub(r"(?i)form \d+-\w+", "", cleaned)

            # Remove repeated headers
            cleaned = re.sub(r"(?i)(table of contents|index).*?\n", "", cleaned)

            return cleaned.strip()
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            return raw
