"""
Seed Script — SmartRecruit Platform
Populates the database with realistic, diverse demo data across
multiple industries, roles, pipeline stages, and interactions.

Usage:  python3 seed_db.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL
from models import (
    Application, ApplicationStatus, Base, CandidateProfile,
    DirectOutreach, EmployerProfile, JobPost, Notification,
    NotificationType, OutreachMessage, OutreachStatus,
    Rating, RatingTarget, User, UserRole,
)
from services.vector_search import ensure_collection, upsert_candidate_vector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _hash(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


def _dt(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATES  (20 diverse profiles across tech, finance, healthcare, creative)
# ─────────────────────────────────────────────────────────────────────────────

CANDIDATES = [
    # ── Technology ──
    {
        "email": "alice.chen@example.com", "pw": "password123",
        "full_name": "Alice Chen", "age": 29, "location": "San Francisco, CA",
        "title": "Senior Python Engineer", "profession": "Software Engineering",
        "skills": "Python, FastAPI, SQLAlchemy, PostgreSQL, Docker, Redis, AWS Lambda, Celery",
        "life_skills": "Leadership, Mentoring, Problem Solving",
        "experience_years": 7, "education": "BSc Computer Science — UC Berkeley, 2017",
        "certifications": "AWS Solutions Architect Associate",
        "languages": "English, Mandarin", "expected_salary": "$130k–$160k",
        "job_type_pref": "FULL_TIME", "is_open_to_work": True,
        "linkedin_url": "https://linkedin.com/in/alicechen",
        "bio": "Senior backend engineer passionate about building scalable distributed systems. 7 years of Python expertise, led teams of up to 8 engineers. Active open-source contributor.",
        "resume": "Alice Chen is a senior backend engineer with 7 years of Python experience. She has built high-throughput APIs serving millions of requests using FastAPI and SQLAlchemy on AWS. Led migration from monolith to microservices architecture cutting latency by 40%. Active open-source contributor and tech lead for a team of 8 engineers.",
    },
    {
        "email": "bob.martinez@example.com", "pw": "password123",
        "full_name": "Bob Martinez", "age": 32, "location": "New York, NY",
        "title": "Machine Learning Engineer", "profession": "Machine Learning",
        "skills": "Python, PyTorch, TensorFlow, scikit-learn, MLflow, Spark, Kubernetes, Hugging Face",
        "life_skills": "Research, Analytical Thinking, Communication",
        "experience_years": 5, "education": "MSc Data Science — Columbia University, 2019",
        "certifications": "Google Professional ML Engineer",
        "languages": "English, Spanish", "expected_salary": "$145k–$175k",
        "job_type_pref": "FULL_TIME", "is_open_to_work": True,
        "bio": "ML engineer specialising in NLP and recommendation systems. Published 3 papers on transformer fine-tuning. Built recommendation engine serving 5M users.",
        "resume": "Bob Martinez specialises in end-to-end ML pipelines. Built recommendation systems and NLP classifiers using PyTorch and Hugging Face transformers. Deployed models with Kubernetes and BentoML serving 5M daily users. 3 published papers on efficient transformer architectures.",
    },
    {
        "email": "carol.kim@example.com", "pw": "password123",
        "full_name": "Carol Kim", "age": 26, "location": "Austin, TX",
        "title": "Full-Stack Developer", "profession": "Web Development",
        "skills": "React, TypeScript, Node.js, GraphQL, Next.js, PostgreSQL, Tailwind CSS, AWS",
        "life_skills": "Creativity, Collaboration, Fast Learner",
        "experience_years": 4, "education": "BSc Software Engineering — UT Austin, 2020",
        "certifications": "Meta Frontend Developer",
        "languages": "English, Korean", "expected_salary": "$95k–$120k",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "Full-stack developer who loves crafting beautiful, performant web apps. Specialise in React ecosystem and GraphQL APIs. 6 shipped products, 2 with 100k+ users.",
        "resume": "Carol Kim builds modern full-stack web applications with React and Next.js on the frontend and Node.js/GraphQL on the backend. Shipped 6 production products, 2 reaching 100k+ MAU. Strong focus on performance, accessibility and TypeScript type safety.",
    },
    {
        "email": "dave.okonkwo@example.com", "pw": "password123",
        "full_name": "Dave Okonkwo", "age": 35, "location": "Seattle, WA",
        "title": "Senior DevOps & Platform Engineer", "profession": "DevOps",
        "skills": "Kubernetes, Terraform, Helm, AWS, GCP, Prometheus, Grafana, ArgoCD, Python, Go",
        "life_skills": "Reliability Engineering, Documentation, Mentoring",
        "experience_years": 9, "education": "BSc Computer Engineering — University of Lagos, 2015",
        "certifications": "CKA (Certified Kubernetes Administrator), AWS DevOps Professional",
        "languages": "English, Yoruba", "expected_salary": "$150k–$180k",
        "job_type_pref": "HYBRID", "is_open_to_work": False,
        "bio": "Platform engineer with 9 years building cloud-native infrastructure. Designed multi-cluster Kubernetes setups for 300+ tenants. Reduced deployment time from 45min to 4min via GitOps.",
        "resume": "Dave Okonkwo designs and operates multi-tenant Kubernetes platforms on AWS and GCP. Implemented GitOps with ArgoCD reducing deployments from 45 to 4 minutes. Built observability stacks with Prometheus, Grafana and Loki tracking 500M+ events/day.",
    },
    {
        "email": "eva.rossi@example.com", "pw": "password123",
        "full_name": "Eva Rossi", "age": 30, "location": "Chicago, IL",
        "title": "Data Engineer & Analytics Lead", "profession": "Data Engineering",
        "skills": "Python, dbt, Apache Airflow, Snowflake, BigQuery, Kafka, Spark, Looker, SQL",
        "life_skills": "Data Storytelling, Attention to Detail, Stakeholder Management",
        "experience_years": 6, "education": "MSc Statistics — University of Milan, 2018",
        "certifications": "dbt Certified Developer, Databricks Associate",
        "languages": "English, Italian, French", "expected_salary": "$120k–$145k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Data engineer who turns messy pipelines into reliable analytics infrastructure. Led migration from legacy ETL to modern lakehouse serving 50 BI users.",
        "resume": "Eva Rossi designs and operates modern data platforms. Builds ELT pipelines with dbt and Airflow processing 2TB/day. Migrated legacy ETL to cloud lakehouse on Snowflake cutting pipeline costs by 60% and latency from 8h to 45min.",
    },
    {
        "email": "frank.osei@example.com", "pw": "password123",
        "full_name": "Frank Osei", "age": 27, "location": "Miami, FL",
        "title": "Mobile Developer (iOS & Android)", "profession": "Mobile Development",
        "skills": "Swift, Kotlin, Flutter, Dart, Firebase, REST APIs, SQLite, Figma",
        "life_skills": "User Empathy, Creativity, Attention to Detail",
        "experience_years": 5, "education": "BSc Computer Science — Florida International University, 2019",
        "certifications": "Google Associate Android Developer",
        "languages": "English, Twi", "expected_salary": "$100k–$125k",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "Mobile developer who has shipped 8 apps with combined 500k+ downloads. Expert in Flutter for cross-platform and native Swift/Kotlin for performance-critical features.",
        "resume": "Frank Osei develops cross-platform and native mobile applications. Published 8 apps on App Store and Google Play with 500k+ combined downloads. Specialise in Flutter for cross-platform efficiency and Swift/Kotlin for native performance.",
    },
    {
        "email": "grace.nakamura@example.com", "pw": "password123",
        "full_name": "Grace Nakamura", "age": 34, "location": "Washington DC",
        "title": "Cybersecurity Engineer", "profession": "Cybersecurity",
        "skills": "Penetration Testing, SIEM, SAST, DAST, Python, Burp Suite, AWS Security, Splunk, Zero Trust",
        "life_skills": "Critical Thinking, Integrity, Continuous Learning",
        "experience_years": 8, "education": "BSc Information Security — Carnegie Mellon, 2016",
        "certifications": "OSCP, CISSP, AWS Security Specialty",
        "languages": "English, Japanese", "expected_salary": "$140k–$165k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Cybersecurity engineer who has secured 15+ startups through SOC 2 Type II. Specialist in AppSec, cloud security posture and penetration testing.",
        "resume": "Grace Nakamura specialises in application and cloud security. Led security programmes at 15 startups achieving SOC 2 Type II compliance. Conducts penetration tests, designs zero-trust architectures, and runs SAST/DAST pipelines.",
    },
    {
        "email": "henry.obi@example.com", "pw": "password123",
        "full_name": "Henry Obi", "age": 31, "location": "Boston, MA",
        "title": "Senior Product Manager", "profession": "Product Management",
        "skills": "Product Strategy, Roadmapping, Agile, Scrum, Figma, SQL, Amplitude, A/B Testing",
        "life_skills": "Strategic Thinking, Stakeholder Management, Communication",
        "experience_years": 6, "education": "MBA — Harvard Business School, 2020",
        "certifications": "Certified Scrum Product Owner",
        "languages": "English, Igbo, French", "expected_salary": "$135k–$160k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Product manager who grew a PLG developer tool from 0 to 12k paying customers. Obsessed with user research, data-driven decisions and shipping fast.",
        "resume": "Henry Obi is a product manager with B2B SaaS expertise. Grew a PLG developer tools product from 0 to 12k paying customers in 18 months. Runs weekly user research sessions, ships bi-weekly releases using Scrum.",
    },
    # ── Finance & Business ──
    {
        "email": "isabella.chen@example.com", "pw": "password123",
        "full_name": "Isabella Torres", "age": 28, "location": "New York, NY",
        "title": "Quantitative Analyst", "profession": "Finance",
        "skills": "Python, R, SQL, Excel, Bloomberg, Monte Carlo Simulation, Risk Modelling, Statistics",
        "life_skills": "Precision, Analytical Thinking, Deadline Management",
        "experience_years": 4, "education": "MSc Financial Mathematics — NYU Courant, 2020",
        "certifications": "CFA Level 2",
        "languages": "English, Spanish, Portuguese", "expected_salary": "$110k–$140k",
        "job_type_pref": "FULL_TIME", "is_open_to_work": True,
        "bio": "Quant analyst building risk models for derivatives trading. 4 years at a top-tier hedge fund building pricing models and backtesting frameworks.",
        "resume": "Isabella Torres builds quantitative risk models and pricing frameworks for derivatives. 4 years at a hedge fund building Monte Carlo simulation engines in Python, backtesting systematic strategies, and producing daily risk reports for $2B AUM.",
    },
    {
        "email": "james.anderson@example.com", "pw": "password123",
        "full_name": "James Anderson", "age": 38, "location": "London, UK",
        "title": "Senior Business Analyst", "profession": "Business Analysis",
        "skills": "Requirements Analysis, BPMN, Power BI, SQL, Jira, Stakeholder Management, Six Sigma",
        "life_skills": "Communication, Problem Solving, Leadership",
        "experience_years": 12, "education": "BSc Business Information Systems — LSE, 2012",
        "certifications": "CBAP (Certified Business Analysis Professional), Six Sigma Black Belt",
        "languages": "English, French", "expected_salary": "£75k–£90k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Senior BA with 12 years bridging the gap between business needs and technical solutions. Led digital transformation projects saving £4M in operational costs.",
        "resume": "James Anderson is a senior business analyst with 12 years experience in financial services and insurance. Led 3 large-scale digital transformation programmes reducing operational costs by £4M. Expert in BPMN process modelling and Power BI dashboards.",
    },
    # ── Healthcare ──
    {
        "email": "sarah.johnson@example.com", "pw": "password123",
        "full_name": "Sarah Johnson", "age": 33, "location": "Houston, TX",
        "title": "Healthcare Data Scientist", "profession": "Data Science",
        "skills": "Python, R, SQL, TensorFlow, Clinical NLP, FHIR, HL7, scikit-learn, Tableau",
        "life_skills": "Patient Empathy, Precision, Research",
        "experience_years": 7, "education": "PhD Biomedical Informatics — UTHealth, 2017",
        "certifications": "CPHIMS (Certified Health Informatics Professional)",
        "languages": "English", "expected_salary": "$125k–$150k",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "Healthcare data scientist applying ML to improve patient outcomes. Built a sepsis prediction model now used in 8 ICUs reducing mortality by 18%.",
        "resume": "Sarah Johnson applies machine learning to clinical data to improve patient outcomes. PhD in Biomedical Informatics. Built an early sepsis detection model deployed across 8 ICUs reducing mortality rate by 18%. Expert in clinical NLP, FHIR data standards and EHR analytics.",
    },
    # ── Creative & Marketing ──
    {
        "email": "miguel.rodrigues@example.com", "pw": "password123",
        "full_name": "Miguel Rodrigues", "age": 25, "location": "Lisbon, Portugal",
        "title": "UX/UI Designer", "profession": "Design",
        "skills": "Figma, Adobe XD, Sketch, Principle, User Research, Prototyping, Design Systems, CSS",
        "life_skills": "Empathy, Visual Thinking, Attention to Detail",
        "experience_years": 3, "education": "BA Design — IADE Porto, 2021",
        "certifications": "Google UX Design Certificate",
        "languages": "Portuguese, English, Spanish", "expected_salary": "€45k–€60k",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "UX designer turning complex user problems into clear, delightful experiences. Redesigned a fintech onboarding flow increasing completion rate from 34% to 72%.",
        "resume": "Miguel Rodrigues is a UX/UI designer specialising in fintech and SaaS products. Redesigned a challenger bank onboarding flow lifting completion from 34% to 72%. Maintains a design system used by 12 engineers. Expert in user research and Figma prototyping.",
    },
    {
        "email": "nina.petrov@example.com", "pw": "password123",
        "full_name": "Nina Petrov", "age": 29, "location": "Berlin, Germany",
        "title": "Growth Marketing Manager", "profession": "Marketing",
        "skills": "SEO, SEM, Google Ads, Meta Ads, HubSpot, Mixpanel, Content Strategy, A/B Testing, SQL",
        "life_skills": "Data-Driven Thinking, Creativity, Communication",
        "experience_years": 5, "education": "BSc Marketing — WHU Business School, 2019",
        "certifications": "Google Analytics Certified, HubSpot Inbound Marketing",
        "languages": "German, English, Russian", "expected_salary": "€65k–€80k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Growth marketer who scaled a B2B SaaS from €200k to €2.5M ARR in 14 months through data-driven demand generation and PLG strategies.",
        "resume": "Nina Petrov is a growth marketer specialising in B2B SaaS. Scaled a startup from €200k to €2.5M ARR in 14 months using paid acquisition, SEO and product-led growth. Expert in attribution modelling and full-funnel optimisation.",
    },
    # ── Engineering ──
    {
        "email": "liam.oconnor@example.com", "pw": "password123",
        "full_name": "Liam O'Connor", "age": 36, "location": "Dublin, Ireland",
        "title": "Embedded Systems Engineer", "profession": "Embedded Engineering",
        "skills": "C, C++, RTOS, ARM Cortex, FPGA, VHDL, CAN Bus, SPI, I2C, Python, JTAG",
        "life_skills": "Precision, Problem Solving, Documentation",
        "experience_years": 10, "education": "MEng Electronic Engineering — Trinity College Dublin, 2014",
        "certifications": "Functional Safety (ISO 26262)",
        "languages": "English, Irish", "expected_salary": "€95k–€115k",
        "job_type_pref": "ONSITE", "is_open_to_work": True,
        "bio": "Embedded engineer with 10 years in automotive and IoT. Designed safety-critical firmware for ADAS systems now in 2M+ vehicles.",
        "resume": "Liam O'Connor designs safety-critical embedded firmware for automotive ADAS systems. 10 years experience with ARM Cortex MCUs, RTOS and CAN Bus. Led firmware team delivering ISO 26262 ASIL-B certified software deployed in 2M+ vehicles.",
    },
    # ── Education & Research ──
    {
        "email": "amara.diallo@example.com", "pw": "password123",
        "full_name": "Amara Diallo", "age": 31, "location": "Toronto, Canada",
        "title": "AI Research Scientist", "profession": "Research",
        "skills": "Python, PyTorch, JAX, Research Design, NLP, Computer Vision, LaTeX, Git",
        "life_skills": "Curiosity, Rigour, Collaboration",
        "experience_years": 6, "education": "PhD Computer Science (AI) — University of Toronto, 2020",
        "certifications": "NeurIPS 2022 Top Reviewer",
        "languages": "English, French, Wolof", "expected_salary": "CA$130k–$160k",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "AI researcher focused on efficient language model training and multilingual NLP. 12 publications including 2 NeurIPS oral papers.",
        "resume": "Amara Diallo is an AI research scientist with expertise in language model efficiency and multilingual NLP. PhD from University of Toronto. 12 peer-reviewed publications including 2 NeurIPS oral presentations. Currently working on parameter-efficient fine-tuning methods.",
    },
    # ── Operations ──
    {
        "email": "rachel.park@example.com", "pw": "password123",
        "full_name": "Rachel Park", "age": 27, "location": "Los Angeles, CA",
        "title": "Operations Manager", "profession": "Operations",
        "skills": "Process Optimisation, ERP Systems, Supply Chain, Six Sigma, Tableau, SQL, JIRA, OKRs",
        "life_skills": "Organisation, Leadership, Communication",
        "experience_years": 4, "education": "BSc Industrial Engineering — UCLA, 2020",
        "certifications": "Six Sigma Green Belt, PMP",
        "languages": "English, Korean", "expected_salary": "$85k–$105k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Operations manager who streamlined logistics for a 200-person e-commerce company reducing fulfilment time by 35% and saving $1.2M annually.",
        "resume": "Rachel Park optimises business operations and supply chains. At a 200-person e-commerce company, redesigned fulfilment workflows reducing processing time from 48h to 31h and saving $1.2M/year. Expert in ERP implementation, OKR frameworks and Six Sigma DMAIC.",
    },
    # ── Legal & Compliance ──
    {
        "email": "omar.hassan@example.com", "pw": "password123",
        "full_name": "Omar Hassan", "age": 40, "location": "Dubai, UAE",
        "title": "Legal & Compliance Manager", "profession": "Legal",
        "skills": "Contract Law, GDPR, AML, Regulatory Compliance, Legal Research, Risk Assessment, Negotiation",
        "life_skills": "Attention to Detail, Discretion, Analytical Thinking",
        "experience_years": 14, "education": "LLM International Business Law — King's College London, 2012",
        "certifications": "CAMS (Certified Anti-Money Laundering Specialist)",
        "languages": "English, Arabic, French", "expected_salary": "AED 45k–60k/month",
        "job_type_pref": "ONSITE", "is_open_to_work": True,
        "bio": "Senior legal and compliance manager with 14 years in financial services and fintech across MENA. Specialise in AML frameworks and cross-border regulatory compliance.",
        "resume": "Omar Hassan is a senior legal and compliance professional with 14 years in financial services across the MENA region. Built AML compliance frameworks at 3 banks, navigated multi-jurisdictional regulatory requirements, and led a team of 6 compliance officers.",
    },
    # ── Healthcare Tech ──
    {
        "email": "priya.sharma@example.com", "pw": "password123",
        "full_name": "Priya Sharma", "age": 28, "location": "Bangalore, India",
        "title": "Backend Engineer (Java & Spring)", "profession": "Software Engineering",
        "skills": "Java, Spring Boot, Microservices, Kafka, PostgreSQL, Docker, Kubernetes, Redis",
        "life_skills": "Collaboration, Problem Solving, Quick Learner",
        "experience_years": 4, "education": "BTech Computer Science — IIT Bombay, 2020",
        "certifications": "Oracle Java SE Professional",
        "languages": "English, Hindi, Kannada", "expected_salary": "₹25L–₹35L",
        "job_type_pref": "REMOTE", "is_open_to_work": True,
        "bio": "Backend engineer building high-availability microservices in Java. Designed a Kafka-based event streaming system processing 50M events/day at a healthcare tech startup.",
        "resume": "Priya Sharma builds scalable microservices with Java and Spring Boot. Designed a Kafka event streaming architecture processing 50M healthcare events per day with 99.99% uptime. Expert in distributed systems design and PostgreSQL query optimisation.",
    },
    # ── Retail & Customer Success ──
    {
        "email": "tom.whitfield@example.com", "pw": "password123",
        "full_name": "Tom Whitfield", "age": 30, "location": "Manchester, UK",
        "title": "Customer Success Manager", "profession": "Customer Success",
        "skills": "Salesforce, HubSpot, Gainsight, NPS, Onboarding, Churn Analysis, SQL, Communication",
        "life_skills": "Empathy, Communication, Relationship Building",
        "experience_years": 5, "education": "BA Business Management — University of Manchester, 2019",
        "certifications": "Salesforce Certified Administrator",
        "languages": "English", "expected_salary": "£50k–£65k",
        "job_type_pref": "HYBRID", "is_open_to_work": True,
        "bio": "Customer success manager who reduced churn from 8% to 2.3% at a B2B SaaS company managing a £4M ARR portfolio. Love turning unhappy customers into advocates.",
        "resume": "Tom Whitfield manages enterprise customer success for B2B SaaS products. Reduced monthly churn from 8% to 2.3% through proactive health scoring and a structured QBR programme. Manages a £4M ARR portfolio of 120 accounts.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYERS  (10 companies across different industries)
# ─────────────────────────────────────────────────────────────────────────────

EMPLOYERS = [
    {
        "email": "hr@techcorp.com", "pw": "employer123",
        "company_name": "TechCorp Solutions", "industry": "Technology",
        "company_size": "101-500 employees", "founded_year": 2014,
        "website": "https://techcorp.io",
        "description": "TechCorp builds enterprise SaaS tools for the global logistics industry. Remote-first company of 200 engineers committed to open-source and developer experience.",
        "work_environment": "Fully remote with optional hubs in SF and NYC. Async-first communication. Monthly team socials, annual all-hands in person. Engineering-led culture where every voice matters.",
        "benefits": "Competitive salary, equity, $2,000 home office budget, unlimited PTO, full health/dental/vision, $2k/year learning budget, 401k with 4% match",
        "work_mode": "REMOTE", "location": "Remote (US)",
        "contact_name": "Sarah Liu", "contact_phone": "+1 415 555 0101",
        "jobs": [
            {
                "title": "Senior Backend Engineer (Python)", "experience_min": 5,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "$120k–$160k",
                "location": "Remote (US)", "industry": "Technology",
                "skills": "Python, FastAPI, PostgreSQL, Redis, AWS, Docker, Celery",
                "description": "Join our core platform team and shape the backbone of our logistics SaaS. You'll design high-throughput async APIs, own performance optimisation, and mentor junior engineers. We deploy 20+ times per week and move fast.",
            },
            {
                "title": "ML Engineer — Recommendations & Search", "experience_min": 4,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "$130k–$170k",
                "location": "Remote (US)", "industry": "Technology",
                "skills": "Python, PyTorch, MLflow, Spark, Kubernetes, Feature Stores",
                "description": "Build and maintain AI-powered shipment routing recommendations used by Fortune 500 clients. You'll own the full ML lifecycle from feature engineering to production serving at scale.",
            },
            {
                "title": "DevOps Engineer", "experience_min": 4,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "$110k–$145k",
                "location": "Remote (US)", "industry": "Technology",
                "skills": "Kubernetes, Terraform, AWS, ArgoCD, Prometheus, Python",
                "description": "Own our cloud infrastructure serving 300+ enterprise clients. Automate everything, champion reliability, and help engineering teams ship faster and safer.",
            },
        ],
    },
    {
        "email": "talent@fintech.io", "pw": "employer123",
        "company_name": "FinTech Innovations", "industry": "Finance",
        "company_size": "51-200 employees", "founded_year": 2018,
        "website": "https://fintechinnovations.com",
        "description": "Challenger bank offering instant lending and embedded finance powered by real-time risk scoring. Regulated in EU and UK. Series B, $45M raised.",
        "work_environment": "Hybrid (London HQ + remote). Fast-paced startup energy, flat hierarchy. Weekly all-hands, monthly team lunches, quarterly offsites. Everyone ships code, including PMs.",
        "benefits": "Competitive salary + equity, flexible hybrid working, private health insurance, 25 days holiday + bank holidays, £1,500 learning budget, cycle-to-work scheme",
        "work_mode": "HYBRID", "location": "London, UK",
        "contact_name": "Marcus Webb", "contact_phone": "+44 20 7946 0023",
        "jobs": [
            {
                "title": "Full-Stack Engineer — Customer Platform", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "£75k–£95k",
                "location": "London, UK", "industry": "Finance",
                "skills": "React, TypeScript, Node.js, GraphQL, PostgreSQL, AWS",
                "description": "Own the customer-facing web app used by 2M+ users. Implement new onboarding flows, build BFF GraphQL APIs, and ensure WCAG 2.1 accessibility. High autonomy, fast feedback loops.",
            },
            {
                "title": "Risk & Fraud Data Scientist", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "£80k–$100k",
                "location": "London, UK", "industry": "Finance",
                "skills": "Python, scikit-learn, SQL, Spark, Risk Modelling, Statistics",
                "description": "Build real-time fraud detection and credit scoring models that protect our customers and our balance sheet. Work with petabytes of transaction data and ship models to production weekly.",
            },
        ],
    },
    {
        "email": "recruiting@cloudbase.dev", "pw": "employer123",
        "company_name": "CloudBase Infrastructure", "industry": "Technology",
        "company_size": "11-50 employees", "founded_year": 2020,
        "website": "https://cloudbase.dev",
        "description": "Managed Kubernetes and observability-as-a-service for startups. VC-backed, growing rapidly. We power infrastructure for 400+ companies.",
        "work_environment": "Fully remote, globally distributed team across 12 timezones. Engineering-first culture. Every engineer owns their piece end-to-end. Weekly demos, open RFC process.",
        "benefits": "Top-of-market salary, significant equity, fully remote, $3k home office setup, $2k conference budget, unlimited PTO, comprehensive health insurance",
        "work_mode": "REMOTE", "location": "Remote (Global)",
        "contact_name": "Yuki Tanaka", "contact_phone": "+1 650 555 0187",
        "jobs": [
            {
                "title": "Platform Engineer — Kubernetes", "experience_min": 6,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "$140k–$180k",
                "location": "Remote (Global)", "industry": "Technology",
                "skills": "Kubernetes, Terraform, Helm, AWS, GCP, Prometheus, Go, Python",
                "description": "Design and run multi-tenant Kubernetes clusters for our 400+ customers. You'll own SLA commitments, automate toil away, and build the platform that thousands of engineers rely on daily.",
            },
            {
                "title": "Security Engineer", "experience_min": 5,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "$130k–$165k",
                "location": "Remote (Global)", "industry": "Technology",
                "skills": "Penetration Testing, AWS Security, SAST, DAST, Python, Zero Trust",
                "description": "Lead our security programme: threat modelling, penetration testing, SOC 2 Type II automation, and building a secure SDLC that developers love instead of fear.",
            },
        ],
    },
    {
        "email": "jobs@healthtech-ai.com", "pw": "employer123",
        "company_name": "MedAI Systems", "industry": "Healthcare",
        "company_size": "51-200 employees", "founded_year": 2019,
        "website": "https://medai.systems",
        "description": "MedAI builds clinical decision support tools using machine learning. Our sepsis prediction model is deployed across 50+ hospitals in the US and Europe.",
        "work_environment": "Mission-driven team where your work literally saves lives. Hybrid (Boston HQ). Collaborative research culture. Regular seminars with clinicians and domain experts.",
        "benefits": "Competitive salary, equity, full medical benefits, 20 days PTO + 10 sick days, $2k professional development, flexible hours",
        "work_mode": "HYBRID", "location": "Boston, MA",
        "contact_name": "Dr. Elena Vasquez",
        "jobs": [
            {
                "title": "Healthcare Data Scientist", "experience_min": 4,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "$120k–$150k",
                "location": "Boston, MA", "industry": "Healthcare",
                "skills": "Python, TensorFlow, Clinical NLP, FHIR, scikit-learn, SQL",
                "description": "Develop and validate ML models for clinical decision support. Work directly with physicians to understand clinical workflows and build tools that are actually used at the bedside.",
            },
            {
                "title": "Backend Engineer (Python / Healthcare APIs)", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "$110k–$135k",
                "location": "Boston, MA", "industry": "Healthcare",
                "skills": "Python, FastAPI, FHIR, HL7, PostgreSQL, Docker, AWS",
                "description": "Build FHIR-compliant APIs that integrate with major EHR systems (Epic, Cerner). You'll be the engineering bridge between ML models and clinical systems used by 50+ hospitals.",
            },
        ],
    },
    {
        "email": "people@designstudio.co", "pw": "employer123",
        "company_name": "Pixel & Craft Studio", "industry": "Design",
        "company_size": "11-50 employees", "founded_year": 2017,
        "website": "https://pixelandcraft.co",
        "description": "Award-winning product design studio working with Series A–C startups to define product strategy, UX and brand. Clients include fintech, healthtech and consumer apps.",
        "work_environment": "Creative, collaborative studio environment in Lisbon. Open plan office, weekly design critiques, monthly inspiration talks. Work with brilliant clients on meaningful problems.",
        "benefits": "Competitive salary, 25 days holiday, health insurance, equipment budget, access to premium design tools, Friday afternoons for personal projects",
        "work_mode": "HYBRID", "location": "Lisbon, Portugal",
        "contact_name": "Sofia Almeida",
        "jobs": [
            {
                "title": "Senior UX/UI Designer", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "€55k–€70k",
                "location": "Lisbon, Portugal", "industry": "Design",
                "skills": "Figma, User Research, Prototyping, Design Systems, CSS, Usability Testing",
                "description": "Lead design for 2–3 client projects simultaneously. From initial user research and strategy through to pixel-perfect Figma handoffs. You'll present directly to C-suite stakeholders.",
            },
        ],
    },
    {
        "email": "hr@growthagency.com", "pw": "employer123",
        "company_name": "Momentum Growth Agency", "industry": "Marketing",
        "company_size": "11-50 employees", "founded_year": 2016,
        "website": "https://momentumgrowth.agency",
        "description": "Performance marketing agency specialising in B2B SaaS. We've helped 80+ companies scale from seed to Series C using data-driven demand generation.",
        "work_environment": "Fast-paced, results-oriented agency culture. Remote-first with quarterly team meetups in Berlin. High autonomy, clear KPIs, quick feedback.",
        "benefits": "Salary + performance bonus, remote-first, 28 days holiday, learning budget, gym membership",
        "work_mode": "REMOTE", "location": "Berlin, Germany",
        "contact_name": "Kai Brandt",
        "jobs": [
            {
                "title": "Growth Marketing Manager (B2B SaaS)", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "€60k–€80k",
                "location": "Remote (Europe)", "industry": "Marketing",
                "skills": "SEO, SEM, Google Ads, HubSpot, Analytics, A/B Testing, Content Strategy, SQL",
                "description": "Own demand generation for 3 key client accounts. Build full-funnel campaigns, run rigorous A/B tests, and report on pipeline attribution. You'll have full budget ownership from day one.",
            },
        ],
    },
    {
        "email": "careers@legaltech.com", "pw": "employer123",
        "company_name": "LexPro Technologies", "industry": "Legal Tech",
        "company_size": "51-200 employees", "founded_year": 2015,
        "website": "https://lexpro.tech",
        "description": "LexPro builds contract lifecycle management software used by legal teams at 200+ enterprises globally. We reduce contract review time by 75% using NLP.",
        "work_environment": "Collaborative, mission-driven team. Offices in Dubai and Singapore. Flexible hybrid working, diverse international team of 25 nationalities.",
        "benefits": "Tax-free salary (Dubai), equity, health insurance, housing allowance (Dubai), 30 days annual leave, international relocation support",
        "work_mode": "HYBRID", "location": "Dubai, UAE",
        "contact_name": "Fatima Al-Rashid",
        "jobs": [
            {
                "title": "Legal & Compliance Manager", "experience_min": 8,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "AED 40k–55k/month",
                "location": "Dubai, UAE", "industry": "Legal Tech",
                "skills": "Contract Law, GDPR, AML, Regulatory Compliance, Risk Assessment, Negotiation",
                "description": "Lead our legal and compliance function across MENA and Asia-Pacific. Manage regulatory relationships, contract templates, vendor agreements and our GDPR compliance programme.",
            },
        ],
    },
    {
        "email": "talent@automaker.de", "pw": "employer123",
        "company_name": "Volt Automotive GmbH", "industry": "Automotive",
        "company_size": "501-1000 employees", "founded_year": 2012,
        "website": "https://voltautomotive.de",
        "description": "Volt is a Tier 1 automotive supplier developing next-generation ADAS firmware and EV powertrain control systems for major OEMs including BMW and Volkswagen.",
        "work_environment": "Engineering-first culture. Offices in Munich and Stuttgart. Collaborative R&D environment with cutting-edge lab facilities. Flexible hours, strong work-life balance.",
        "benefits": "Competitive German salary, company car, 30 days holiday, public transport subsidy, canteen, gym, excellent pension contribution",
        "work_mode": "ONSITE", "location": "Munich, Germany",
        "contact_name": "Klaus Bauer",
        "jobs": [
            {
                "title": "Senior Embedded Systems Engineer (ADAS)", "experience_min": 6,
                "job_type": "FULL_TIME", "work_mode": "ONSITE", "salary": "€90k–€115k",
                "location": "Munich, Germany", "industry": "Automotive",
                "skills": "C, C++, RTOS, ARM Cortex, CAN Bus, ISO 26262, AUTOSAR, Python",
                "description": "Design and validate safety-critical firmware for next-generation ADAS systems including lane keeping and emergency braking. Work directly with OEM partners on ASIL-B to ASIL-D requirements.",
            },
        ],
    },
    {
        "email": "hr@ecomlogistics.com", "pw": "employer123",
        "company_name": "SwiftShip Logistics", "industry": "E-commerce",
        "company_size": "201-500 employees", "founded_year": 2013,
        "website": "https://swiftship.com",
        "description": "SwiftShip is a tech-enabled 3PL logistics company processing 50,000 orders/day for 500+ e-commerce brands. We're the invisible engine behind fast delivery.",
        "work_environment": "Operations-driven, data-obsessed culture. LA HQ with warehouses across the US. Hybrid office schedule, strong team culture, regular company events.",
        "benefits": "Competitive salary, health benefits, 401k, PTO, employee discounts, quarterly team events",
        "work_mode": "HYBRID", "location": "Los Angeles, CA",
        "contact_name": "Derek Mills",
        "jobs": [
            {
                "title": "Operations Manager — Fulfilment", "experience_min": 3,
                "job_type": "FULL_TIME", "work_mode": "HYBRID", "salary": "$85k–$105k",
                "location": "Los Angeles, CA", "industry": "E-commerce",
                "skills": "Process Optimisation, Supply Chain, ERP, Six Sigma, Tableau, SQL",
                "description": "Lead operations for our LA fulfilment centre processing 8,000 orders/day. Drive efficiency initiatives, manage a team of 30 warehouse staff, and own KPIs including on-time dispatch rate and cost per order.",
            },
        ],
    },
    {
        "email": "jobs@aicorp.io", "pw": "employer123",
        "company_name": "Cognify AI Labs", "industry": "Technology",
        "company_size": "11-50 employees", "founded_year": 2022,
        "website": "https://cognifyai.io",
        "description": "Cognify is an early-stage AI research lab building next-generation multilingual language models. Spun out of University of Toronto AI lab, funded by top-tier VCs.",
        "work_environment": "Research-first culture. Work alongside world-class researchers. Fully remote. Publish your work. Strong emphasis on learning and scientific rigour.",
        "benefits": "Competitive research salary, equity, remote-first, conference travel budget, GPU compute access, publication bonus",
        "work_mode": "REMOTE", "location": "Remote (Global)",
        "contact_name": "Prof. Amara Diallo",
        "jobs": [
            {
                "title": "AI Research Scientist — NLP", "experience_min": 4,
                "job_type": "FULL_TIME", "work_mode": "REMOTE", "salary": "CA$140k–$180k",
                "location": "Remote (Global)", "industry": "Technology",
                "skills": "Python, PyTorch, JAX, NLP, Transformer Architectures, Research, LaTeX",
                "description": "Drive core research on multilingual language model training and efficient fine-tuning methods. Publish at top venues (NeurIPS, ACL, ICLR). Collaborate with a world-class team of 15 researchers.",
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_create_user(db: AsyncSession, email: str, pw: str, role: UserRole) -> tuple[User, bool]:
    r = await db.execute(select(User).where(User.email == email))
    u = r.scalar_one_or_none()
    if u:
        return u, False
    u = User(email=email, password_hash=_hash(pw), role=role)
    db.add(u)
    await db.flush()
    return u, True


# ─────────────────────────────────────────────────────────────────────────────
# Seed functions
# ─────────────────────────────────────────────────────────────────────────────

async def seed_candidates(db: AsyncSession) -> list[CandidateProfile]:
    profiles = []
    for c in CANDIDATES:
        user, _ = await get_or_create_user(db, c["email"], c["pw"], UserRole.CANDIDATE)
        r = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        cp = r.scalar_one_or_none()
        if cp is None:
            cp = CandidateProfile(
                user_id=user.id, full_name=c["full_name"], age=c.get("age"),
                location=c["location"], title=c["title"], profession=c["profession"],
                skills=c["skills"], life_skills=c["life_skills"],
                experience_years=c["experience_years"], education=c.get("education"),
                certifications=c.get("certifications"), languages=c.get("languages"),
                expected_salary=c.get("expected_salary"), job_type_pref=c.get("job_type_pref"),
                linkedin_url=c.get("linkedin_url"), bio=c.get("bio"),
                resume_text=c["resume"], is_searchable=True,
                is_open_to_work=c.get("is_open_to_work", True),
            )
            db.add(cp)
            await db.flush()
            logger.info("  ✓ Candidate: %s — %s", c["full_name"], c["title"])
        profiles.append(cp)
    return profiles


async def seed_employers(db: AsyncSession) -> tuple[list[EmployerProfile], list[JobPost]]:
    emp_profiles, all_jobs = [], []
    for e in EMPLOYERS:
        user, _ = await get_or_create_user(db, e["email"], e["pw"], UserRole.EMPLOYER)
        r = await db.execute(select(EmployerProfile).where(EmployerProfile.user_id == user.id))
        ep = r.scalar_one_or_none()
        if ep is None:
            ep = EmployerProfile(
                user_id=user.id, company_name=e["company_name"],
                industry=e["industry"], company_size=e.get("company_size"),
                founded_year=e.get("founded_year"), website=e.get("website"),
                description=e["description"], work_environment=e["work_environment"],
                benefits=e["benefits"], work_mode=e["work_mode"],
                location=e["location"], contact_name=e.get("contact_name"),
                contact_phone=e.get("contact_phone"),
            )
            db.add(ep)
            await db.flush()
            logger.info("  ✓ Employer: %s", e["company_name"])

        for jd in e["jobs"]:
            r2 = await db.execute(
                select(JobPost).where(JobPost.employer_id == ep.id, JobPost.title == jd["title"])
            )
            job = r2.scalar_one_or_none()
            if job is None:
                job = JobPost(
                    employer_id=ep.id, title=jd["title"],
                    description=jd["description"],
                    skills_required=jd["skills"],
                    experience_min=jd["experience_min"],
                    job_type=jd["job_type"], work_mode=jd["work_mode"],
                    salary_range=jd["salary"], location=jd["location"],
                    industry=jd["industry"], is_active=True,
                )
                db.add(job)
                await db.flush()
                logger.info("    → Job: %s", jd["title"])
            all_jobs.append(job)
    return emp_profiles, all_jobs


async def seed_applications(
    db: AsyncSession,
    candidates: list[CandidateProfile],
    jobs: list[JobPost],
) -> None:
    """
    Creates realistic applications at various pipeline stages.
    Maps candidates to jobs that actually fit their background.
    """
    # (candidate_index, job_title_fragment, status, days_ago, note)
    applications = [
        # Alice — Python engineer applying to backend roles
        (0, "Senior Backend Engineer (Python)", ApplicationStatus.SCREENING, 14, "Strong Python background, moved to screening after phone screen."),
        (0, "Backend Engineer (Python / Healthcare APIs)", ApplicationStatus.INTERVIEW, 10, "Good FHIR experience, invited to technical interview."),
        # Bob — ML engineer
        (1, "ML Engineer — Recommendations", ApplicationStatus.OFFER, 20, "Excellent portfolio, extended offer pending decision."),
        (1, "Risk & Fraud Data Scientist", ApplicationStatus.INTERVIEW, 8, "Strong stats background, in final round."),
        (1, "AI Research Scientist — NLP", ApplicationStatus.APPLIED, 3, None),
        # Carol — fullstack
        (2, "Full-Stack Engineer — Customer Platform", ApplicationStatus.ONBOARDED, 45, "Joined the team on 1 Aug. Excellent onboarding."),
        (2, "Senior UX/UI Designer", ApplicationStatus.REJECTED, 30, "Strong technical skills but design portfolio didn't match studio aesthetic."),
        # Dave — DevOps
        (3, "DevOps Engineer", ApplicationStatus.SCREENING, 12, "CKA cert impressive, discussing comp expectations."),
        (3, "Platform Engineer — Kubernetes", ApplicationStatus.TEST, 7, "Passed technical screen, sent take-home project."),
        # Eva — data engineer
        (4, "Risk & Fraud Data Scientist", ApplicationStatus.INTERVIEW, 9, "Great SQL skills, moved to hiring manager round."),
        (4, "Healthcare Data Scientist", ApplicationStatus.APPLIED, 2, None),
        # Frank — mobile
        (5, "Full-Stack Engineer — Customer Platform", ApplicationStatus.SCREENING, 11, "Flutter experience is a plus, reviewing mobile-adjacent skills."),
        # Grace — security
        (6, "Security Engineer", ApplicationStatus.OFFER, 15, "Outstanding OSCP. Verbal offer accepted, awaiting written confirmation."),
        (6, "Senior Embedded Systems Engineer (ADAS)", ApplicationStatus.REJECTED, 25, "Security background strong but lacks automotive/embedded experience."),
        # Henry — PM
        (7, "Growth Marketing Manager (B2B SaaS)", ApplicationStatus.WITHDRAWN, 20, None),
        # Isabella — quant
        (8, "Risk & Fraud Data Scientist", ApplicationStatus.TEST, 6, "Exceptional quant background, sent modelling assessment."),
        # Sarah — healthcare data scientist
        (10, "Healthcare Data Scientist", ApplicationStatus.INTERVIEW, 5, "PhD and clinical experience outstanding, final interview scheduled."),
        (10, "Backend Engineer (Python / Healthcare APIs)", ApplicationStatus.APPLIED, 1, None),
        # Miguel — UX
        (12, "Senior UX/UI Designer", ApplicationStatus.SCREENING, 8, "Portfolio very strong, fit check call scheduled."),
        # Nina — marketing
        (13, "Growth Marketing Manager (B2B SaaS)", ApplicationStatus.ONBOARDED, 60, "Exceptional results in first 30 days. Already exceeded MQL target."),
        # Liam — embedded
        (14, "Senior Embedded Systems Engineer (ADAS)", ApplicationStatus.INTERVIEW, 4, "ASIL-B certified, deep RTOS experience. Technical interview tomorrow."),
        # Amara — researcher
        (15, "AI Research Scientist — NLP", ApplicationStatus.OFFER, 10, "3 NeurIPS papers. Dream candidate. Offer letter sent."),
        # Rachel — ops
        (16, "Operations Manager — Fulfilment", ApplicationStatus.SCREENING, 7, "Six Sigma GB and 4 years ops experience. Screening in progress."),
        # Omar — legal
        (17, "Legal & Compliance Manager", ApplicationStatus.INTERVIEW, 6, "CAMS certification and MENA experience exactly what we need."),
        # Tom — CS
        (19, "Operations Manager — Fulfilment", ApplicationStatus.APPLIED, 2, None),
    ]

    for cand_idx, job_fragment, status, days_ago, note in applications:
        if cand_idx >= len(candidates):
            continue
        cp = candidates[cand_idx]

        # Find matching job
        job = None
        for j in jobs:
            if job_fragment.lower() in j.title.lower():
                job = j
                break
        if not job:
            continue

        existing = await db.execute(
            select(Application).where(
                Application.candidate_id == cp.id,
                Application.job_id == job.id,
            )
        )
        if existing.scalar_one_or_none() is None:
            app = Application(
                candidate_id=cp.id, job_id=job.id, status=status,
                employer_note=note,
                cover_letter=f"I am very excited about the {job.title} position at your company. My background in {cp.profession} aligns well with your requirements and I believe I can make a strong contribution to your team.",
                applied_at=_dt(days_ago),
                updated_at=_dt(max(0, days_ago - 2)),
            )
            db.add(app)
            logger.info("  ✓ Application: %s → %s [%s]", cp.full_name, job.title, status.value)


async def seed_outreaches(
    db: AsyncSession,
    employers: list[EmployerProfile],
    candidates: list[CandidateProfile],
    jobs: list[JobPost],
) -> None:
    """Creates outreach threads with realistic back-and-forth messages."""

    def _emp(name: str) -> EmployerProfile | None:
        return next((e for e in employers if name.lower() in e.company_name.lower()), None)

    def _cand(email_frag: str) -> CandidateProfile | None:
        return next((c for c in candidates if email_frag.lower() in (c.full_name or "").lower()), None)

    def _job(title_frag: str) -> JobPost | None:
        return next((j for j in jobs if title_frag.lower() in j.title.lower()), None)

    threads = [
        # TechCorp → Alice: full conversation leading to interview
        {
            "employer": _emp("TechCorp"), "candidate": _cand("Alice"),
            "job": _job("Senior Backend Engineer"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Alice, we came across your profile and your Python + AWS background is exactly what our platform team needs. We're building distributed logistics APIs at scale. Would you be open to a quick 20-minute chat this week? — Sarah, TechCorp"),
                ("CANDIDATE", "Hi Sarah! Thanks for reaching out — TechCorp's open-source work has been on my radar for a while. I'd love to chat. I'm available Tuesday or Thursday afternoon PST. Looking forward to it!"),
                ("EMPLOYER", "Perfect! Let's do Thursday at 3pm PST. I'll send a calendar invite shortly. In the meantime, feel free to check out our engineering blog at techcorp.io/blog — gives a good sense of the technical challenges we're solving."),
                ("CANDIDATE", "Great, Thursday at 3pm works perfectly. Just had a read through the blog — the post on async job processing was really interesting. See you Thursday!"),
            ],
        },
        # TechCorp → Bob: short warm outreach
        {
            "employer": _emp("TechCorp"), "candidate": _cand("Bob"),
            "job": _job("ML Engineer"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Bob! Your recommendation systems work caught our attention — we're rebuilding our shipment routing engine using ML and your PyTorch + Spark experience fits perfectly. Interested in exploring?"),
                ("CANDIDATE", "Hey! Definitely interested — logistics ML is a fascinating domain and TechCorp's scale is appealing. Happy to have a call. What does the role look like day-to-day?"),
                ("EMPLOYER", "Great question! You'd own the full ML lifecycle — feature engineering, training, A/B testing and production serving. Typical model serves 20M+ predictions/day. Team of 4 ML engineers reporting to the Head of AI. Salary up to $170k + equity. Shall I set up a call with the team?"),
                ("CANDIDATE", "That sounds excellent. Yes please — I'm free most of next week. Thursday works best if that suits."),
            ],
        },
        # FinTech → Carol: direct outreach, quick accept
        {
            "employer": _emp("FinTech"), "candidate": _cand("Carol"),
            "job": _job("Full-Stack Engineer"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Carol, I'm Marcus from FinTech Innovations. We saw your profile and love your React + GraphQL work. We're building the next generation of our customer platform and are looking for someone like you. Would you like to learn more?"),
                ("CANDIDATE", "Hi Marcus! Thank you for reaching out. I've been following FinTech Innovations — the real-time lending product is really impressive. I'd love to hear more about the role. Could you share more about the stack and team size?"),
            ],
        },
        # MedAI → Sarah: research-focused outreach
        {
            "employer": _emp("MedAI"), "candidate": _cand("Sarah"),
            "job": _job("Healthcare Data Scientist"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Sarah, I'm Dr. Vasquez from MedAI Systems. Your PhD work on sepsis prediction is actually very aligned with what we do — we deploy clinical ML models across 50 hospitals. I think you'd find the work here incredibly impactful. Would you be open to a conversation?"),
                ("CANDIDATE", "Dr. Vasquez, thank you so much for reaching out! I've actually read the MedAI paper on early deterioration detection — remarkable results. I would absolutely love to learn more about the team and the clinical deployment process. When would work for you?"),
                ("EMPLOYER", "Wonderful! I'm glad the research resonated. How about a 45-minute call next Monday at 10am EST? I can walk you through our current pipeline, the clinical validation process and the team structure."),
                ("CANDIDATE", "Monday at 10am EST works perfectly. I'll prepare a few questions about your FHIR integration approach. Looking forward to it!"),
            ],
        },
        # CloudBase → Grace: direct hire conversation
        {
            "employer": _emp("CloudBase"), "candidate": _cand("Grace"),
            "job": _job("Security Engineer"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Grace, Yuki here from CloudBase Infrastructure. Your OSCP + CISSP combination is rare and exactly what we need for our security lead role. We're building security-as-a-service for 400+ companies and need someone who can build the programme from the ground up. Interested?"),
                ("CANDIDATE", "Hi Yuki! CloudBase is doing really interesting work — I've seen some of your talks on zero-trust for multi-tenant Kubernetes. Yes, absolutely interested. Is this a leadership role or more hands-on?"),
                ("EMPLOYER", "Both, honestly — you'd be our first dedicated security hire so you'd be hands-on initially (penetration testing, threat modelling, SOC 2 automation) and then grow a team as we scale. Full ownership. Salary up to $165k + meaningful equity. Remote globally. Does that appeal?"),
                ("CANDIDATE", "That appeals a lot. Building a security programme from scratch is exactly the kind of challenge I'm looking for. I'd love to meet the team. Can we schedule a technical discussion?"),
            ],
        },
        # Cognify → Amara: peer researcher outreach
        {
            "employer": _emp("Cognify"), "candidate": _cand("Amara"),
            "job": _job("AI Research Scientist"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Amara, I'm actually a big fan of your NeurIPS paper on parameter-efficient multilingual fine-tuning — it's directly relevant to what we're building at Cognify. We're a small research lab (15 people) working on efficient multilingual LLMs and I think you'd be a great fit. Open to talking?"),
                ("CANDIDATE", "Oh, that's kind of you! I saw Cognify's preprint on sparse MoE architectures — very nice work. I'd definitely be interested in learning more. What's the research agenda for the next 12 months?"),
            ],
        },
        # Volt → Liam: direct match
        {
            "employer": _emp("Volt"), "candidate": _cand("Liam"),
            "job": _job("Senior Embedded Systems Engineer"),
            "status": OutreachStatus.PENDING,
            "messages": [
                ("EMPLOYER", "Hi Liam, I'm Klaus from Volt Automotive. Your automotive embedded systems experience is exactly what we need for our ADAS firmware team — your ISO 26262 certification in particular. We're developing next-gen lane-keeping and emergency braking systems for BMW and VW. Would you be interested in chatting?"),
            ],
        },
        # Design Studio → Miguel: creative outreach
        {
            "employer": _emp("Pixel"), "candidate": _cand("Miguel"),
            "job": _job("Senior UX/UI Designer"),
            "status": OutreachStatus.ACCEPTED,
            "messages": [
                ("EMPLOYER", "Hi Miguel! We discovered your Dribbble portfolio and your fintech redesign case study blew us away — the onboarding flow improvement from 34% to 72% completion is remarkable. We have an opening for a Senior Designer and think you'd be a perfect fit for our studio. Interested?"),
                ("CANDIDATE", "Hi Sofia! That project was definitely one of my favourites — there's something deeply satisfying about a conversion uplift backed by real user research. I've heard great things about Pixel & Craft. What kind of clients would I be working with primarily?"),
                ("EMPLOYER", "Primarily Series B fintech and healthtech — we just kicked off a new app for a London-based insurance startup and are starting a healthcare patient portal project. You'd be leading both with support from a junior designer. Happy to share more detail on a call?"),
                ("CANDIDATE", "Both of those sound right up my alley. Yes, I'd love a call. I'm in Lisbon so a Lisbon timezone slot would be ideal — any morning this week works for me."),
            ],
        },
    ]

    for thread_data in threads:
        emp = thread_data["employer"]
        cp  = thread_data["candidate"]
        job = thread_data["job"]
        if not emp or not cp:
            continue

        # Check if outreach already exists
        existing = await db.execute(
            select(DirectOutreach).where(
                DirectOutreach.employer_id == emp.id,
                DirectOutreach.candidate_id == cp.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        first_msg = thread_data["messages"][0][1]
        outreach = DirectOutreach(
            employer_id=emp.id, candidate_id=cp.id,
            job_id=job.id if job else None,
            message=first_msg,
            status=thread_data["status"],
            candidate_reply=next((m[1] for m in thread_data["messages"] if m[0] == "CANDIDATE"), None),
        )
        db.add(outreach)
        await db.flush()

        # Get user IDs for sender
        emp_user = await db.get(User, emp.user_id)
        cand_user = await db.get(User, cp.user_id)

        # Seed message thread
        for idx, (role, body) in enumerate(thread_data["messages"]):
            sender_id = emp_user.id if role == "EMPLOYER" else cand_user.id
            msg = OutreachMessage(
                outreach_id=outreach.id, sender_role=role,
                sender_id=sender_id, body=body,
            )
            db.add(msg)

        logger.info("  ✓ Outreach thread: %s → %s (%d messages)", emp.company_name, cp.full_name, len(thread_data["messages"]))


async def seed_ratings(
    db: AsyncSession,
    employers: list[EmployerProfile],
    candidates: list[CandidateProfile],
) -> None:
    # Candidates rating employers
    cand_employer_ratings = [
        (0, "FinTech", 5.0, "Incredibly smooth hiring process. Marcus was responsive and transparent throughout. The role description was accurate to what I actually do."),
        (2, "FinTech", 4.5, "Great experience overall. Well-organised interview process with clear feedback at each stage."),
        (6, "CloudBase", 5.0, "Best hiring experience I've ever had. Yuki was knowledgeable, honest about challenges, and the team interview felt like a real technical conversation."),
        (13, "Momentum", 4.0, "Efficient process, clear expectations. Would have appreciated more info about team structure upfront."),
        (15, "Cognify", 5.0, "Talking to other researchers during the process was refreshing. They really care about the quality of work."),
        (10, "MedAI", 5.0, "Dr. Vasquez is incredible. The whole team is mission-driven and they clearly care about clinical outcomes, not just the technology."),
        (12, "Pixel", 4.5, "Lovely studio culture. The design critique process during interviews was challenging but fair."),
        (14, "Volt", 3.5, "Solid process but slower than expected — took 6 weeks from first contact to offer. The technical depth was impressive though."),
    ]

    # Employers rating candidates
    emp_candidate_ratings = [
        ("TechCorp", 0, 5.0, "Alice is exceptional — technically brilliant and a natural communicator. Highly recommend."),
        ("TechCorp", 1, 4.5, "Bob's ML background is outstanding. Very strong portfolio and published research."),
        ("FinTech", 2, 5.0, "Carol joined the team and immediately made an impact. Excellent engineer and team player."),
        ("CloudBase", 3, 4.0, "Dave is one of the most experienced K8s engineers we've spoken to. Highly reliable."),
        ("CloudBase", 6, 5.0, "Grace's security expertise is world-class. The OSCP + CISSP combination is rare."),
        ("MedAI", 10, 5.0, "Sarah's clinical AI background is exactly what the field needs. Outstanding researcher."),
        ("Momentum", 13, 4.5, "Nina delivered results from week one. One of the best hires we've made."),
        ("Cognify", 15, 5.0, "Amara's NeurIPS work is directly relevant. One of the top NLP researchers we've interviewed."),
    ]

    def _emp(name: str) -> EmployerProfile | None:
        return next((e for e in employers if name.lower() in e.company_name.lower()), None)

    for cand_idx, emp_name, score, review in cand_employer_ratings:
        if cand_idx >= len(candidates):
            continue
        ep = _emp(emp_name)
        if not ep:
            continue
        cp = candidates[cand_idx]
        cand_user = await db.get(User, cp.user_id)
        if not cand_user:
            continue
        existing = await db.execute(
            select(Rating).where(Rating.rater_user_id == cand_user.id, Rating.target_employer_id == ep.id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(Rating(
                rater_user_id=cand_user.id, target=RatingTarget.EMPLOYER,
                target_employer_id=ep.id, score=score, review=review,
            ))

    for emp_name, cand_idx, score, review in emp_candidate_ratings:
        if cand_idx >= len(candidates):
            continue
        ep = _emp(emp_name)
        if not ep:
            continue
        cp = candidates[cand_idx]
        emp_user = await db.get(User, ep.user_id)
        if not emp_user:
            continue
        existing = await db.execute(
            select(Rating).where(Rating.rater_user_id == emp_user.id, Rating.target_candidate_id == cp.id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(Rating(
                rater_user_id=emp_user.id, target=RatingTarget.CANDIDATE,
                target_candidate_id=cp.id, score=score, review=review,
            ))

    logger.info("  ✓ Ratings seeded.")


async def seed_notifications(
    db: AsyncSession,
    candidates: list[CandidateProfile],
    employers: list[EmployerProfile],
) -> None:
    notifs = [
        # Candidates
        (0, NotificationType.STATUS_CHANGE, "Application update: Senior Backend Engineer", "Your application status changed to SCREENING. TechCorp is reviewing your profile.", "/applications"),
        (1, NotificationType.OUTREACH, "New message from TechCorp Solutions", "Your recommendation systems work caught our attention...", "/outreach/inbox"),
        (1, NotificationType.STATUS_CHANGE, "Application update: ML Engineer", "🎉 Congratulations! You received an offer from TechCorp Solutions.", "/applications"),
        (2, NotificationType.STATUS_CHANGE, "You're onboarded at FinTech Innovations!", "Welcome to the team, Carol! Your first day is confirmed.", "/applications"),
        (5, NotificationType.JOB_MATCH, "3 new jobs match your Flutter skills", "New mobile developer positions posted in the last 24 hours.", "/jobs"),
        (6, NotificationType.STATUS_CHANGE, "Offer received: Security Engineer at CloudBase", "CloudBase has extended you a formal offer. Congratulations!", "/applications"),
        (10, NotificationType.OUTREACH, "New message from MedAI Systems", "Dr. Vasquez would like to discuss your clinical ML work.", "/outreach/inbox"),
        (13, NotificationType.STATUS_CHANGE, "You're onboarded at Momentum Growth Agency!", "Nina, welcome aboard! Your onboarding docs have been sent.", "/applications"),
        (15, NotificationType.OUTREACH, "New message from Cognify AI Labs", "We loved your NeurIPS paper and want to discuss a research role.", "/outreach/inbox"),
        (15, NotificationType.STATUS_CHANGE, "Offer received: AI Research Scientist", "Cognify has extended you an offer. Check your email for details.", "/applications"),
        # Employers (notify on replies)
        (None, NotificationType.APPLICATION, None, None, None),  # placeholder
    ]

    for i, (cand_idx, ntype, title, body, link) in enumerate(notifs):
        if cand_idx is None:
            continue
        if cand_idx >= len(candidates):
            continue
        cp = candidates[cand_idx]
        cand_user = await db.get(User, cp.user_id)
        if not cand_user:
            continue
        existing = await db.execute(
            select(Notification).where(
                Notification.user_id == cand_user.id,
                Notification.title == title,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(Notification(
                user_id=cand_user.id, type=ntype,
                title=title, body=body, link=link,
                is_read=i > 3,  # first few unread, rest read
            ))

    # Employer notifications
    emp_notifs = [
        ("TechCorp", NotificationType.APPLICATION, "New application: Senior Backend Engineer", "Alice Chen applied with 7 years Python experience.", "/applications/employer"),
        ("TechCorp", NotificationType.APPLICATION, "New application: ML Engineer", "Bob Martinez applied — 3 NeurIPS papers, strong PyTorch background.", "/applications/employer"),
        ("FinTech", NotificationType.APPLICATION, "Carol Kim accepted your offer!", "Carol will be joining on 1 August. Onboarding docs sent.", "/applications/employer"),
        ("CloudBase", NotificationType.OUTREACH, "Grace Nakamura replied to your message", "She's very interested and available for a technical call next week.", "/outreach/employer-view"),
        ("MedAI", NotificationType.OUTREACH, "Sarah Johnson replied to your message", "Monday at 10am EST works perfectly for her.", "/outreach/employer-view"),
        ("Cognify", NotificationType.OUTREACH, "Amara Diallo replied to your message", "She's interested and wants to know about the research agenda.", "/outreach/employer-view"),
    ]

    for emp_name, ntype, title, body, link in emp_notifs:
        ep = next((e for e in employers if emp_name.lower() in e.company_name.lower()), None)
        if not ep:
            continue
        emp_user = await db.get(User, ep.user_id)
        if not emp_user:
            continue
        existing = await db.execute(
            select(Notification).where(
                Notification.user_id == emp_user.id,
                Notification.title == title,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(Notification(
                user_id=emp_user.id, type=ntype,
                title=title, body=body, link=link, is_read=False,
            ))

    logger.info("  ✓ Notifications seeded.")


async def seed_vectors(candidates: list[CandidateProfile]) -> None:
    await ensure_collection()
    for cp in candidates:
        text = " ".join(filter(None, [cp.title, cp.profession, cp.skills, cp.resume_text, cp.bio]))
        await upsert_candidate_vector(
            cp.id, text,
            {
                "candidate_id": cp.id, "title": cp.title,
                "profession": cp.profession, "skills": cp.skills,
                "experience_years": cp.experience_years,
                "location": cp.location,
            }
        )
        logger.info("  ✓ Indexed: %s — %s", cp.full_name, cp.title)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("=" * 65)
    logger.info("SmartRecruit — Rich Demo Data Seeder")
    logger.info("=" * 65)

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    logger.info("\n[1/6] Creating database tables…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("  Tables ready.")

    logger.info("\n[2/6] Seeding %d candidates…", len(CANDIDATES))
    async with Session() as db:
        candidates = await seed_candidates(db)
        await db.commit()

    logger.info("\n[3/6] Seeding %d employers & jobs…", len(EMPLOYERS))
    async with Session() as db:
        r_c = await db.execute(select(CandidateProfile).order_by(CandidateProfile.id))
        candidates = list(r_c.scalars().all())
        employers, jobs = await seed_employers(db)
        await db.commit()

    logger.info("\n[4/6] Seeding applications, outreach threads & ratings…")
    async with Session() as db:
        from sqlalchemy import select as _sel
        r_c = await db.execute(_sel(CandidateProfile).order_by(CandidateProfile.id))
        r_e = await db.execute(_sel(EmployerProfile).order_by(EmployerProfile.id))
        r_j = await db.execute(_sel(JobPost).order_by(JobPost.id))
        candidates = list(r_c.scalars().all())
        employers  = list(r_e.scalars().all())
        jobs       = list(r_j.scalars().all())

        await seed_applications(db, candidates, jobs)
        await seed_outreaches(db, employers, candidates, jobs)
        await seed_ratings(db, employers, candidates)
        await seed_notifications(db, candidates, employers)
        await db.commit()

    logger.info("\n[5/6] Indexing candidate vectors in Qdrant…")
    async with Session() as db:
        r = await db.execute(select(CandidateProfile).order_by(CandidateProfile.id))
        candidates = list(r.scalars().all())
    await seed_vectors(candidates)

    logger.info("\n" + "=" * 65)
    logger.info("Seed complete!")
    logger.info("  %d candidates | %d employers | %d jobs", len(CANDIDATES), len(EMPLOYERS), sum(len(e["jobs"]) for e in EMPLOYERS))
    logger.info("  Start the server: python3 app.py")
    logger.info("=" * 65)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
