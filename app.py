import streamlit as st
import fitz  # PyMuPDF
from docx import Document
from google import genai
from PIL import Image
import pandas as pd
import io
import json

st.set_page_config(page_title="Document Visual AI Agent", layout="wide")

st.title("📄 Document / PDF / Visual Scraping AI Agent")
st.write("Upload PDF, DOCX, JPG, or PNG and extract text, tables, contract details, billing details, or visual information.")

# Gemini API key from Streamlit Secrets
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Gemini API key is missing. Please add GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

uploaded_file = st.file_uploader(
    "Upload your file",
    type=["pdf", "docx", "jpg", "jpeg", "png"]
)

extraction_type = st.selectbox(
    "Select extraction type",
    [
        "Contract Details",
        "Billing Details",
        "Invoice Details",
        "Visual / Scanned Document Details",
        "Risk / Missing Information",
        "Custom Question"
    ]
)

custom_question = ""

if extraction_type == "Custom Question":
    custom_question = st.text_area(
        "What details do you want to extract?",
        placeholder="Example: Extract customer name, effective date, total area, rate, payment terms and escalation clause."
    )

analyze_visual = st.checkbox(
    "Analyze visual/scanned content also",
    value=True
)

max_pages = st.slider(
    "Maximum PDF pages to visually analyze",
    min_value=1,
    max_value=10,
    value=5
)

def extract_pdf_text(file_bytes):
    text = ""
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")

    for page_num, page in enumerate(pdf_document, start=1):
        text += f"\n\n--- Page {page_num} ---\n"
        text += page.get_text()

    return text

def convert_pdf_pages_to_images(file_bytes, max_pages=5):
    images = []
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")

    total_pages = min(len(pdf_document), max_pages)

    for page_index in range(total_pages):
        page = pdf_document[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        images.append(image)

    return images

def extract_docx_text(file):
    text = ""
    doc = Document(file)

    for para in doc.paragraphs:
        if para.text.strip():
            text += para.text + "\n"

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            text += " | ".join(cells) + "\n"

    return text

def get_question(extraction_type, custom_question):
    if extraction_type == "Contract Details":
        return """
Extract the following contract details:
1. Customer / Project name
2. Effective date
3. Contract term
4. Handover date
5. Commercial operation date
6. Total area
7. Rate
8. Escalation clause
9. Payment terms
10. Important obligations
"""

    elif extraction_type == "Billing Details":
        return """
Extract the following billing details:
1. Billing start date
2. Billing frequency
3. Billing rate
4. Currency
5. Quantity / area / volume
6. Payment terms
7. Tax or additional charges
8. Escalation rule
9. Billing conditions
"""

    elif extraction_type == "Invoice Details":
        return """
Extract the following invoice details:
1. Invoice number
2. Invoice date
3. Customer name
4. Amount
5. Currency
6. PO number
7. Job / shipment reference
8. Tax amount
9. Total invoice value
10. Any discrepancy
"""

    elif extraction_type == "Visual / Scanned Document Details":
        return """
Read the visual/scanned document carefully and extract:
1. All visible important text
2. Tables and values
3. Dates
4. Amounts
5. Customer / company names
6. Contract or invoice references
7. Signatures, stamps, handwritten notes if visible
8. Any unclear or unreadable parts
"""

    elif extraction_type == "Risk / Missing Information":
        return """
Review the document and identify:
1. Missing information
2. Unclear dates
3. Unclear commercial terms
4. Assumptions
5. Risk points
6. Clauses requiring manual review
"""

    else:
        return custom_question

def build_prompt(document_text, question):
    return f"""
You are a document scraping AI agent.

Read the uploaded document carefully. The document may contain text, scanned pages, images, visual tables, stamps, signatures, or screenshots.

User request:
{question}

Extracted text from document:
{document_text}

Return the output only in this JSON format:

{{
  "summary": "Short summary of the document",
  "extracted_details": [
    {{
      "field": "Field name",
      "value": "Extracted value",
      "reference": "Page number, section, or visual reference if available"
    }}
  ],
  "missing_or_unclear_details": [
    "Mention anything missing, unclear, unreadable, or assumed"
  ]
}}
"""

def ask_gemini_text(document_text, question):
    prompt = build_prompt(document_text, question)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text

def ask_gemini_visual(document_text, question, images):
    prompt = build_prompt(document_text, question)

    contents = [prompt]

    for image in images:
        contents.append(image)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents
    )

    return response.text

def show_result(ai_result):
    st.subheader("AI Extracted Result")
    st.write(ai_result)

    try:
        cleaned = ai_result.replace("```json", "").replace("```", "").strip()
        result_json = json.loads(cleaned)

        st.subheader("Summary")
        st.write(result_json.get("summary", ""))

        details = result_json.get("extracted_details", [])
        df = pd.DataFrame(details)

        if not df.empty:
            st.subheader("Extracted Details Table")
            st.dataframe(df)

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)

            st.download_button(
                label="Download Excel",
                data=excel_buffer.getvalue(),
                file_name="extracted_document_details.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        missing = result_json.get("missing_or_unclear_details", [])

        if missing:
            st.subheader("Missing / Unclear Details")
            for item in missing:
                st.warning(item)

    except Exception:
        st.info("AI result is shown above. Excel conversion was skipped because the AI response was not valid JSON.")

if st.button("Extract Details"):
    if not uploaded_file:
        st.error("Please upload a file.")
    elif extraction_type == "Custom Question" and not custom_question:
        st.error("Please enter your custom question.")
    else:
        try:
            question = get_question(extraction_type, custom_question)
            file_name = uploaded_file.name.lower()
            file_bytes = uploaded_file.getvalue()

            document_text = ""
            images = []

            with st.spinner("Reading file and extracting details..."):

                if file_name.endswith(".pdf"):
                    document_text = extract_pdf_text(file_bytes)

                    if analyze_visual:
                        images = convert_pdf_pages_to_images(file_bytes, max_pages=max_pages)

                    if len(document_text.strip()) < 50:
                        st.warning("Very little text was extracted. This may be a scanned PDF, so visual analysis will be used.")

                    if analyze_visual and images:
                        ai_result = ask_gemini_visual(document_text, question, images)
                    else:
                        ai_result = ask_gemini_text(document_text, question)

                elif file_name.endswith(".docx"):
                    document_text = extract_docx_text(uploaded_file)
                    ai_result = ask_gemini_text(document_text, question)

                elif file_name.endswith(".jpg") or file_name.endswith(".jpeg") or file_name.endswith(".png"):
                    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                    st.image(image, caption="Uploaded Image", use_container_width=True)

                    images = [image]
                    document_text = "The uploaded file is an image. Please read all visible text and visual information from the image."

                    ai_result = ask_gemini_visual(document_text, question, images)

                else:
                    st.error("Unsupported file type.")
                    st.stop()

            show_result(ai_result)

        except Exception as e:
            st.error("Something went wrong.")
            st.write(str(e))
