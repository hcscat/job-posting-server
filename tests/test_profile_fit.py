from __future__ import annotations

import unittest
from types import SimpleNamespace

from job_harvest.profile_fit import attach_profile_fit, assess_profile_fit


class ProfileFitTest(unittest.TestCase):
    def test_assess_profile_fit_scores_enterprise_java_job_high(self) -> None:
        job = SimpleNamespace(
            title="Java Spring 업무 시스템 개발자",
            search_title="Java Spring 업무 시스템 개발자",
            page_title="공공 백오피스 개발",
            summary="공공 백오피스 운영개발 포지션",
            description="Java, Spring, MyBatis 기반 관리자 화면 및 업무 시스템 개발",
            ai_summary="Java Spring 기반 백오피스 운영개발",
            ai_relevance_reason="공공, 백오피스, 운영개발, Oracle 경험과 일치",
            company="Example SI",
            location="서울",
            employment_type="정규직",
            experience_level="3년 이상",
            education_level="무관",
            date_posted="today",
            valid_through="",
            ai_job_family="backend",
            ai_seniority="mid",
            ai_work_model="onsite",
            tags=["공공", "업무 시스템"],
            ai_tech_stack=["Java", "Spring", "MyBatis", "Oracle"],
            ai_requirements=["Java", "Spring", "업무 시스템"],
            ai_responsibilities=["백오피스 운영개발", "관리자 화면 개발"],
            ai_benefits=["유연근무"],
        )

        assessment = assess_profile_fit(job)
        self.assertGreaterEqual(assessment.score, 50)
        self.assertIn(assessment.level, {"high", "medium"})
        self.assertTrue(assessment.reasons)
        self.assertIn("Java", assessment.highlights)

    def test_assess_profile_fit_penalizes_non_matching_data_job(self) -> None:
        job = SimpleNamespace(
            title="Data Scientist",
            search_title="ML Researcher",
            page_title="AI Research",
            summary="머신러닝 모델 연구 및 데이터 분석",
            description="Python 기반 AI 모델 연구",
            ai_summary="머신러닝 리서치 포지션",
            ai_relevance_reason="데이터 사이언스와 AI 리서치 중심",
            company="ML Lab",
            location="서울",
            employment_type="정규직",
            experience_level="무관",
            education_level="석사 이상",
            date_posted="today",
            valid_through="",
            ai_job_family="data",
            ai_seniority="mid",
            ai_work_model="hybrid",
            tags=["AI", "ML"],
            ai_tech_stack=["Python", "TensorFlow"],
            ai_requirements=["머신러닝", "Python"],
            ai_responsibilities=["모델 연구"],
            ai_benefits=["원격근무"],
        )

        assessment = assess_profile_fit(job)
        self.assertLess(assessment.score, 50)
        self.assertIn(assessment.level, {"low", "none"})
        self.assertTrue(assessment.cautions)

    def test_attach_profile_fit_sets_runtime_fields(self) -> None:
        job = SimpleNamespace(
            title="SAP UI5 운영개발",
            search_title="SAP UI5 운영개발",
            page_title="Fiori 운영",
            summary="SAP UI5/Fiori 기반 운영개발",
            description="JavaScript와 SAP UI5로 관리자 화면을 유지보수",
            ai_summary="SAP UI5/Fiori 운영개발 포지션",
            ai_relevance_reason="SAP UI5, 운영개발, 관리자 화면 경험과 직접 연결",
            company="Enterprise App Co",
            location="판교",
            employment_type="정규직",
            experience_level="5년 이상",
            education_level="무관",
            date_posted="today",
            valid_through="",
            ai_job_family="frontend",
            ai_seniority="mid",
            ai_work_model="hybrid",
            tags=["운영개발"],
            ai_tech_stack=["JavaScript", "SAP UI5", "Fiori"],
            ai_requirements=["SAP UI5", "JavaScript"],
            ai_responsibilities=["운영개발"],
            ai_benefits=["유연근무"],
        )

        assessment = attach_profile_fit(job)
        self.assertEqual(job.profile_fit_score, assessment.score)
        self.assertEqual(job.profile_fit_level, assessment.level)
        self.assertEqual(job.profile_fit_reasons, assessment.reasons)
        self.assertEqual(job.profile_fit_highlights, assessment.highlights)


if __name__ == "__main__":
    unittest.main()
