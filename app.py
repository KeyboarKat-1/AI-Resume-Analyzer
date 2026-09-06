import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# Monkeypatch for Python 3.14 protobuf bug
import sys
sys.modules['google._upb._message'] = None
sys.modules['google._upb'] = None

import io
import json
import logging
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Gemini API Key — optional when the local analyzer is available
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("[OK] Gemini API key configured successfully.")
else:
    print("=" * 60)
    print("  ERROR: No GEMINI_API_KEY found!")
    print("  Create a .env file with: GEMINI_API_KEY=your_key_here")
    print("  Get a free key at: https://aistudio.google.com/apikey")
    print("=" * 60)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(pdf_path):
    """Extracts text from a given PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None
    return text.strip() if text.strip() else None


def _normalise_text(value):
    """Normalize PDF text without discarding line and section evidence."""
    return "\n".join(line.strip() for line in value.replace("\r", "\n").splitlines() if line.strip())


def _term_pattern(term):
    aliases = {
        "javascript": r"(?:javascript|js)",
        "postgresql": r"(?:postgresql|postgres)",
        "machine learning": r"(?:machine learning|ml)",
        "c++": r"c\+\+",
        "c#": r"c#|csharp",
        "dotnet": r"(?:\.net|dotnet)",
        "ci/cd": r"(?:ci/cd|continuous integration|continuous delivery)",
    }
    return r"(?<![a-z0-9])" + aliases.get(term, re.escape(term)) + r"(?![a-z0-9])"


def _contains_term(text, term):
    return bool(re.search(_term_pattern(term), text.lower()))


def _display_term(term):
    labels = {"javascript": "JavaScript", "postgresql": "PostgreSQL", "machine learning": "Machine Learning", "c++": "C++", "c#": "C#", "dotnet": ".NET", "ci/cd": "CI/CD", "aws": "AWS", "gcp": "GCP", "sql": "SQL", "api": "API", "html": "HTML", "css": "CSS", "nlp": "NLP", "ai": "AI"}
    return labels.get(term, term.title())


def _section_blocks(text):
    headings = {
        "summary": r"summary|objective|profile",
        "experience": r"experience|employment|work history|professional history",
        "education": r"education|academic",
        "skills": r"skills?|technologies|technical skills",
        "projects": r"projects?|portfolio",
        "certifications": r"certifications?|licenses?",
        "achievements": r"achievements?|awards?|honors?",
        "leadership": r"leadership|positions? of responsibility|activities",
    }
    lines = text.splitlines()
    blocks = {key: [] for key in headings}
    current = "other"
    for line in lines:
        heading = next((key for key, pattern in headings.items() if re.fullmatch(pattern, line.strip(), re.IGNORECASE)), None)
        if heading:
            current = heading
            continue
        if current in blocks:
            blocks[current].append(line)
    return {key: "\n".join(value).strip() for key, value in blocks.items()}


def parse_resume_evidence(resume_text):
    text = _normalise_text(resume_text)
    lower = text.lower()
    sections = _section_blocks(text)
    lines = text.splitlines()
    bullet_lines = [line for line in lines if re.match(r"^\s*(?:[-*•▪◦‣]|\d+[.)])\s+", line)]
    entry_lines = [line for line in lines if len(re.findall(r"[.!?]", line)) or re.search(r"\b(?:developed|built|implemented|managed|led|created|designed|improved|intern)\b", line, re.I)]
    quantified_lines = [line for line in lines if re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|users?|customers?|ms|seconds?|hours?|days?|dollars?)\b|\$\s*\d", line, re.I)]
    experience_text = "\n".join(filter(None, (sections["experience"], sections["projects"], sections["leadership"])))
    years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?", lower)]
    internships = len(re.findall(r"\bintern(?:ship|ed)?\b", lower))
    projects = len(re.findall(r"\b(?:project|developed|built|created|implemented)\b", sections["projects"].lower()))
    contact_signals = sum(bool(re.search(pattern, lower)) for pattern in (r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", r"\b(?:linkedin|github)\b", r"\+?\d[\d ()-]{7,}"))
    quality_issues = []
    if len(text) < 120:
        quality_issues.append("Very little selectable text was extracted from the PDF.")
    if not sections["experience"] and not sections["projects"]:
        quality_issues.append("No experience or project section was recognized.")
    return {
        "text": text, "sections": sections, "lines": lines, "bullet_lines": bullet_lines,
        "entry_lines": entry_lines, "quantified_lines": quantified_lines, "experience_text": experience_text,
        "years": years, "internships": internships, "projects": projects, "contact_signals": contact_signals,
        "extraction_confidence": "low" if quality_issues else "high", "quality_issues": quality_issues,
    }


def parse_job_description(job_description):
    text = _normalise_text(job_description)
    lower = text.lower()
    catalog = (
        "python", "javascript", "typescript", "react", "angular", "vue", "node", "express", "django", "flask", "fastapi", "java", "spring", "spring boot", "c++", "c#", "dotnet", "go", "golang", "rust", "ruby", "rails", "php", "laravel", "sql", "mysql", "postgresql", "mongodb", "redis", "docker", "kubernetes", "aws", "azure", "gcp", "devops", "ci/cd", "git", "github", "html", "css", "tailwind", "sass", "bootstrap", "graphql", "rest", "api", "machine learning", "deep learning", "nlp", "ai", "data science", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "excel", "power bi", "statistics", "agile", "scrum", "jira", "terraform", "communication", "leadership", "collaboration", "testing", "problem solving"
    )
    found = [term for term in catalog if _contains_term(lower, term)]
    required_markers = r"required|must|minimum|need|essential|responsibilit|qualif"
    preferred_markers = r"preferred|nice to have|bonus|plus|desired"
    required = []
    preferred = []
    for term in found:
        term_segments = [segment for segment in re.split(r"[.;\n]", text) if _contains_term(segment, term)]
        term_context = " ".join(term_segments).lower()
        if re.search(preferred_markers, term_context) and not re.search(required_markers, term_context):
            preferred.append(term)
        else:
            required.append(term)
    if not required and not preferred:
        required = found[:]
    required = list(dict.fromkeys(required))
    preferred = list(dict.fromkeys(preferred))
    education = list(dict.fromkeys(re.findall(r"\b(?:bachelor(?:'s)?|master(?:'s)?|phd|doctorate|associate(?:'s)?|b\.s\.?|m\.s\.?)\b", lower)))
    years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?", lower)]
    responsibilities = [line.strip(" -*•") for line in text.splitlines() if re.search(r"\b(?:develop|design|build|maintain|lead|manage|deploy|analy[sz]e|test|implement)\w*\b", line, re.I)]
    meaningful_words = [word for word in re.findall(r"[a-z0-9+#./-]+", lower) if word not in {"a", "an", "and", "as", "at", "be", "for", "in", "is", "of", "on", "or", "the", "to", "with"}]
    sufficient = len(meaningful_words) >= 3 or len(found) >= 2 or bool(years or education or responsibilities)
    return {"text": text, "required": required, "preferred": preferred, "education": education, "years": years, "responsibilities": responsibilities, "sufficient": sufficient, "insufficiency_reason": "Job description is too short to perform a reliable job-specific analysis. Please provide the complete job description." if not sufficient else None}


def generate_evidence_analysis(resume_text, job_description):
    """Build the complete result from structured evidence, with one score source."""
    resume = parse_resume_evidence(resume_text)
    job = parse_job_description(job_description)
    if not job["sufficient"]:
        return {"error": job["insufficiency_reason"], "analysis_status": "insufficient_job_description", "resume_evidence": {"extraction_confidence": resume["extraction_confidence"], "quality_issues": resume["quality_issues"]}}
    resume_lower = resume["text"].lower()

    def bounded(value):
        return max(0, min(100, int(round(value))))

    def evidence_for(term):
        locations = []
        for section, content in resume["sections"].items():
            if content and _contains_term(content, term):
                locations.append(section.title())
        return locations

    def skill_record(term, status, locations):
        label = _display_term(term)
        evidence = ", ".join(locations) if locations else "Not found"
        return {"name": label, "status": status, "evidence": evidence}

    all_jd_terms = list(dict.fromkeys(job["required"] + job["preferred"]))
    matched_required = []
    matched_preferred = []
    missing_required = []
    missing_preferred = []
    matched_skills = []
    partial_skills = []
    missing_skills = []
    for term in all_jd_terms:
        locations = evidence_for(term)
        in_resume = bool(locations) or _contains_term(resume_lower, term)
        strong = bool(set(locations) & {"Skills", "Experience", "Projects", "Education", "Certifications"})
        if in_resume and strong:
            item = skill_record(term, "explicit" if "Skills" in locations else "evidenced", locations)
            matched_skills.append({"name": item["name"], "proficiency": bounded(55 + 15 * min(len(locations), 3)), "status": item["status"], "evidence": item["evidence"]})
            (matched_required if term in job["required"] else matched_preferred).append(item)
        elif in_resume:
            item = skill_record(term, "weak", locations or ["Other text"])
            partial_skills.append(item)
            (matched_required if term in job["required"] else matched_preferred).append(item)
        else:
            item = {"name": _display_term(term), "importance": "high" if term in job["required"] else "low", "recommendation": f"Do not claim {_display_term(term)} without experience. Add it only after gaining verifiable experience.", "status": "missing", "evidence": "Not found in resume"}
            missing_skills.append(item)
            (missing_required if term in job["required"] else missing_preferred).append(item)

    catalog = {"python", "javascript", "typescript", "react", "angular", "vue", "node", "django", "flask", "java", "spring", "sql", "mysql", "postgresql", "mongodb", "docker", "kubernetes", "aws", "azure", "gcp", "git", "github", "html", "css", "graphql", "rest", "api", "machine learning", "deep learning", "nlp", "ai", "data science", "pandas", "numpy", "tensorflow", "pytorch", "agile", "scrum", "jira", "terraform", "testing", "leadership", "communication"}
    additional = [{"name": _display_term(term), "evidence": ", ".join(evidence_for(term))} for term in catalog if _contains_term(resume_lower, term) and term not in all_jd_terms]

    required_count = len(job["required"])
    preferred_count = len(job["preferred"])
    keyword_score = bounded(100 * len([item for item in matched_required if item["status"] != "weak"]) / required_count) if required_count else 0
    technical_score = bounded(100 * (len(matched_required) + 0.5 * len(partial_skills)) / len(all_jd_terms)) if all_jd_terms else 0

    professional_lines = [line for line in resume["sections"]["experience"].splitlines() + resume["sections"]["leadership"].splitlines() if line.strip()]
    project_lines = [line for line in resume["sections"]["projects"].splitlines() if line.strip()]
    relevant_professional_lines = [line for line in professional_lines if any(_contains_term(line, term) for term in all_jd_terms)]
    relevant_project_lines = [line for line in project_lines if any(_contains_term(line, term) for term in all_jd_terms)]
    relevant_lines = relevant_professional_lines + relevant_project_lines
    required_years = max(job["years"] or [0])
    candidate_years = max(resume["years"] or [0])
    duration_score = bounded(100 * min(candidate_years / required_years, 1)) if required_years else 0
    project_credit = min(len(relevant_project_lines) * 8, 20)
    internship_credit = min(resume["internships"] * 15, 20)
    professional_relevance = bounded(100 * len(relevant_professional_lines) / max(len(professional_lines), 1)) if relevant_professional_lines else 0
    experience_score = bounded((duration_score * 0.55) + (professional_relevance * 0.30) + project_credit + internship_credit) if required_years else bounded((professional_relevance * 0.65) + project_credit + internship_credit)

    education_required = bool(job["education"])
    education_present = bool(re.search(r"\b(?:bachelor(?:'s)?|master(?:'s)?|phd|doctorate|associate(?:'s)?|b\.s\.?|m\.s\.?)\b", resume_lower))
    education_score = 50 if not education_required else (100 if any(_contains_term(resume_lower, requirement) for requirement in job["education"]) else 0)
    section_count = sum(bool(value) for value in resume["sections"].values())
    structural_bullets = max(len(resume["bullet_lines"]), len(resume["entry_lines"]) if resume["sections"]["experience"] or resume["sections"]["projects"] else 0)
    formatting_score = bounded((section_count / 8) * 55 + min(structural_bullets, 10) / 10 * 25 + resume["contact_signals"] / 3 * 20)
    if resume["extraction_confidence"] == "low":
        formatting_score = min(formatting_score, 45)

    breakdown = {"keywords": keyword_score, "formatting": formatting_score, "experience": experience_score, "education": education_score, "skills": technical_score}
    ats_score = bounded(breakdown["keywords"] * .30 + breakdown["skills"] * .30 + breakdown["experience"] * .20 + breakdown["education"] * .10 + breakdown["formatting"] * .10)

    improvements = []
    if missing_required:
        names = ", ".join(item["name"] for item in missing_required)
        improvements.append({"category": "keywords", "priority": "critical", "title": f"Address required gaps: {names}", "description": f"Problem: the JD requires {names}. Recommendation: do not claim these skills without experience; add truthful evidence after gaining it. Evidence: these requirements were not found in the resume."})
    if required_years and candidate_years < required_years:
        improvements.append({"category": "experience", "priority": "critical", "title": "Clarify the experience gap", "description": f"Problem: the JD asks for {required_years}+ years and the resume states {candidate_years} years. Recommendation: emphasize relevant internships and projects, without presenting them as professional years."})
    if not resume["quantified_lines"]:
        improvements.append({"category": "impact", "priority": "important", "title": "Add measurable outcomes", "description": "Problem: no quantified achievement line was extracted. Recommendation: add truthful metrics to relevant project or experience bullets."})
    if resume["extraction_confidence"] == "low":
        improvements.append({"category": "formatting", "priority": "important", "title": "Improve selectable PDF text", "description": f"Problem: extraction confidence is low because {', '.join(resume['quality_issues'])} Recommendation: upload a text-based PDF with recognizable headings."})
    if not improvements:
        improvements.append({"category": "content", "priority": "nice-to-have", "title": "Keep evidence aligned", "description": f"The resume provides evidence for {len(matched_required)} of {required_count} required terms. Keep those terms tied to concrete work or project outcomes."})

    question_topics = [_display_term(term) for term in job["required"][:5]] + [_display_term(term) for term in job["preferred"][:2]]
    interview_questions = []
    for topic in dict.fromkeys(question_topics):
        resume_evidence = next((item["evidence"] for item in matched_skills + partial_skills if item["name"] == topic), "Not found in resume")
        if resume_evidence != "Not found in resume":
            question = f"Your resume references {topic} in {resume_evidence}. What problem did you solve with it, and what was the outcome?"
            category = "project-based"
        else:
            question = f"The JD requires {topic}, which is not evidenced in the resume. How would you approach becoming productive with it in this role?"
            category = "JD-specific"
        interview_questions.append({"question": question, "category": category, "difficulty": "medium", "tips": f"Use only evidence from the resume when answering; explain the gap honestly where {topic} is not present."})
    for line in relevant_lines[:3]:
        interview_questions.append({"question": f"Walk through this resume evidence and its relevance to the role: {line}", "category": "role-specific", "difficulty": "medium", "tips": "Explain your individual contribution, the technology used, and the result."})
    interview_questions = interview_questions[:12]

    strengths = []
    if matched_skills:
        strengths.append(f"Required skills evidenced in {', '.join(item['name'] for item in matched_skills)} ({', '.join(sorted({item['evidence'] for item in matched_skills}))}).")
    if resume["quantified_lines"]:
        strengths.append(f"Quantified evidence appears in: {resume['quantified_lines'][0]}")
    if resume["internships"] or resume["projects"]:
        strengths.append(f"The resume includes {resume['internships']} internship signal(s) and {resume['projects']} project/work evidence signal(s).")
    growth_areas = []
    if missing_required:
        growth_areas.append(f"The JD gaps are {', '.join(item['name'] for item in missing_required)}.")
    if partial_skills:
        growth_areas.append(f"These terms appear weakly or outside a recognized skills/experience section: {', '.join(item['name'] for item in partial_skills)}.")
    recommended = [f"Document verifiable evidence for {item['name']} before claiming it." for item in missing_required[:3]]
    if not recommended:
        recommended.append("Keep each matched requirement tied to a specific project or work outcome.")
    career = {"role_fit": ats_score, "strengths": strengths, "growth_areas": growth_areas, "recommended_next_steps": recommended, "career_trajectory": f"Based on the extracted evidence, this resume is a {ats_score}% fit for the stated role. The next step is to close the documented gaps: {', '.join(item['name'] for item in missing_required[:2]) or 'none detected'}.", "salary_context": "Salary cannot be inferred reliably from this resume and JD alone; use the documented skill, experience, and education match when comparing roles."}
    return {"ats_score": ats_score, "ats_breakdown": breakdown, "keyword_match": {"matched_required": matched_required, "missing_required": missing_required, "matched_preferred": matched_preferred, "missing_preferred": missing_preferred}, "resume_evidence": {"extraction_confidence": resume["extraction_confidence"], "quality_issues": resume["quality_issues"], "sections": {key: bool(value) for key, value in resume["sections"].items()}, "bullet_count": structural_bullets}, "improvements": improvements, "interview_questions": interview_questions, "skill_gap": {"matched_skills": matched_skills, "partially_matched_skills": partial_skills, "missing_skills": missing_skills, "additional_resume_skills": additional}, "career_insights": career}


def generate_local_fallback_analysis(resume_text, job_description):
    """Create a deterministic analysis from the two supplied documents.

    This path is used when Gemini is unavailable. It deliberately has no
    baseline scores or fallback content: every value is derived from evidence
    found in the resume and job description.
    """
    return generate_evidence_analysis(resume_text, job_description)

    # Retained below only as historical context; the evidence analyzer above
    # is the sole producer used by the application.
    import re

    resume_lower = resume_text.lower()
    jd_lower = job_description.lower()
    skill_catalog = (
        "python", "javascript", "typescript", "react", "angular", "vue", "node", "express", "django", "flask",
        "fastapi", "java", "spring", "c++", "c#", "dotnet", "go", "golang", "rust", "ruby", "rails", "php",
        "laravel", "sql", "mysql", "postgresql", "mongodb", "redis", "docker", "kubernetes", "aws", "azure",
        "gcp", "devops", "ci/cd", "git", "github", "html", "css", "tailwind", "sass", "bootstrap", "graphql",
        "rest", "api", "machine learning", "deep learning", "nlp", "ai", "data science", "pandas", "numpy",
        "scikit-learn", "tensorflow", "pytorch", "agile", "scrum", "jira"
    )
    stopwords = {
        "the", "and", "a", "of", "to", "is", "in", "that", "it", "you", "for", "on", "with",
        "as", "this", "at", "by", "an", "be", "are", "from", "or", "about", "our", "your", "we",
        "they", "he", "she", "his", "her", "their", "them", "me", "us", "i", "will", "have", "has",
        "who", "what", "when", "where", "which", "while", "able", "work", "working", "role", "team"
    }

    def contains_term(text, term):
        pattern = r"(?<![a-z0-9])" + re.escape(term).replace(r"/", r"[/\\]") + r"(?![a-z0-9])"
        return bool(re.search(pattern, text))

    def score(value):
        return max(0, min(100, int(round(value))))

    resume_words = set(re.findall(r"[a-z0-9]+", resume_lower)) - stopwords
    jd_words = set(re.findall(r"[a-z0-9]+", jd_lower)) - stopwords
    matched_words = resume_words & jd_words
    keyword_score = score(100 * len(matched_words) / len(jd_words)) if jd_words else 0

    required_skills = []
    for skill in skill_catalog:
        if skill not in required_skills and contains_term(jd_lower, skill):
            required_skills.append(skill)
    matched_skills = []
    missing_skills = []
    for skill in required_skills:
        display_name = skill.upper() if skill in {"aws", "gcp", "sql", "api", "html", "css", "nlp", "ai"} else skill.title()
        if skill == "dotnet":
            display_name = ".NET"
        occurrences = len(re.findall(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", resume_lower))
        if occurrences:
            proficiency = score(35 + min(occurrences, 4) * 12 + (15 if re.search(r"senior|lead|principal|architect", resume_lower) else 0))
            matched_skills.append({"name": display_name, "proficiency": proficiency})
        else:
            importance = "high" if skill in required_skills[:max(1, len(required_skills) // 3)] else "medium"
            missing_skills.append({
                "name": display_name,
                "importance": importance,
                "recommendation": f"Add verifiable {display_name} experience only if you have it; otherwise build a relevant project and describe its outcome."
            })

    skill_score = score(100 * len(matched_skills) / len(required_skills)) if required_skills else keyword_score
    section_count = sum(bool(re.search(pattern, resume_lower)) for pattern in (
        r"\b(summary|objective|profile)\b", r"\bexperience\b", r"\beducation\b", r"\bskills?\b",
        r"\bprojects?\b", r"\b(certifications?|awards?)\b"
    ))
    bullet_count = len(re.findall(r"(?:^|\n)\s*[-*•]\s+", resume_text))
    contact_count = sum(bool(re.search(pattern, resume_lower)) for pattern in (r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", r"\b(?:linkedin|github)\b", r"\+?\d[\d ()-]{7,}"))
    formatting_score = score(100 * (section_count + min(bullet_count, 10) / 10 + contact_count) / 9)

    jd_years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?", jd_lower)]
    resume_years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?", resume_lower)]
    if jd_years:
        experience_score = score(100 * min(max(resume_years or [0]) / max(jd_years), 1))
    else:
        experience_signals = sum(bool(re.search(pattern, resume_lower)) for pattern in (r"\bexperience\b", r"\bmanaged\b", r"\bled\b", r"\bdeveloped\b", r"\bimplemented\b"))
        experience_score = score(100 * experience_signals / 5)

    education_required = bool(re.search(r"\b(bachelor|master|phd|degree|b\.s\.?|m\.s\.?)\b", jd_lower))
    education_present = bool(re.search(r"\b(bachelor|master|phd|degree|b\.s\.?|m\.s\.?)\b", resume_lower))
    education_score = 100 if not education_required else (100 if education_present else 0)
    ats_score = score(keyword_score * 0.30 + skill_score * 0.25 + experience_score * 0.25 + education_score * 0.10 + formatting_score * 0.10)

    improvements = []
    if missing_skills:
        names = ", ".join(item["name"] for item in missing_skills[:4])
        improvements.append({"category": "keywords", "priority": "critical", "title": f"Address missing requirements: {names}", "description": f"The job description includes {names}, but those terms are not evidenced in the uploaded resume."})
    if formatting_score < 70:
        improvements.append({"category": "formatting", "priority": "important", "title": "Improve ATS-readable structure", "description": f"The resume contains {section_count} recognizable sections, {bullet_count} bullet points, and {contact_count} contact signals. Use clear headings and concise bullets where evidence is missing."})
    if not re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|users?|customers?|ms|seconds?|hours?|days?|dollars?|\$)\b", resume_lower):
        improvements.append({"category": "impact", "priority": "important", "title": "Quantify resume outcomes", "description": "No measurable outcome was detected in the resume. Add metrics to relevant experience bullets only where they accurately describe your work."})
    if keyword_score < 60:
        improvements.append({"category": "keywords", "priority": "important", "title": "Align wording with the job description", "description": f"Only {len(matched_words)} of {len(jd_words)} meaningful job-description terms were found in the resume. Mirror applicable terminology in the relevant experience or skills section."})
    if not improvements:
        improvements.append({"category": "content", "priority": "nice-to-have", "title": "Preserve the current match", "description": f"The resume covers all detected required skills and has a {keyword_score}% keyword overlap. Keep the evidence specific and current for this role."})

    interview_questions = []
    question_terms = [item["name"] for item in matched_skills[:3]] or [word for word in sorted(jd_words & resume_words)[:3]]
    for term in question_terms:
        interview_questions.append({"question": f"Describe the most relevant result you achieved using {term} in the experience shown on your resume.", "category": "technical", "difficulty": "medium", "tips": f"Use a concrete example from the resume, explain your decision-making around {term}, and quantify the result if the source document supports it."})
    if missing_skills:
        interview_questions.append({"question": f"How would you close the gap in {missing_skills[0]['name']} for this role?", "category": "situational", "difficulty": "medium", "tips": f"Connect your existing evidence to {missing_skills[0]['name']} and give a specific, realistic learning or delivery plan."})
    if not interview_questions and jd_words:
        interview_questions.append({"question": f"Which experience in your resume best demonstrates fit for a role focused on {' '.join(sorted(jd_words)[:3])}?", "category": "behavioral", "difficulty": "medium", "tips": "Answer with a specific resume example and explain the outcome."})

    strengths = [f"The resume evidences {', '.join(item['name'] for item in matched_skills)} against the job requirements."] if matched_skills else []
    if formatting_score >= 60:
        strengths.append(f"The extracted resume has {section_count} recognizable sections and {bullet_count} bullet points.")
    growth_areas = [f"Missing job requirements: {', '.join(item['name'] for item in missing_skills)}."] if missing_skills else []
    if experience_score < 60:
        growth_areas.append("The resume does not provide enough evidence for the experience signals requested by this job description.")
    career_trajectory = f"The evidence supports a {ats_score}% match for this target role. Prioritize {', '.join(item['name'] for item in missing_skills[:2]) or 'stronger quantified outcomes'} before applying to improve alignment."
    salary_context = f"Compensation competitiveness cannot be priced from a resume alone; this profile shows {ats_score}% role alignment, with {len(missing_skills)} detected requirement gaps affecting positioning."

    return {"ats_score": ats_score, "ats_breakdown": {"keywords": keyword_score, "formatting": formatting_score, "experience": experience_score, "education": education_score, "skills": skill_score}, "improvements": improvements, "interview_questions": interview_questions, "skill_gap": {"matched_skills": matched_skills, "missing_skills": missing_skills}, "career_insights": {"role_fit": ats_score, "strengths": strengths, "growth_areas": growth_areas, "career_trajectory": career_trajectory, "salary_context": salary_context}}


def analyze_resume_with_gemini(resume_text, job_description):
    """Ask Gemini for structured context, then use local evidence as authority."""

    if not GEMINI_API_KEY:
        print("[LOCAL ANALYSIS] Gemini key is not configured; using evidence-based analysis.")
        return generate_local_fallback_analysis(resume_text, job_description)

    if GEMINI_API_KEY == "your_api_key_here":
        if not app.config.get('TESTING'):
            print("[LOCAL ANALYSIS] Using evidence-based local analysis (placeholder API key).")
            return generate_local_fallback_analysis(resume_text, job_description)

    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=generation_config,
    )

    prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer, career coach, and senior technical recruiter.

IMPORTANT: Carefully analyze the SPECIFIC resume content against the SPECIFIC job description provided below. Every score, suggestion, question, and skill assessment MUST be derived from the actual content of these two documents. Do NOT use generic or placeholder responses.

Return EXACTLY this JSON structure:
{{
    "ats_score": <integer 0-100 — calculated by comparing resume keywords, skills, and experience against what the job description requires>,
    "ats_breakdown": {{
        "keywords": <integer 0-100 — percentage of JD keywords found in resume>,
        "formatting": <integer 0-100 — resume structure, readability, ATS-parsability>,
        "experience": <integer 0-100 — how well resume experience matches JD requirements>,
        "education": <integer 0-100 — education match with JD requirements>,
        "skills": <integer 0-100 — technical/soft skills overlap with JD>
    }},
    "improvements": [
        {{
            "category": "<content|keywords|formatting|impact>",
            "priority": "<critical|important|nice-to-have>",
            "title": "<short actionable title specific to THIS resume>",
            "description": "<detailed suggestion referencing specific sections/content from THIS resume and THIS job description>"
        }}
    ],
    "interview_questions": [
        {{
            "question": "<interview question tailored to THIS role and THIS candidate's background>",
            "category": "<behavioral|technical|system-design|coding|situational>",
            "difficulty": "<easy|medium|hard>",
            "tips": "<preparation tips specific to THIS candidate's experience>"
        }}
    ],
    "skill_gap": {{
        "matched_skills": [
            {{"name": "<skill from resume that matches JD>", "proficiency": <integer 0-100 estimated from resume context>}}
        ],
        "missing_skills": [
            {{"name": "<skill required by JD but missing from resume>", "importance": "<high|medium|low>", "recommendation": "<specific learning resource or action>"}}
        ]
    }},
    "career_insights": {{
        "role_fit": <integer 0-100 — overall fit assessment>,
        "strengths": ["<strength derived from THIS resume relative to THIS JD>"],
        "growth_areas": ["<gap derived from comparing THIS resume to THIS JD>"],
        "career_trajectory": "<personalized career advice based on THIS candidate's current skills and THIS target role>",
        "salary_context": "<competitiveness context based on skill match>"
    }}
}}

Scoring rules for ats_score:
- Count how many required skills/keywords from the JD appear in the resume
- Assess whether the years/type of experience match
- Check if education requirements are met
- Evaluate formatting for ATS compatibility (bullet points, clear sections, no tables/graphics)
- The canonical score is weighted: keywords(30%) + skills(30%) + experience(20%) + education(10%) + formatting(10%)

Guidelines:
- Provide 4-8 improvement suggestions, each referencing specific content from the resume
- Generate 6-10 interview questions tailored to the specific role and candidate background
- List ALL skills from the resume that match JD requirements with realistic proficiency
- List ALL skills the JD requires that are MISSING from the resume
- Be brutally honest — if the resume is a poor match, the score should reflect that
- Reference specific sections, job titles, technologies from the actual resume text

Job Description:
---
{job_description}
---

Resume Text:
---
{resume_text}
---"""

    try:
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        if not isinstance(result, dict):
            raise ValueError("AI response must be a JSON object")

        # Gemini may enrich prose, but the evidence analyzer is authoritative
        # for every displayed score, skill state, and recommendation. This
        # prevents a valid-looking model response from contradicting the PDF.
        return generate_evidence_analysis(resume_text, job_description)

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        try:
            print(f"Raw response preview: {response.text[:500]}")
        except Exception:
            pass
        try:
            retry_prompt = f"Return valid JSON only for the requested resume analysis. Do not add markdown or commentary. Resume: {resume_text}\nJob description: {job_description}"
            model.generate_content(retry_prompt)
        except Exception:
            pass
        print("[LOCAL ANALYSIS] Falling back after JSON parsing error.")
        return generate_local_fallback_analysis(resume_text, job_description)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        print("[LOCAL ANALYSIS] Falling back after API error.")
        return generate_local_fallback_analysis(resume_text, job_description)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    file = request.files['resume']
    job_description = request.form.get('job_description', '')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not job_description.strip():
        return jsonify({"error": "Job description is required"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            resume_text = extract_text_from_pdf(filepath)
            if not resume_text:
                return jsonify({"error": "Could not extract text from the PDF. Make sure it contains selectable text (not a scanned image)."}), 500

            analysis_result = analyze_resume_with_gemini(resume_text, job_description)

            if "error" in analysis_result:
                return jsonify(analysis_result), 400

            return jsonify(analysis_result)

        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    else:
        return jsonify({"error": "Invalid file type. Only PDF files are allowed."}), 400


# ==============================================================
# PDF Report Generation (Server-Side with ReportLab)
# ==============================================================

def draw_wrapped_text(c, text, x, y, max_width, font_name, font_size, line_height=None, color=None):
    """Draw text that wraps within max_width. Returns the new y position."""
    if not text:
        return y
    if color:
        c.setFillColor(color)
    if line_height is None:
        line_height = font_size + 3
    c.setFont(font_name, font_size)

    words = str(text).split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if c.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    for line in lines:
        if y < 50:  # Near bottom of page
            c.showPage()
            y = 780
            c.setFont(font_name, font_size)
            if color:
                c.setFillColor(color)
        c.drawString(x, y, line)
        y -= line_height
    return y


def check_page_break(c, y, needed=60):
    """Check if we need a new page. Returns new y position."""
    if y < needed:
        c.showPage()
        return 780
    return y


def draw_section_header(c, title, y):
    """Draw a styled section header. Returns new y position."""
    y = check_page_break(c, y, 80)
    y -= 10
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(HexColor('#1e40af'))
    c.drawString(40, y, title)
    y -= 3
    c.setStrokeColor(HexColor('#3b82f6'))
    c.setLineWidth(1.5)
    c.line(40, y, 555, y)
    y -= 18
    c.setFillColor(HexColor('#000000'))
    return y


def draw_score_box(c, label, score, x, y, width=240, height=60, color='#3b82f6'):
    """Draw a score metric box."""
    # Box background
    c.setFillColor(HexColor('#f1f5f9'))
    c.roundRect(x, y - height, width, height, 6, fill=1, stroke=0)
    # Border
    c.setStrokeColor(HexColor('#cbd5e1'))
    c.setLineWidth(0.5)
    c.roundRect(x, y - height, width, height, 6, fill=0, stroke=1)
    # Label
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor('#64748b'))
    c.drawCentredString(x + width / 2, y - 16, label.upper())
    # Score
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(HexColor(color))
    c.drawCentredString(x + width / 2, y - 46, f"{score}/100")
    # Grade text
    c.setFont("Helvetica-Bold", 9)
    if score >= 80:
        grade, g_color = "EXCELLENT", '#166534'
    elif score >= 65:
        grade, g_color = "GOOD MATCH", '#854d0e'
    elif score >= 45:
        grade, g_color = "FAIR", '#9a3412'
    else:
        grade, g_color = "NEEDS WORK", '#991b1b'
    c.setFillColor(HexColor(g_color))
    c.drawCentredString(x + width / 2, y - 58, grade)


def generate_pdf_report(data):
    """Generate a complete PDF report using ReportLab.
    Returns a BytesIO buffer containing the PDF.
    """
    print("[PDF] === Starting server-side PDF generation ===")

    # ---- Extract and validate all data fields ----
    ats_score = data.get('ats_score', 0)
    if isinstance(ats_score, str):
        import re
        m = re.search(r'\d+', ats_score)
        ats_score = int(m.group()) if m else 0
    ats_score = int(ats_score)
    print(f"[PDF] ATS Score: {ats_score}")

    breakdown = data.get('ats_breakdown', {})
    improvements = data.get('improvements', [])
    interview_questions = data.get('interview_questions', [])
    skill_gap = data.get('skill_gap', {})
    matched_skills = skill_gap.get('matched_skills', [])
    missing_skills = skill_gap.get('missing_skills', [])
    career_insights = data.get('career_insights', {})
    role_fit = career_insights.get('role_fit', 0)
    strengths = career_insights.get('strengths', [])
    growth_areas = career_insights.get('growth_areas', [])
    trajectory = career_insights.get('career_trajectory', 'N/A')
    salary_ctx = career_insights.get('salary_context', 'N/A')

    print(f"[PDF] Improvements: {len(improvements)}, Matched skills: {len(matched_skills)}, "
          f"Missing skills: {len(missing_skills)}, Interview Qs: {len(interview_questions)}")

    # ---- Create PDF in memory ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4  # 595 x 842 points
    print(f"[PDF] Canvas created — page size: {page_width:.0f} x {page_height:.0f}")

    # Colors
    DARK = HexColor('#0f172a')
    GRAY = HexColor('#475569')
    LIGHT_GRAY = HexColor('#64748b')
    BLUE = HexColor('#3b82f6')
    GREEN = HexColor('#166534')
    RED = HexColor('#991b1b')
    AMBER = HexColor('#92400e')
    BLACK = HexColor('#000000')

    # ============================================================
    # PAGE 1: Header + Scores + Breakdown
    # ============================================================
    y = 790

    # --- Report Header ---
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(DARK)
    c.drawString(40, y, "CareerAI Pro")
    c.setFont("Helvetica", 10)
    c.setFillColor(LIGHT_GRAY)
    c.drawString(40, y - 18, "AI-Powered Career & Resume Analysis Report")
    c.drawRightString(555, y - 18, f"Generated: {datetime.now().strftime('%B %d, %Y')}")
    y -= 25
    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.line(40, y, 555, y)
    y -= 30
    print("[PDF] Header drawn")

    # --- Score Boxes ---
    draw_score_box(c, "ATS Match Score", ats_score, 40, y, 245, 65, '#3b82f6')
    draw_score_box(c, "Role Fit Index", int(role_fit), 310, y, 245, 65, '#8b5cf6')
    y -= 85

    # --- ATS Category Breakdown ---
    y = draw_section_header(c, "ATS Category Breakdown", y)
    categories = ['keywords', 'formatting', 'experience', 'education', 'skills']
    for cat in categories:
        val = breakdown.get(cat, 0)
        if isinstance(val, str):
            try:
                val = int(val)
            except ValueError:
                val = 0
        y = check_page_break(c, y, 25)

        # Category label
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawString(50, y, cat.capitalize())

        # Progress bar background
        bar_x, bar_w, bar_h = 160, 300, 10
        c.setFillColor(HexColor('#e2e8f0'))
        c.roundRect(bar_x, y - 2, bar_w, bar_h, 3, fill=1, stroke=0)

        # Progress bar fill
        fill_w = max(1, (val / 100) * bar_w)
        c.setFillColor(BLUE)
        c.roundRect(bar_x, y - 2, fill_w, bar_h, 3, fill=1, stroke=0)

        # Percentage
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DARK)
        c.drawRightString(520, y, f"{val}%")
        y -= 24
    print(f"[PDF] Breakdown drawn — {len(categories)} categories")

    # ============================================================
    # RESUME IMPROVEMENTS
    # ============================================================
    y = draw_section_header(c, "Resume Improvements", y)
    if not improvements:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(50, y, "No improvement suggestions available.")
        y -= 20
    else:
        for i, imp in enumerate(improvements):
            y = check_page_break(c, y, 70)
            title = imp.get('title', 'Suggestion')
            desc = imp.get('description', '')
            priority = imp.get('priority', 'important')
            category = imp.get('category', 'general')

            # Priority badge color
            if priority == 'critical':
                p_color, p_label = RED, 'CRITICAL'
            elif priority == 'nice-to-have':
                p_color, p_label = GREEN, 'NICE TO HAVE'
            else:
                p_color, p_label = AMBER, 'IMPORTANT'

            # Title
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(DARK)
            c.drawString(50, y, f"{i+1}. {title}")

            # Priority label
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(p_color)
            c.drawRightString(540, y, f"[{p_label}]")
            y -= 14

            # Description
            y = draw_wrapped_text(c, desc, 60, y, 480, "Helvetica", 9, 12, GRAY)

            # Category
            c.setFont("Helvetica", 8)
            c.setFillColor(LIGHT_GRAY)
            c.drawString(60, y, f"Category: {category}")
            y -= 20
    print(f"[PDF] Improvements drawn — {len(improvements)} items")

    # ============================================================
    # SKILL GAP ANALYSIS
    # ============================================================
    y = draw_section_header(c, "Skill Gap Analysis", y)

    # -- Matched Skills --
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GREEN)
    c.drawString(50, y, "Matched Skills")
    y -= 18

    if not matched_skills:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(60, y, "No matched skills found.")
        y -= 16
    else:
        for skill in matched_skills:
            y = check_page_break(c, y, 20)
            name = skill.get('name', 'Unknown')
            prof = skill.get('proficiency', 0)
            c.setFont("Helvetica", 10)
            c.setFillColor(DARK)
            c.drawString(60, y, f"• {name}")
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(GREEN)
            c.drawRightString(540, y, f"{prof}%")
            y -= 16
    print(f"[PDF] Matched skills drawn — {len(matched_skills)} items")

    y -= 10

    # -- Missing Skills --
    y = check_page_break(c, y, 40)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(RED)
    c.drawString(50, y, "Missing Skills (To Acquire)")
    y -= 18

    if not missing_skills:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(60, y, "No missing skills identified.")
        y -= 16
    else:
        for skill in missing_skills:
            y = check_page_break(c, y, 40)
            name = skill.get('name', 'Unknown')
            importance = skill.get('importance', 'medium')
            recommendation = skill.get('recommendation', '')

            imp_color = RED if importance == 'high' else AMBER

            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(DARK)
            c.drawString(60, y, f"• {name}")
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(imp_color)
            c.drawRightString(540, y, f"[{importance.upper()}]")
            y -= 14

            if recommendation:
                y = draw_wrapped_text(c, f"→ {recommendation}", 70, y, 460, "Helvetica", 9, 12, GRAY)
            y -= 6
    print(f"[PDF] Missing skills drawn — {len(missing_skills)} items")

    # ============================================================
    # AI SUGGESTIONS (Interview Questions)
    # ============================================================
    y = draw_section_header(c, "AI-Predicted Interview Questions", y)

    if not interview_questions:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(50, y, "No interview questions generated.")
        y -= 20
    else:
        for idx, q in enumerate(interview_questions):
            y = check_page_break(c, y, 80)
            question = q.get('question', '')
            category = q.get('category', 'general')
            difficulty = q.get('difficulty', 'medium')
            tips = q.get('tips', '')

            # Question header
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(DARK)
            c.drawString(50, y, f"Q{idx+1}. ({category.capitalize()}) [{difficulty.upper()}]")
            y -= 14

            # Question text
            y = draw_wrapped_text(c, f'"{question}"', 60, y, 480, "Helvetica-Bold", 10, 13, DARK)
            y -= 4

            # Tips
            if tips:
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(LIGHT_GRAY)
                c.drawString(60, y, "Preparation Tips:")
                y -= 12
                y = draw_wrapped_text(c, tips, 70, y, 470, "Helvetica", 9, 12, GRAY)
            y -= 14
    print(f"[PDF] Interview questions drawn — {len(interview_questions)} items")

    # ============================================================
    # CAREER INSIGHTS
    # ============================================================
    y = draw_section_header(c, "Career Insights & Development", y)

    # Strengths
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(GREEN)
    c.drawString(50, y, "Core Strengths")
    y -= 16
    if not strengths:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(60, y, "No strengths data available.")
        y -= 14
    else:
        for s in strengths:
            y = check_page_break(c, y, 20)
            y = draw_wrapped_text(c, f"✓ {s}", 60, y, 480, "Helvetica", 10, 14, DARK)
    y -= 10

    # Growth Areas
    y = check_page_break(c, y, 40)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(AMBER)
    c.drawString(50, y, "Growth Areas")
    y -= 16
    if not growth_areas:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(LIGHT_GRAY)
        c.drawString(60, y, "No growth areas data available.")
        y -= 14
    else:
        for g in growth_areas:
            y = check_page_break(c, y, 20)
            y = draw_wrapped_text(c, f"△ {g}", 60, y, 480, "Helvetica", 10, 14, DARK)
    y -= 10

    # Trajectory
    y = check_page_break(c, y, 60)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(BLUE)
    c.drawString(50, y, "Career Trajectory")
    y -= 16
    y = draw_wrapped_text(c, trajectory, 60, y, 480, "Helvetica", 10, 13, GRAY)
    y -= 10

    # Salary context
    y = check_page_break(c, y, 60)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(HexColor('#7c3aed'))
    c.drawString(50, y, "Salary & Market Context")
    y -= 16
    y = draw_wrapped_text(c, salary_ctx, 60, y, 480, "Helvetica", 10, 13, GRAY)
    print("[PDF] Career insights drawn")

    # ============================================================
    # Footer on every page
    # ============================================================
    c.setFont("Helvetica", 7)
    c.setFillColor(LIGHT_GRAY)
    c.drawCentredString(page_width / 2, 25, "Generated by CareerAI Pro — AI-Powered Resume Analysis")

    # ---- Finalize ----
    c.showPage()
    c.save()
    buffer.seek(0)

    pdf_size = buffer.getbuffer().nbytes
    print(f"[PDF] === PDF generation complete — size: {pdf_size} bytes ===")

    if pdf_size < 500:
        print(f"[PDF] WARNING: PDF is suspiciously small ({pdf_size} bytes), may be blank!")

    return buffer


@app.route('/download-report', methods=['POST'])
def download_report():
    """Server-side PDF generation endpoint.
    Receives analysis data as JSON and returns a PDF file.
    """
    print("\n[DOWNLOAD] === /download-report called ===")

    try:
        data = request.get_json()

        if not data:
            print("[DOWNLOAD] ERROR: No JSON data received")
            return jsonify({"error": "No analysis data provided"}), 400

        print(f"[DOWNLOAD] Received data keys: {list(data.keys())}")

        # Validate required fields
        ats_score = data.get('ats_score')
        if ats_score is None:
            print("[DOWNLOAD] ERROR: Missing ats_score")
            return jsonify({"error": "Missing ATS score in data"}), 400

        skill_gap = data.get('skill_gap')
        if not skill_gap:
            print("[DOWNLOAD] WARNING: Missing skill_gap, using empty")
            data['skill_gap'] = {'matched_skills': [], 'missing_skills': []}

        career_insights = data.get('career_insights')
        if not career_insights:
            print("[DOWNLOAD] WARNING: Missing career_insights, using empty")
            data['career_insights'] = {'role_fit': 0, 'strengths': [], 'growth_areas': [],
                                       'career_trajectory': 'N/A', 'salary_context': 'N/A'}

        # Generate PDF
        pdf_buffer = generate_pdf_report(data)

        print("[DOWNLOAD] Sending PDF file to client")
        filename = f"CareerAI_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf"

        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"[DOWNLOAD] ERROR generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
