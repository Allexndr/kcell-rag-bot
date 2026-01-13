import chromadb
import config
from chromadb.utils import embedding_functions
import requests
import json
import os
import time
from collections import OrderedDict

try:
    from langdetect import detect
except Exception:
    detect = None  # graceful degradation if langdetect not installed

try:
    from rank_bm25 import BM25Okapi
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    BM25Okapi = None  # fallback to vector-only if dependency missing
    TfidfVectorizer = None

class RAGEngineLocal:
    """RAG Engine using local Ollama instead of Gemini API"""
    
    def __init__(self, ollama_url="http://localhost:11434", model="llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
        self.client = chromadb.PersistentClient(path=config.DB_DIR)
        
        # Use the same local embedding function as ingestion
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=config.EMBEDDING_MODEL
        )
        
        self.collection = self.client.get_collection(
            name=config.COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )
        
        # Slang / Synonym Dictionary
        self.synonyms = {
            "револьверку": "револьверный пакет",
            "револьвер": "револьверный пакет",
            "ватс": "виртуальная атс",
            "vats": "виртуальная атс",
            "ватс қызметі": "виртуальная атс",
            "виртуалды атс": "виртуальная атс",
            "симку": "sim карта",
            "симка": "sim карта",
            "esim": "есим",
            "есим": "esim",
            "тарифи": "тарифы",
            "доки": "документы",
            "подключить": "подключение",
            "отключить": "отключение",
            "қосылу": "подключение",
            "өшіру": "отключение",
            "нөмір": "номер",
            "нөмірлер": "номера",
            "қызмет": "услуга",
            "құжаттар": "документы"
        }

        # Quick answers for frequent gaps (fallback when context is missing)
        self.quick_answers = {
            "мультиномер": (
                "Мультиномер — доп. услуга к «Бизнес-телефонии» для исходящих звонков с брендового GSM-номера.\n"
                "• Требуется АТС/Бизнес-телефония.\n"
                "• Абонплата: 15 000 тг/мес за каждый GSM-номер.\n"
                "• Исходящие тарифицируются по ТП «Бизнес-телефония».\n"
                "• Входящие не предусмотрены: можно настроить переадресацию на телефоне, тарификация по ТП номера.\n"
                "• Несколько номеров: 15 000 тг за каждый."
            ),
            "sla": (
                "SLA для ВАТС, SIP-транка, Teams, бизнес-телефонии, виртуального номера и револьверных пакетов "
                "отдельно не регламентирован; действуют общие условия техподдержки Kcell."
            ),
            "лимит внутренних номеров": (
                "Прямого лимита внутренних номеров в документах нет; ограничения зависят от конфигурации и договорённости "
                "с технической службой."
            ),
            "тестовый период": (
                "Тестовый период обычно не предусмотрен (ВАТС, SIP-транк, бизнес-телефония, виртуальный номер, револьверные пакеты). "
                "Пилот/POC — по индивидуальному согласованию."
            ),
            "кто настраивает оборудование": (
                "Настройку оборудования/конфигурации выполняет техническая служба Kcell/инженеры; клиент обеспечивает свою АТС/терминалы по требованиям."
            ),
        }
        
        # Simple LRU cache for answers
        self.cache = OrderedDict()
        self.cache_size = getattr(config, "CACHE_SIZE", 200)

        # Analytics log path
        self.analytics_path = getattr(config, "ANALYTICS_LOG", "analytics/usage.log")
        os.makedirs(os.path.dirname(self.analytics_path), exist_ok=True)

        # Initialize hybrid search components
        self.tfidf_vectorizer = None
        self.document_texts = []
        self.bm25_model = None
        self._initialize_hybrid_search()
        
        print(f"✅ RAG Engine initialized with Ollama model: {model}")
    
    def _initialize_hybrid_search(self):
        """Initialize TF-IDF and BM25 models for hybrid search"""
        try:
            # Get all documents from collection
            results = self.collection.get(include=["documents", "metadatas"])
            if results and results['documents']:
                self.document_texts = results['documents']

                # Initialize TF-IDF
                if TfidfVectorizer:
                    self.tfidf_vectorizer = TfidfVectorizer(
                        max_features=5000,
                        stop_words=['и', 'в', 'на', 'с', 'по', 'для', 'не', 'что', 'как', 'из', 'за', 'от', 'до', 'без', 'при', 'после', 'во', 'со', 'об', 'про', 'через', 'над', 'под', 'перед', 'между']
                    )
                    self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.document_texts)

                # Initialize BM25
                if BM25Okapi:
                    # Tokenize documents for BM25
                    tokenized_docs = [doc.lower().split() for doc in self.document_texts]
                    self.bm25_model = BM25Okapi(tokenized_docs)

                print(f"🔍 Hybrid search initialized with {len(self.document_texts)} documents")
            else:
                print("⚠️ No documents found for hybrid search initialization")

        except Exception as e:
            print(f"⚠️ Failed to initialize hybrid search: {e}")

    def hybrid_search(self, query, top_k=20):
        """Perform hybrid search combining vector, TF-IDF, and BM25"""
        scores = {}

        # 1. Vector search (primary)
        try:
            vector_results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["metadatas", "documents", "distances"]
            )

            if vector_results and vector_results['documents']:
                for i, doc in enumerate(vector_results['documents'][0]):
                    doc_id = f"vector_{i}"
                    distance = vector_results['distances'][0][i] if vector_results['distances'] else 1.0
                    # Convert distance to similarity score
                    vector_score = max(0, 1 - distance)
                    scores[doc_id] = {
                        'doc': doc,
                        'meta': vector_results['metadatas'][0][i],
                        'vector_score': vector_score,
                        'combined_score': vector_score
                    }
        except Exception as e:
            print(f"⚠️ Vector search failed: {e}")

        # 2. TF-IDF search
        if self.tfidf_vectorizer and query:
            try:
                query_vector = self.tfidf_vectorizer.transform([query])
                tfidf_scores = cosine_similarity(query_vector, self.tfidf_matrix)[0]

                for i, score in enumerate(tfidf_scores):
                    doc_id = f"tfidf_{i}"
                    if doc_id not in scores:
                        scores[doc_id] = {
                            'doc': self.document_texts[i],
                            'meta': {},
                            'tfidf_score': score,
                            'combined_score': score * 0.3  # Weight TF-IDF lower
                        }
                    else:
                        scores[doc_id]['tfidf_score'] = score
                        scores[doc_id]['combined_score'] += score * 0.3
            except Exception as e:
                print(f"⚠️ TF-IDF search failed: {e}")

        # 3. BM25 search
        if self.bm25_model and query:
            try:
                tokenized_query = query.lower().split()
                bm25_scores = self.bm25_model.get_scores(tokenized_query)

                for i, score in enumerate(bm25_scores):
                    doc_id = f"bm25_{i}"
                    normalized_score = score / max(bm25_scores) if max(bm25_scores) > 0 else 0

                    if doc_id not in scores:
                        scores[doc_id] = {
                            'doc': self.document_texts[i],
                            'meta': {},
                            'bm25_score': normalized_score,
                            'combined_score': normalized_score * 0.2  # Weight BM25 lower
                        }
                    else:
                        scores[doc_id]['bm25_score'] = normalized_score
                        scores[doc_id]['combined_score'] += normalized_score * 0.2
            except Exception as e:
                print(f"⚠️ BM25 search failed: {e}")

        # Sort by combined score and return top results
        sorted_results = sorted(scores.items(), key=lambda x: x[1]['combined_score'], reverse=True)
        return [item[1] for item in sorted_results[:top_k]]
    
    def expand_query_rule_based(self, query):
        """Simple rule-based expansion for common slang"""
        expanded = query.lower()
        for slang, formal in self.synonyms.items():
            if slang in expanded:
                expanded = expanded.replace(slang, formal)
        return expanded

    def detect_language(self, text):
        """Detect language code; default to 'ru'."""
        if not detect:
            return "ru"
        try:
            return detect(text)
        except Exception:
            return "ru"

    def _from_cache(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def _to_cache(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)

    def _log_usage(self, *, query, search_query, lang, response, cached, n_results):
        try:
            entry = {
                "ts": time.time(),
                "query": query,
                "search_query": search_query,
                "lang": lang,
                "response_len": len(response) if response else 0,
                "cached": cached,
                "n_results": n_results,
            }
            with open(self.analytics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # do not break main flow on logging issues

    def _bm25_rerank(self, query, results):
        """Optional BM25 rerank of vector results for better lexical relevance."""
        if not BM25Okapi:
            return results

        docs = results.get("documents", [[]])
        metas = results.get("metadatas", [[]])
        ids = results.get("ids", [[]])
        if not docs or not docs[0]:
            return results

        corpus = [doc for doc in docs[0]]
        tokenized_corpus = [c.lower().split() for c in corpus]
        try:
            bm25 = BM25Okapi(tokenized_corpus)
            scores = bm25.get_scores(query.lower().split())
        except Exception:
            return results

        # Sort indices by score descending
        sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        docs_sorted = [docs[0][i] for i in sorted_idx]
        metas_sorted = [metas[0][i] for i in sorted_idx]
        ids_sorted = [ids[0][i] for i in sorted_idx]

        return {
            "documents": [docs_sorted],
            "metadatas": [metas_sorted],
            "ids": [ids_sorted],
        }

    def generate_text(self, prompt):
        """Generate text using Ollama API"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1, # Lower temperature for more factual answers
                        "num_ctx": 4096,    # Larger context window
                        "num_predict": 1000
                    }
                },
                timeout=120 # Increased timeout for larger model
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return f"Error: Ollama returned status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "❌ Error: Ollama не запущен. Установите и запустите: brew install ollama && ollama serve"
        except Exception as e:
            return f"Error: {e}"
    
    def answer_question(self, user_query):
        lang = self.detect_language(user_query)

        # 1. Expand Query (Rule-based)
        search_query = self.expand_query_rule_based(user_query)
        print(f"🔍 Original: '{user_query}' -> Search: '{search_query}'")

        # Store original query for citation extraction
        original_query = user_query

        # 0. Quick answers fallback (simple contains check)
        sq_lower = search_query.lower()
        for key, val in self.quick_answers.items():
            if key in sq_lower:
                self._log_usage(
                    query=user_query,
                    search_query=search_query,
                    lang=lang,
                    response=val,
                    cached=False,
                    n_results=0,
                )
                return {
                    "answer": val,
                    "sources": [{"source": "База знаний Kcell (быстрый ответ)", "contribution": 95}],
                    "confidence": 95,
                    "reasoning": 5
                }

        cache_key = search_query.strip().lower()
        cached = self._from_cache(cache_key)
        if cached:
            self._log_usage(
                query=user_query,
                search_query=search_query,
                lang=lang,
                response=cached,
                cached=True,
                n_results=0,
            )
            return {
                "answer": cached,
                "sources": [{"source": "Кэш ответов", "contribution": 90}],
                "confidence": 90,
                "reasoning": 10
            }

        # 2. Retrieve Documents using hybrid search
        hybrid_results = self.hybrid_search(search_query, top_k=50)

        # Convert to format compatible with existing code
        if hybrid_results:
            results = {
                'documents': [[doc['doc'] for doc in hybrid_results]],
                'metadatas': [[doc['meta'] for doc in hybrid_results]],
                'distances': [[1 - doc.get('combined_score', 0) for doc in hybrid_results]]
            }
        else:
            # Fallback to regular vector search
            results = self.collection.query(
            query_texts=[search_query],
            n_results=50,
            include=["metadatas", "documents", "distances"]
            )

        # 2.1 Optional BM25 rerank for better lexical precision (if not using hybrid)
        if not hybrid_results:
            results = self._bm25_rerank(search_query, results)

        # Collect sources with contribution percentages
        sources_with_contribution = []
        total_confidence = 0
        reasoning = 0

        if results['documents'] and results['documents'][0]:
            # Calculate contribution based on relevance scores (inverse of distance)
            docs_with_scores = []
            distances = results.get('distances', [[]])
            if not distances:
                distances = [[]]

            for i, doc in enumerate(results['documents'][0][:20]):  # Top 20 results
                meta = results['metadatas'][0][i]
                distance = distances[0][i] if i < len(distances[0]) else 1.0
                source = meta.get('source', 'Unknown')

                # Use position-based relevance since distances seem to be uniform
                # Higher relevance for top results
                position_weight = max(0.1, 1.0 - (i * 0.05))  # Decreasing weight by position
                distance_weight = max(0, 1 - distance) if distance < 1 else 0.5  # Fallback distance weight

                relevance_score = position_weight * 0.7 + distance_weight * 0.3

                docs_with_scores.append({
                    'source': source,
                    'relevance': relevance_score,
                    'rank': i + 1
                })

            # Group by source and collect citations
            source_contributions = {}
            source_citations = {}

            for i, doc in enumerate(results['documents'][0][:20]):
                meta = results['metadatas'][0][i]
                source = meta.get('source', 'Unknown')

                # Find corresponding score
                doc_score = None
                for ds in docs_with_scores:
                    if ds['rank'] == i + 1:
                        doc_score = ds['relevance']
                        break

                if doc_score:
                    if source not in source_contributions:
                        source_contributions[source] = 0
                        source_citations[source] = []

                    source_contributions[source] += doc_score

                    # Extract relevant citation - use original user query for better relevance
                    clean_doc = doc.replace('\n', ' ').strip()

                    # Remove technical metadata markers and file extensions
                    clean_doc = clean_doc.replace('[[SOURCE:', '').replace(']]', '')
                    clean_doc = clean_doc.replace('.pdf', '').replace('.docx', '').replace('.xlsx', '').replace('.txt', '')
                    clean_doc = clean_doc.replace('pdf', '').replace('docx', '').replace('xlsx', '').replace('txt', '')

                    # Remove table artifacts and non-meaningful content
                    clean_doc = clean_doc.replace('|', '').replace('nan', '').replace('*', '')
                    # Remove excessive whitespace
                    import re as regex
                    clean_doc = regex.sub(r'\s+', ' ', clean_doc)

                    # Find the most relevant sentence containing keywords from ORIGINAL user query
                    sentences = [s.strip() for s in clean_doc.split('.') if s.strip() and len(s.strip()) > 15]
                    best_sentence = ""
                    max_relevance = 0

                    # Use original query words for better relevance
                    original_words = set(original_query.lower().split())
                    # Add some expanded terms that might be relevant
                    relevant_terms = original_words.copy()
                    if 'sip' in original_words or 'номер' in original_words:
                        relevant_terms.update(['телефон', 'номер', 'sip', 'звонок', 'вызов'])
                    if 'компани' in original_words or 'наименовани' in original_words:
                        relevant_terms.update(['компания', 'название', 'фирма', 'организация'])

                    for sentence in sentences:
                        sentence_lower = sentence.lower()
                        relevance = sum(1 for word in relevant_terms if word in sentence_lower)
                        # Bonus for sentences that contain multiple keywords
                        if relevance >= 2:
                            relevance *= 1.5

                        if relevance > max_relevance and len(sentence) > 20 and len(sentence) < 150:
                            max_relevance = relevance
                            best_sentence = sentence.strip()

                    # If no highly relevant sentence found, skip this citation
                    if best_sentence and len(best_sentence) > 20 and max_relevance >= 1:
                        # Clean up the citation
                        citation = best_sentence.strip()
                        # Remove extra dots and normalize
                        citation = citation.rstrip('.')
                        # Skip if citation looks like table data or garbage
                        if not any(char.isdigit() for char in citation[:10]):  # Skip table-like content
                            citation = f'"{citation}."'
                            if citation not in source_citations[source] and len(source_citations[source]) < 2:  # Max 2 per source
                                source_citations[source].append(citation)

            # Sort sources by contribution and calculate percentages
            sorted_sources = sorted(source_contributions.items(), key=lambda x: x[1], reverse=True)
            total_relevance = sum(contrib for _, contrib in sorted_sources)

            if total_relevance > 0:
                for source, contribution in sorted_sources[:10]:  # Show top 10 sources
                    percentage = max(1, int((contribution / total_relevance) * 100))  # At least 1%
                    citations = source_citations.get(source, [])[:2]  # Max 2 citations per source

                    sources_with_contribution.append({
                        'source': source,
                        'contribution': percentage,
                        'citations': citations
                    })
                    total_confidence += percentage

            # Adjust confidence and reasoning
            if total_confidence > 100:
                total_confidence = 100
            reasoning = max(0, 100 - total_confidence)

            context_parts = []
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                source = meta.get('source', 'Unknown')
                # Clean up newlines in doc for better context
                clean_doc = doc.replace('\n', ' ').strip()
                context_parts.append(f"SOURCE: {source}\nCONTENT: {clean_doc}")
            
            context_str = "\n\n".join(context_parts)
        else:
            context_str = "NO DOCUMENTS FOUND."
            sources_with_contribution = [{"source": "Документы не найдены", "contribution": 0}]
            total_confidence = 20
            reasoning = 80
        
        # 3. Construct Prompt (Simplified for reliability)
        if lang.startswith("kk"):
            answer_language = "Kazakh"
        else:
            answer_language = "Russian"

        prompt = f"""You are a helpful AI assistant for Kcell. 
Answer the user's question using ONLY the context below.
If the answer is not in the context, say "К сожалению, информации нет в документах."
If the user asks for anything outside the provided context, politely refuse.
Never invent facts; be concise and factual.
Respond in {answer_language}.

CONTEXT:
{context_str}

USER QUESTION: 
{user_query}

ANSWER (in {answer_language}):"""
        
        # 4. Generate Answer
        response = self.generate_text(prompt)

        # Adjust confidence based on response content
        if "К сожалению" in response or "информации нет" in response:
            confidence = max(20, confidence - 30)
            reasoning = min(80, reasoning + 30)

        # Cache and log usage
        self._to_cache(cache_key, response)
        self._log_usage(
            query=user_query,
            search_query=search_query,
            lang=lang,
            response=response,
            cached=False,
            n_results=len(results.get("documents", [[]])[0]) if results else 0,
        )

        return {
            "answer": response,
            "sources": sources_with_contribution,
            "confidence": total_confidence,
            "reasoning": reasoning
        }
    
    def query(self, user_query):
        """Alias for compatibility"""
        return self.answer_question(user_query)

if __name__ == "__main__":
    # Test
    print("Testing local RAG with Ollama...")
    rag = RAGEngineLocal()
    
    test_queries = [
        "Как подключить револьверку",
        "Что такое ВАТС"
    ]
    
    for q in test_queries:
        print(f"\nQuery: {q}")
        print("Response:")
        print(rag.answer_question(q))
