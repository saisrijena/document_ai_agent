import streamlit as st
import fitz  # PyMuPDF
from docx import Document
from google import genai
import pandas as pd
import io
import json

st.set_page_config(page_title="Document Scraping AI Agent", layout="wide")

st.title("📄 Document / PDF Scraping AI Agent")
st.write("Upload a PDF or DOCX file and extract the details you need.")

# Gemini API key from Streamlit Secrets
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Gemini API key is missing. Please add GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

uploaded_file = st.file_uploader(
    "Upload your PDF or DOCX file",
    type=["pdf", "docx"]
)

extraction_type = st.selectbox(
    "Select extraction type",
    [
        "Contract Details",
        "Billing Details",
        "Invoice Details",
        "Risk / Missing Information",
        "Custom Question"
    ]
)

custom_question = ""

if extraction_type == "Custom Question":
    custom_question = st.text_area(
        "What details do you want to extract?",
        placeholder="Example: Extract customer name, effective date, rate, area, billing start date, payment terms and escalation clause."
    )

def extract_pdf_text(file):
    text = ""
    file_bytes = file.read()
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")

    for page_num, page in enumerate(pdf_document, start=1):
        text += f"\n\n--- Page {page_num} ---\n"
        text += page.get_text()

    return text

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

def ask_gemini(document_text, question):
    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a document scraping AI agent.

Read the document text and extract the requested details accurately.

User request:
{question}

Document text:
{document_text}

Return the output only in this JSON format:

{{
  "summary": "Short summary of the document",
  "extracted_details": [
    {{
      "field": "Field name",
      "value": "Extracted value",
      "reference": "Page number or section if available"
    }}
  ],
  "missing_or_unclear_details": [
    "Mention anything missing, unclear or assumed"
  ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text

if st.button("Extract Details"):
    if not uploaded_file:
        st.error("Please upload a PDF or DOCX file.")
    elif extraction_type == "Custom Question" and not custom_question:
        st.error("Please enter your custom question.")
    else:
        try:
            with st.spinner("Reading document and extracting details..."):

                if uploaded_file.name.lower().endswith(".pdf"):
                    document_text = extract_pdf_text(uploaded_file)
                elif uploaded_file.name.lower().endswith(".docx"):
                    document_text = extract_docx_text(uploaded_file)
                else:
                    st.error("Unsupported file type.")
                    st.stop()

                if len(document_text.strip()) < 50:
                    st.warning("Very little text was extracted. This may be a scanned PDF and may need OCR.")

                question = get_question(extraction_type, custom_question)
                ai_result = ask_gemini(document_text, question)

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

        except Exception as e:
            st.error("Something went wrong.")
            st.write(str(e))
