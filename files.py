from pathlib import Path
from pypdf import PdfReader
from docx import Document
import pandas as pd

def extract_text(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    if ext == ".docx":
        return "\n".join(x.text for x in Document(path).paragraphs)
    if ext in {".txt", ".md", ".py", ".json", ".csv"}:
        return p.read_text(encoding="utf-8", errors="ignore")
    if ext in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        return "\n\n".join(f"[{name}]\n{df.to_string(index=False)}" for name, df in sheets.items())
    raise ValueError(f"Unsupported file type: {ext}")
