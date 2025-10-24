import os
import re
from io import BytesIO
from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Inches

# ------------------------------
# APP SETUP
# ------------------------------
app = Flask(__name__, static_folder=".")
CORS(app)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise EnvironmentError("❌ Missing OPENAI_API_KEY — add it in Railway Variables")

client = OpenAI(api_key=OPENAI_KEY)

# ------------------------------
# HELPER FUNCTIONS
# ------------------------------
def extract_job_title(job_desc: str) -> str:
    """Extract job title from job description."""
    title_match = re.search(r"(?i)(?:for|as|position:|role:)\s+([A-Za-z &/-]{3,60})", job_desc)
    if title_match:
        title = title_match.group(1).strip().title().replace(" ", "_").replace("/", "_")
    else:
        title = "Updated_CV"
    return title


def create_docx(cv_text: str, job_title: str):
    """Generate a well-formatted Word document."""
    clean_title = job_title.replace("_", " ")
    doc = Document()

    # Title
    title_para = doc.add_paragraph()
    run = title_para.add_run(f"{clean_title} CV")
    run.bold = True
    run.font.size = Pt(18)
    doc.add_paragraph()

    # Split into logical sections using simple cues
    sections = re.split(r"(?=Summary|Key Skills|Professional Experience|Education|Certifications|Additional Information)", cv_text)

    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        heading = lines[0].strip()
        content = "\n".join(lines[1:]).strip()

        # Add heading
        head = doc.add_heading(heading, level=2)
        head.bold = True

        # Add content with spacing
        for para in content.split("\n"):
            if para.strip():
                p = doc.add_paragraph(para.strip())
                p_format = p.paragraph_format
                p_format.space_after = Pt(6)

        doc.add_paragraph()

    # Adjust margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Save to buffer
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ------------------------------
# ROUTES
# ------------------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/generate", methods=["POST"])
def generate_cv():
    """Generate the ATS-optimized CV"""
    try:
        data = request.get_json(force=True)
        old_cv = data.get("old_cv", "").strip()
        job_desc = data.get("job_desc", "").strip()

        if not old_cv or not job_desc:
            return jsonify({"error": "Missing 'old_cv' or 'job_desc'"}), 400

        # --- Create the AI prompt ---
        prompt = f"""
        You are a professional ATS resume writer.
        Rewrite the following CV to match this job description.
        Focus on clarity, achievements, and relevant keywords.
        Structure output exactly as follows:

        ============================
        FULL NAME
        LOCATION | CONTACT INFO | EMAIL | LINKEDIN

        Summary
        [2–3 lines highlighting strengths aligned to the job]

        Key Skills
        - [8–12 skill points with keywords]

        Professional Experience
        [Company Name], [Role] | [Dates]
        - [3–5 bullet points per job with metrics or achievements]

        Education
        [Degree], [Institution], [Year or GPA if strong]

        Certifications
        [Certifications if applicable]

        Additional Information
        [Optional section for languages, awards, or technical tools]
        ============================

        === JOB DESCRIPTION ===
        {job_desc}

        === CURRENT CV ===
        {old_cv}

        Output only the full rewritten CV in plain text (no markdown).
        """

        # --- Call OpenAI ---
        response = client.chat.completions.create(
            model="gpt-4-turbo",  # ✅ Stable model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        updated_cv = response.choices[0].message.content.strip()

        # Extract the job title dynamically
        job_title = extract_job_title(job_desc)

        # Generate .docx
        buffer = create_docx(updated_cv, job_title)
        filename = f"{job_title}.docx"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except Exception as e:
        print("❌ Backend error:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "Backend running fine"})


# ------------------------------
# MAIN
# ------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
