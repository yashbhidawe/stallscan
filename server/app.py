import fitz  # PyMuPDF
import re
import tempfile
import os
import numpy as np
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Geometry-First Floorplan Extractor", version="3.0.0")

# ------------------------------
# Step 1: Extract text + coordinates
# ------------------------------
def extract_text_with_coordinates(pdf_path: str, page_num: int) -> List[Dict[str, Any]]:
    """Extract text spans with coordinates using PyMuPDF."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    text_blocks = []

    dict_data = page.get_text("dict")
    for block in dict_data["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text_blocks.append({
                    "text": span["text"].strip(),
                    "x": span["bbox"][0],
                    "y": span["bbox"][1],
                    "w": span["bbox"][2] - span["bbox"][0],
                    "h": span["bbox"][3] - span["bbox"][1]
                })
    return text_blocks

# ------------------------------
# Step 2: Geometry-first grouping
# ------------------------------
def group_booths_by_text(texts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Use booth number spans as anchors and attach nearby company + size text."""
    booths = []
    blacklist = {"ENTRY", "EXIT", "TOILET", "PANEL", "STORAGE", "CAFETRIA",
                 "REGISTRATION", "HALL", "BUYER", "SELLER", "LOUNGE", "PACKMACH"}

    # Identify booth numbers (patterns like J45, A01, G73 etc.)
    booth_spans = [t for t in texts if re.fullmatch(r"[A-Za-z]\d{1,3}[A-Za-z]?", t["text"])]

    for booth_span in booth_spans:
        booth = booth_span["text"]
        bx, by = booth_span["x"], booth_span["y"]

        # collect text near the booth (tuned for ~50px vertical & ~200px horizontal)
        neighbors = [
            t for t in texts
            if (abs(t["y"] - by) < 60 and abs(t["x"] - bx) < 220)
        ]

        company_parts, size = [], None
        for t in neighbors:
            txt = t["text"].strip()
            if not txt or txt.upper() in blacklist:
                continue

            # detect size like (9), 9 sq.m, 12sqm, etc.
            size_match = re.match(r"^\(?(\d+)\)?\s*(sq\.?m|sqm|m2)?$", txt, re.IGNORECASE)
            if size_match:
                size = size_match.group(1) + " sq.m"
                continue

            # otherwise treat as company text
            if not re.fullmatch(r"[\d\.]+", txt):
                company_parts.append(txt)

        company = " ".join(company_parts).strip()
        if company:
            booths.append({
                "company_name": company,
                "size": size or "",
                "booth": booth
            })

    return booths

# ------------------------------
# FastAPI Endpoint
# ------------------------------
@app.post("/extract")
async def extract_booths(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        pdf_path = tmp.name

    try:
        texts = extract_text_with_coordinates(pdf_path, 0)  # page 0 only for now
        booths = group_booths_by_text(texts)
    finally:
        os.unlink(pdf_path)

    return JSONResponse(content={"total_booths": len(booths), "booths": booths})


@app.get("/health")
async def health():
    return {"status": "ok"}
