import unittest
from unittest.mock import patch, MagicMock
import io
import json
import os
import sys

# Set a dummy env var before importing app to avoid warnings and errors
os.environ["GEMINI_API_KEY"] = "dummy_key_for_testing"

import app

class TestResumeAnalyzer(unittest.TestCase):
    def setUp(self):
        # Set up Flask test client
        app.app.config['TESTING'] = True
        app.app.config['UPLOAD_FOLDER'] = 'test_uploads'
        self.client = app.app.test_client()

    def test_allowed_file(self):
        self.assertTrue(app.allowed_file('resume.pdf'))
        self.assertTrue(app.allowed_file('RESUME.PDF'))
        self.assertFalse(app.allowed_file('resume.png'))
        self.assertFalse(app.allowed_file('resume.txt'))
        self.assertFalse(app.allowed_file('resume'))

    @patch('app.PdfReader')
    def test_extract_text_from_pdf_success(self, mock_pdf_reader):
        # Mock PdfReader and pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is a resume content."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader

        with patch('builtins.open', unittest.mock.mock_open()):
            text = app.extract_text_from_pdf('dummy.pdf')
            self.assertEqual(text, "This is a resume content.")

    @patch('app.PdfReader')
    def test_extract_text_from_pdf_empty(self, mock_pdf_reader):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader

        with patch('builtins.open', unittest.mock.mock_open()):
            text = app.extract_text_from_pdf('dummy.pdf')
            self.assertIsNone(text)

    @patch('app.PdfReader')
    def test_extract_text_from_pdf_exception(self, mock_pdf_reader):
        mock_pdf_reader.side_effect = Exception("File read error")
        with patch('builtins.open', unittest.mock.mock_open()):
            text = app.extract_text_from_pdf('dummy.pdf')
            self.assertIsNone(text)

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_resume_with_gemini_success(self, mock_gen_model):
        mock_response = MagicMock()
        expected_json = {
            "ats_score": 85,
            "ats_breakdown": {"keywords": 80, "formatting": 90, "experience": 85, "education": 100, "skills": 80},
            "improvements": [],
            "interview_questions": [],
            "skill_gap": {"matched_skills": [], "missing_skills": []},
            "career_insights": {"role_fit": 85, "strengths": [], "growth_areas": [], "career_trajectory": "", "salary_context": ""}
        }
        mock_response.text = json.dumps(expected_json)
        
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_model_instance

        # Temporarily make sure API key is set
        with patch('app.GEMINI_API_KEY', 'dummy_key'):
            res = app.analyze_resume_with_gemini("resume text", "Python developer with SQL")
            expected = app.generate_evidence_analysis("resume text", "Python developer with SQL")
            self.assertEqual(res["ats_score"], expected["ats_score"])
            self.assertEqual(res["ats_breakdown"], expected["ats_breakdown"])

    def test_analyze_resume_with_gemini_no_api_key(self):
        with patch('app.GEMINI_API_KEY', ''):
            res = app.analyze_resume_with_gemini("resume text", "Python developer with SQL")
            self.assertIn("ats_score", res)
            self.assertIn("resume_evidence", res)

    def test_local_analysis_has_no_demo_defaults(self):
        result = app.generate_local_fallback_analysis(
            "Alex Example\nCustomer support representative\nHigh school diploma",
            "Senior Python engineer with Kubernetes and AWS experience"
        )

        self.assertEqual(result["skill_gap"]["matched_skills"], [])
        self.assertEqual(result["skill_gap"]["missing_skills"][0]["name"], "Python")
        self.assertNotIn("Software Engineering", str(result))
        self.assertEqual(result["ats_breakdown"]["skills"], 0)
        self.assertEqual(result["ats_breakdown"]["education"], 50)

    def test_local_analysis_changes_with_resume_evidence(self):
        job = "Python developer with SQL and AWS, 3 years experience, bachelor's degree"
        without_match = app.generate_local_fallback_analysis("Retail assistant", job)
        with_match = app.generate_local_fallback_analysis(
            "Python SQL AWS\n3 years experience\nBachelor's degree\nExperience\n- Reduced costs by 20%",
            job
        )

        self.assertGreater(with_match["ats_score"], without_match["ats_score"])
        self.assertEqual(with_match["skill_gap"]["missing_skills"], [])
        self.assertGreater(with_match["ats_breakdown"]["skills"], without_match["ats_breakdown"]["skills"])
        self.assertNotEqual(with_match["career_insights"]["career_trajectory"], without_match["career_insights"]["career_trajectory"])

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_resume_with_gemini_json_decode_error(self, mock_gen_model):
        mock_response = MagicMock()
        mock_response.text = "invalid json string"
        
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_model_instance

        with patch('app.GEMINI_API_KEY', 'dummy_key'):
            res = app.analyze_resume_with_gemini("resume text", "Python developer with SQL")
            self.assertIn("ats_score", res)
            self.assertIn("resume_evidence", res)

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_resume_with_gemini_api_exception(self, mock_gen_model):
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.side_effect = Exception("API connection timed out")
        mock_gen_model.return_value = mock_model_instance

        with patch('app.GEMINI_API_KEY', 'dummy_key'):
            res = app.analyze_resume_with_gemini("resume text", "Python developer with SQL")
            self.assertIn("ats_score", res)
            self.assertIn("skill_gap", res)

    def test_same_resume_three_job_descriptions_changes_all_match_modules(self):
        resume = "Alex Doe\nSkills\nPython Flask SQL\nProjects\nBuilt Flask API with SQL\nEducation\nBachelor degree"
        analyses = [app.generate_evidence_analysis(resume, jd) for jd in (
            "AI Engineer required Python machine learning AWS",
            "Java Backend Developer required Java Spring SQL 2 years",
            "Frontend Developer required JavaScript React CSS",
        )]
        self.assertEqual(len({item["ats_score"] for item in analyses}), 3)
        self.assertEqual(len({item["ats_breakdown"]["keywords"] for item in analyses}), 3)
        self.assertGreater(len({item["ats_breakdown"]["experience"] for item in analyses}), 1)
        self.assertEqual(len({str(item["skill_gap"]) for item in analyses}), 3)
        self.assertEqual(len({str(item["interview_questions"]) for item in analyses}), 3)
        self.assertEqual(len({str(item["improvements"]) for item in analyses}), 3)
        self.assertEqual(len({item["ats_breakdown"]["formatting"] for item in analyses}), 1)

    def test_different_resumes_same_job_change_evidence(self):
        job = "Python Flask SQL developer"
        first = app.generate_evidence_analysis("Skills\nPython Flask\nProjects\nBuilt API", job)
        second = app.generate_evidence_analysis("Skills\nJava React\nProjects\nBuilt UI", job)
        self.assertNotEqual(first["ats_score"], second["ats_score"])
        self.assertNotEqual(first["skill_gap"], second["skill_gap"])

    def test_internships_and_projects_are_relevant_experience(self):
        result = app.generate_evidence_analysis(
            "Education\nBachelor degree\nInternship\nPython developer intern\nProjects\nBuilt Python Flask app\nCreated SQL dashboard",
            "Python Flask SQL developer with 2 years experience"
        )
        self.assertGreater(result["ats_breakdown"]["experience"], 0)
        self.assertTrue(any("internship" in item.lower() for item in result["career_insights"]["strengths"]))

    def test_multiple_required_and_missing_skills_are_listed(self):
        result = app.generate_evidence_analysis("Skills\nPython\nProjects\nPython script", "Required Python, Docker, AWS, Kubernetes and PostgreSQL")
        self.assertEqual(len(result["skill_gap"]["matched_skills"]), 1)
        self.assertGreaterEqual(len(result["skill_gap"]["missing_skills"]), 3)
        self.assertTrue(all(item["status"] == "missing" for item in result["skill_gap"]["missing_skills"]))

    def test_score_is_derived_from_displayed_breakdown(self):
        result = app.generate_evidence_analysis("Skills\nPython\nExperience\n2 years Python", "Required Python, 2 years experience")
        breakdown = result["ats_breakdown"]
        expected = round(breakdown["keywords"] * .30 + breakdown["skills"] * .30 + breakdown["experience"] * .20 + breakdown["education"] * .10 + breakdown["formatting"] * .10)
        self.assertEqual(result["ats_score"], expected)

    def test_poor_extraction_is_labeled(self):
        result = app.generate_evidence_analysis("x", "Required Python developer role")
        self.assertEqual(result["resume_evidence"]["extraction_confidence"], "low")
        self.assertIn("low", result["resume_evidence"]["extraction_confidence"])

    def test_short_job_description_is_rejected(self):
        result = app.generate_evidence_analysis("Skills\nPython", "AI")
        self.assertEqual(result["analysis_status"], "insufficient_job_description")
        self.assertIn("too short", result["error"].lower())

    def test_five_job_descriptions_change_requirement_modules(self):
        resume = """Alex Doe
Skills
Python Flask SQL Git HTML CSS JavaScript
Projects
Built a Flask REST API with SQL and created an HTML/CSS dashboard.
Experience
Python developer intern
Education
Bachelor's degree
"""
        job_descriptions = (
            "Python Developer with Python, Flask, REST API, SQL and Git.",
            "Java Developer with Java, Spring Boot, MySQL, Docker and AWS.",
            "Data Analyst with Python, SQL, Excel, Power BI and statistics.",
            "Frontend Developer with HTML, CSS, JavaScript, React and TypeScript.",
            "AI/ML Engineer with Python, machine learning, TensorFlow, NLP and deep learning.",
        )
        results = [app.generate_evidence_analysis(resume, job) for job in job_descriptions]
        self.assertEqual(len({result["ats_score"] for result in results}), 5)
        self.assertEqual(len({str(result["keyword_match"]) for result in results}), 5)
        self.assertEqual(len({str(result["skill_gap"]) for result in results}), 5)
        self.assertEqual(len({str(result["interview_questions"]) for result in results}), 5)
        self.assertEqual(len({str(result["career_insights"]) for result in results}), 5)
        self.assertEqual(len({result["ats_breakdown"]["formatting"] for result in results}), 1)

    def test_keyword_evidence_and_missing_skills_are_from_jd(self):
        result = app.generate_evidence_analysis("Skills\nPython\nProjects\nPython script", "Required Python, Docker, AWS")
        self.assertEqual([item["name"] for item in result["keyword_match"]["matched_required"]], ["Python"])
        self.assertEqual({item["name"] for item in result["keyword_match"]["missing_required"]}, {"Docker", "AWS"})
        self.assertEqual({item["name"] for item in result["skill_gap"]["missing_skills"]}, {"Docker", "AWS"})

    def test_education_score_is_neutral_only_when_jd_omits_education(self):
        missing = app.generate_evidence_analysis("Skills\nPython", "Python developer with SQL")
        unsupported = app.generate_evidence_analysis("Skills\nPython", "Python developer with SQL and a master's degree")
        supported = app.generate_evidence_analysis("Skills\nPython\nEducation\nMaster's degree", "Python developer with SQL and a master's degree")
        self.assertEqual(missing["ats_breakdown"]["education"], 50)
        self.assertEqual(unsupported["ats_breakdown"]["education"], 0)
        self.assertEqual(supported["ats_breakdown"]["education"], 100)

    def test_index_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_analyze_route_no_resume(self):
        response = self.client.post('/analyze', data={'job_description': 'Software Engineer'})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "No resume file provided")

    def test_analyze_route_empty_filename(self):
        response = self.client.post('/analyze', data={
            'resume': (io.BytesIO(b""), ''),
            'job_description': 'Software Engineer'
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "No file selected")

    def test_analyze_route_empty_job_description(self):
        response = self.client.post('/analyze', data={
            'resume': (io.BytesIO(b"dummy pdf content"), 'resume.pdf'),
            'job_description': ''
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Job description is required")

    def test_analyze_route_invalid_file_type(self):
        response = self.client.post('/analyze', data={
            'resume': (io.BytesIO(b"dummy text content"), 'resume.txt'),
            'job_description': 'Software Engineer'
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Invalid file type. Only PDF files are allowed.")

    @patch('app.extract_text_from_pdf')
    @patch('app.analyze_resume_with_gemini')
    def test_analyze_route_success(self, mock_analyze, mock_extract):
        mock_extract.return_value = "Resume content extracted"
        mock_analyze.return_value = {
            "ats_score": 90,
            "ats_breakdown": {"keywords": 90, "formatting": 90, "experience": 90, "education": 90, "skills": 90},
            "improvements": [],
            "interview_questions": [],
            "skill_gap": {"matched_skills": [], "missing_skills": []},
            "career_insights": {"role_fit": 90, "strengths": [], "growth_areas": [], "career_trajectory": "", "salary_context": ""}
        }

        # Mock werkzeug file saving
        with patch('werkzeug.datastructures.FileStorage.save') as mock_save:
            response = self.client.post('/analyze', data={
                'resume': (io.BytesIO(b"dummy pdf content"), 'resume.pdf'),
                'job_description': 'Software Engineer'
            })
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['ats_score'], 90)
            mock_save.assert_called_once()

    @patch('app.extract_text_from_pdf')
    def test_analyze_route_extraction_failure(self, mock_extract):
        mock_extract.return_value = None

        with patch('werkzeug.datastructures.FileStorage.save'):
            response = self.client.post('/analyze', data={
                'resume': (io.BytesIO(b"dummy pdf content"), 'resume.pdf'),
                'job_description': 'Software Engineer'
            })
            self.assertEqual(response.status_code, 500)
            data = json.loads(response.data)
            self.assertIn("Could not extract text from the PDF", data['error'])

if __name__ == '__main__':
    unittest.main()
