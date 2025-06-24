import json
import io
import streamlit as st
import openai
import pdfplumber
from fpdf import FPDF

openai.api_key = st.secrets["OPENAI_API_KEY"]
st.write("🔑 Key prefix:", st.secrets["OPENAI_API_KEY"][:4])
st.write("🔢 Key length:",  len(st.secrets["OPENAI_API_KEY"]))

st.set_page_config(page_title="AML Source-of-Funds Assistant")
st.title("AML Source-of-Funds Assistant")
st.write("Upload bank statements and enter purchase details to analyze source of funds.")

uploaded_files = st.file_uploader("Upload Bank Statement PDFs", type="pdf", accept_multiple_files=True)
purchase_price       = st.number_input("Purchase Price",       min_value=0.0, step=1000.0)
mortgage_advance     = st.number_input("Mortgage Advance",     min_value=0.0, step=1000.0)
personal_contribution= st.number_input("Personal Contribution",min_value=0.0, step=1000.0)
user_role            = st.selectbox("User Role", ["Client", "Solicitor", "Estate Agent"])

def json_to_markdown(data: dict) -> str:
    md = "### Transactions\n"
    md += "|Date|Description|Amount|Direction|Category|Follow Up|\n"
    md += "|-----|-----------|------|---------|--------|---------|\n"
    for t in data.get("transactions", []):
        md += f"|{t['date']}|{t['description']}|{t['amount']}|{t['direction']}|{t['category']}|{t['follow_up']}|\n"
    md += "\n### Funding Reconciliation\n"
    rec = data.get("reconciliation", {})
    md += f"- Total Verified: {rec.get('total_verified',0)}\n"
    md += f"- Declared Contribution: {rec.get('declared_contribution',0)}\n"
    md += f"- Mortgage Advance: {rec.get('mortgage_advance',0)}\n"
    md += f"- Shortfall: {rec.get('shortfall',0)}\n"
    md += "\n### Red Flags\n"
    for rf in data.get("red_flags", []):
        md += f"- {rf}\n"
    md += f"\n### Summary\n{data.get('summary','')}\n"
    return md

if st.button("Analyze"):
    if not uploaded_files:
        st.warning("Please upload at least one PDF.")
    else:
        # 1) extract text
        all_text = ""
        for f in uploaded_files:
            with pdfplumber.open(f) as pdf:
                for p in pdf.pages:
                    all_text += p.extract_text() + "\n"

        # 2) build prompt
        prompt = f"""
You are AML Source-of-Funds Brain v1.1. Classify transactions, detect salary, trace transfers, flag AML red-flags, and reconcile declared vs. verified funds for purchase price {purchase_price}, mortgage {mortgage_advance}, contribution {personal_contribution}. Return JSON using the schema on README.

Bank Statement Text:
{all_text}
"""

        # 3) call OpenAI
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You are an expert AML assistant for conveyancing."},
                {"role":"user","content":prompt}
            ],
        )

        # 4) parse JSON
        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            st.error("Failed to parse AI response as JSON.")
            st.text(response.choices[0].message.content)
            st.stop()

        # 5) render results
        md = json_to_markdown(result)
        st.markdown(md, unsafe_allow_html=True)

        # 6) download PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)
        pdf.set_font("Arial", size=12)
        for line in md.splitlines():
            pdf.multi_cell(0, 10, line)
        data = pdf.output(dest="S").encode("latin-1")
        st.download_button("Download as PDF", data=data, file_name="analysis.pdf", mime="application/pdf")
