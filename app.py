import os
import re
from io import BytesIO
from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from docx import Document

app = Flask(__name__, static_folder=".")
CORS(app)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise EnvironmentError("❌ Missing OPENAI_API_KEY in Railway environment variables")

client = OpenAI(api_key=OPENAI_KEY)


def create_docx(cv_text: str, job_title: str):
    doc = Document()
    doc.add_heading(f"{job_title} — Tailored CV", level=1)
    doc.add_paragraph(cv_text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def extract_job_title(job_desc: str) -> str:
    title_match = re.search(r"(?i)(?:for|as)\s+([A-Za-z ]{3,50})", job_desc)
    if title_match:
        title = title_match.group(1).strip().title().replace(" ", "_")
    else:
        title = "Tailored_CV"
    return title


@app.route("/")
def home():
    # serve index.html from the same root
    return send_from_directory(".", "index.html")


@app.route("/generate", methods=["POST"])
def generate_cv():
    data = request.get_json()
    old_cv = data.get("old_cv", "")
    job_desc = data.get("job_desc", "")

    if not old_cv or not job_desc:
        return jsonify({"error": "Missing 'old_cv' or 'job_desc'"}), 400

    prompt = f"""
    You are a professional resume optimizer.
    Rewrite the following CV to be ATS-friendly and perfectly tailored to the job description.

    Format sections as:
    - Summary
    - Key Skills
    - Professional Experience
    - Education
    - Certifications (if any)

    Use concise bullet points, strong action verbs, and relevant keywords.

    === JOB DESCRIPTION ===
    {job_desc}

    === EXISTING CV ===
    {old_cv}

    Output only the final improved CV text (plain text).
    """

    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        updated_cv = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    job_title = extract_job_title(job_desc)
    buffer = create_docx(updated_cv, job_title)
    filename = f"{job_title}.docx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "ATS CV Generator running"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
