# Tests Directory

This directory contains test scripts for the Kcell RAG Bot project.

## Test Files

### Core Tests
- `test_rag_direct.py` - Direct RAG engine testing
- `test_comprehensive.py` - Comprehensive system testing with 100+ queries
- `test_e2e.py` - End-to-end testing with Telegram API

### Specialized Tests
- `test_pdf.py` - PDF processing and OCR testing
- `test_interactive.py` - Interactive testing interface

## Running Tests

```bash
# Run specific test
python3 tests/test_rag_direct.py

# Run comprehensive test suite
python3 tests/test_comprehensive.py

# Run end-to-end tests
python3 tests/test_e2e.py
```

## Test Categories

The comprehensive test suite covers:
- **Factual Services** (19 queries) - What is VATS, business telephony, etc.
- **Factual Tariffs** (11 queries) - Tariff plans, prices, etc.
- **Procedural How-To** (10 queries) - How to connect services
- **Procedural Forms** (10 queries) - Documents and forms needed
- **Contact & Support** (10 queries) - Who to call, contacts
- **Technical** (10 queries) - Technical specifications
- **Comparison** (10 queries) - Service comparisons
- **Complex Multi-step** (10 queries) - Complex scenarios

## Test Results

Test results are saved as JSON files in the main directory with timestamps.
Look for files like `test_results_20251203_121723.json`.

