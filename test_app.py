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
            res = app.analyze_resume_with_gemini("resume text", "job description")
            self.assertEqual(res["ats_score"], 85)
            self.assertEqual(res["ats_breakdown"]["keywords"], 80)

    def test_analyze_resume_with_gemini_no_api_key(self):
        with patch('app.GEMINI_API_KEY', ''):
            res = app.analyze_resume_with_gemini("resume text", "job description")
            self.assertIn("error", res)
            self.assertIn("Gemini API key is not configured", res["error"])

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_resume_with_gemini_json_decode_error(self, mock_gen_model):
        mock_response = MagicMock()
        mock_response.text = "invalid json string"
        
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_gen_model.return_value = mock_model_instance

        with patch('app.GEMINI_API_KEY', 'dummy_key'):
            res = app.analyze_resume_with_gemini("resume text", "job description")
            self.assertIn("error", res)
            self.assertIn("Failed to parse AI response", res["error"])

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_resume_with_gemini_api_exception(self, mock_gen_model):
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.side_effect = Exception("API connection timed out")
        mock_gen_model.return_value = mock_model_instance

        with patch('app.GEMINI_API_KEY', 'dummy_key'):
            res = app.analyze_resume_with_gemini("resume text", "job description")
            self.assertIn("error", res)
            self.assertIn("Failed to analyze resume", res["error"])

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
