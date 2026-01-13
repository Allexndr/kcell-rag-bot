import difflib
import re
from typing import List, Dict, Any
import os

# Try to import extraction functions from ingest.py
# Assuming ingest.py is in the root and this file is in src/compare/
# We might need to adjust python path or just duplicate the simple extraction logic for now to be robust against import errors
try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import ingest
except ImportError:
    # Fallback if ingest.py cannot be imported (e.g. missing deps)
    print("Warning: Could not import ingest.py, defining basic extractors locally")
    import pypdf
    import docx
    
    def extract_text_from_pdf(filepath):
        text = ""
        try:
            with open(filepath, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            text = f"Error: {e}"
        return text

    def extract_text_from_docx(filepath):
        text = ""
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            text = f"Error: {e}"
        return text

class DocumentComparator:
    def __init__(self):
        pass

    def _get_text(self, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            # Use ingest.py's extractor if available, else local
            if 'ingest' in sys.modules:
                return ingest.extract_text_from_pdf(filepath)
            else:
                return extract_text_from_pdf(filepath)
        elif ext == '.docx':
            if 'ingest' in sys.modules:
                return ingest.extract_text_from_docx(filepath)
            else:
                return extract_text_from_docx(filepath)
        elif ext == '.txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        else:
            return f"Unsupported file format: {ext}"

    def compare_files(self, file_path_1: str, file_path_2: str) -> Dict[str, Any]:
        """
        Compares two files and returns structured diff data.
        """
        text1 = self._get_text(file_path_1)
        text2 = self._get_text(file_path_2)

        return self.compare_text(text1, text2)

    def compare_text(self, text1: str, text2: str) -> Dict[str, Any]:
        # Normalize newlines
        lines1 = text1.replace('\r\n', '\n').split('\n')
        lines2 = text2.replace('\r\n', '\n').split('\n')

        # Remove empty lines for cleaner diff? Or keep them?
        # Let's keep them but maybe trim whitespaces
        lines1 = [l.rstrip() for l in lines1]
        lines2 = [l.rstrip() for l in lines2]

        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        
        diff_Result = []
        added_count = 0
        deleted_count = 0
        modified_count = 0
        
        # We will iterate through opcodes to build a display-friendly structure
        # 'replace': range1, range2 -> Modified
        # 'delete': range1 -> Deleted
        # 'insert': range2 -> Added
        # 'equal': range1, range2 -> Unchanged

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            block = {
                'type': tag,
                'old_start': i1,
                'old_end': i2,
                'new_start': j1,
                'new_end': j2,
                'old_lines': lines1[i1:i2],
                'new_lines': lines2[j1:j2]
            }
            
            if tag == 'replace':
                modified_count += max(i2-i1, j2-j1) # count lines involved
            elif tag == 'delete':
                deleted_count += (i2 - i1)
            elif tag == 'insert':
                added_count += (j2 - j1)
            
            diff_Result.append(block)

        return {
            "blocks": diff_Result,
            "stats": {
                "added": added_count,
                "deleted": deleted_count,
                "modified": modified_count
            }
        }
