# SmartRecruit — Recruitment & Talent Matchmaking Platform

A full-featured recruitment platform connecting candidates and employers.
Built with **Python**, **Litestar**, **SQLAlchemy**, **PostgreSQL**, and **Qdrant**.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | Litestar 2.12 (async Python) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Relational Database | PostgreSQL |
| Search Engine | Qdrant (standalone binary) + fastembed |
| Templates | Jinja2 |
| Frontend | Tailwind CSS (CDN) + Vanilla JS |
| Server | Uvicorn with auto-reload |

---

## Prerequisites

You need the following installed and running before starting:

### 1. Python 3.10 or higher
Your machine uses Python 3.13. Always run with `python3`, never `python` (which points to a system Python 2.7).

### 2. PostgreSQL
Already installed at `C:\BioTime\pgsql`. Must be running on `localhost:5432`.

The database `recruitment_db` must exist. Create it once:
```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE recruitment_db;"
```
Password: `123321123`

### 3. Qdrant standalone binary
No Docker required. Download the Windows binary from:

**https://github.com/qdrant/qdrant/releases/latest**

Download: `qdrant-x86_64-pc-windows-msvc.zip`

Extract `qdrant.exe` and place it in the `recruitment_platform/` folder (next to `app.py`).

---

## Project Layout

```
recruitment_platform/
├── app.py                          # Application entry point + Uvicorn runner
├── config.py                       # All configuration constants (reads .env)
├── models.py                       # All SQLAlchemy ORM models
├── seed_db.py                      # Database + search index seeder
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables
├── qdrant_config.yaml              # Qdrant server configuration
├── qdrant.exe                      # Qdrant binary (you download this)
│
├── controllers/
│   ├── auth.py                     # Register, login, logout
│   ├── candidates.py               # Candidate list, search, dashboard
│   ├── employers.py                # Employer list, job posting, dashboard
│   ├── jobs.py                     # Browse jobs, apply, bookmark, close
│   ├── applications.py             # Application pipeline management
│   ├── profiles.py                 # Public profiles, edit profile, avatar, CV, send outreach
│   ├── notifications.py            # In-app notifications
│   ├── ratings.py                  # Candidate and employer ratings
│   └── outreach.py                 # Messaging system (send, reply, inbox, employer view)
│
├── services/
│   ├── auth.py                     # Password hashing, session management
│   ├── notifications.py            # Notification creation and retrieval
│   ├── ratings.py                  # Rating submission and aggregation
│   └── vector_search.py            # Qdrant client + search indexing
│
└── templates/
    ├── base.html                   # Shared layout (nav, footer, notification badge)
    ├── landing.html                # Public landing page
    ├── 404.html                    # Error page
    ├── auth/
    │   ├── login.html
    │   └── register.html
    ├── candidate/
    │   ├── dashboard.html
    │   ├── profile.html            # Edit own profile (CV, avatar, skills, etc.)
    │   ├── applications.html       # Application history + pipeline tracker
    │   └── outreach_inbox.html     # Candidate message inbox with reply forms
    ├── employer/
    │   ├── dashboard.html
    │   ├── profile.html            # Edit company profile and logo
    │   ├── post_job.html           # Create a new job ad
    │   ├── applicants.html         # Manage applicants, message, make offer, reject
    │   ├── my_jobs.html            # All job posts with applicant counts
    │   └── outreach_sent.html      # Employer view of sent messages + candidate replies
    └── shared/
        ├── profile_view.html       # Public social-style profile (both roles)
        ├── job_detail.html         # Job detail + apply modal
        ├── jobs.html               # Browse / search all jobs
        ├── notifications.html      # All notifications
        └── application_detail.html # Single application detail
```

---

## Setup & Running

### Step 1 — Install Python dependencies

```powershell
cd "c:\Users\ceilr\Documents\Project\School\Apparent V2\recruitment_platform"
python3 -m pip install -r requirements.txt
```

### Step 2 — Start Qdrant (keep this terminal open)

```powershell
.\qdrant.exe --config-path qdrant_config.yaml
```

You should see: `Qdrant HTTP listening on 6333`

Leave this running. Every time you use the platform, Qdrant must be running.

### Step 3 — Create the database (first time only)

```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE recruitment_db;"
```

### Step 4 — Seed the database (first time only)

Populates 8 candidates, 3 employers, 5 job posts, applications, ratings, notifications, and indexes all profiles for search.

```powershell
python3 seed_db.py
```

### Step 5 — Start the application

Open a second terminal (keep Qdrant running in the first):

```powershell
python3 app.py
```

Open **http://127.0.0.1:8000** in your browser.

---

## Fresh Start (wipe everything and reseed)

```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "DROP DATABASE recruitment_db;"
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE recruitment_db;"
python3 seed_db.py
```

---

## Demo Accounts (seeded)

### Candidates

| Name | Email | Password | Role / Specialty |
|------|-------|----------|-----------------|
| Alice Chen | alice.chen@example.com | password123 | Senior Python Engineer |
| Bob Martinez | bob.martinez@example.com | password123 | Machine Learning Engineer |
| Carol Kim | carol.kim@example.com | password123 | Full-Stack Developer |
| Dave Okonkwo | dave.okonkwo@example.com | password123 | DevOps / Platform Engineer |
| Eva Rossi | eva.rossi@example.com | password123 | Data Engineer |
| Frank Osei | frank.osei@example.com | password123 | Mobile Developer |
| Grace Nakamura | grace.nakamura@example.com | password123 | Cybersecurity Engineer |
| Henry Obi | henry.obi@example.com | password123 | Senior Product Manager |
| Isabella Torres | isabella.chen@example.com | password123 | Quantitative Analyst |
| James Anderson | james.anderson@example.com | password123 | Senior Business Analyst |
| Sarah Johnson | sarah.johnson@example.com | password123 | Healthcare Data Scientist |
| Miguel Rodrigues | miguel.rodrigues@example.com | password123 | UX/UI Designer |
| Nina Petrov | nina.petrov@example.com | password123 | Growth Marketing Manager |
| Liam O'Connor | liam.oconnor@example.com | password123 | Embedded Systems Engineer |
| Amara Diallo | amara.diallo@example.com | password123 | AI Research Scientist |
| Rachel Park | rachel.park@example.com | password123 | Operations Manager |
| Omar Hassan | omar.hassan@example.com | password123 | Legal & Compliance Manager |
| Priya Sharma | priya.sharma@example.com | password123 | Backend Engineer (Java) |
| Tom Whitfield | tom.whitfield@example.com | password123 | Customer Success Manager |

### Employers

| Company | Email | Password | Industry |
|---------|-------|----------|----------|
| TechCorp Solutions | hr@techcorp.com | employer123 | Technology (Logistics SaaS) |
| FinTech Innovations | talent@fintech.io | employer123 | Finance (Challenger Bank) |
| CloudBase Infrastructure | recruiting@cloudbase.dev | employer123 | Technology (K8s-as-a-Service) |
| MedAI Systems | jobs@healthtech-ai.com | employer123 | Healthcare |
| Pixel & Craft Studio | people@designstudio.co | employer123 | Design |
| Momentum Growth Agency | hr@growthagency.com | employer123 | Marketing |
| LexPro Technologies | careers@legaltech.com | employer123 | Legal Tech |
| Volt Automotive GmbH | talent@automaker.de | employer123 | Automotive |
| SwiftShip Logistics | hr@ecomlogistics.com | employer123 | E-commerce / Logistics |
| Cognify AI Labs | jobs@aicorp.io | employer123 | AI Research |

---

## Features

### For Candidates
- Register and build a rich profile — name, age, birthday, phone, location, bio
- Upload a profile picture (stored in database)
- Upload a CV / resume (stored in database, downloadable by employers)
- Add technical skills, soft skills, education, certifications, languages
- Set expected salary, preferred job type, LinkedIn and portfolio URLs
- Browse and search all active job postings
- Get job recommendations matched to your profile
- Apply to jobs with an optional cover letter
- Track applications through the full hiring pipeline:
  `Applied → Screening → Interview → Test → Offer → Onboarded`
- Receive in-app notifications for messages, status changes and job matches
- Bookmark jobs to review later
- **Read and reply to employer messages** from your Messages inbox
- Quick Accept / Decline Politely buttons for fast responses
- Rate employers you've interacted with (1–5 stars + review)
- Public profile visible to employers, similar to a social media profile
- Toggle searchability and open-to-work status anytime

### For Employers
- Register with full company info — name, industry, size, founded year, website
- Upload a company logo (stored in database)
- Describe work environment, culture, and benefits
- Post job ads with title, description, required skills, salary range, job type and work mode
- Search candidates by profession using plain-English description
- Send direct outreach messages to candidates from their profile or the applicants page
- Use message templates (invite to interview, extend offer, request more info)
- **View candidate replies** in the Messages sent view
- Manage all applicants across all jobs with a visual pipeline
- Move applicants through stages with one click (Make Offer, Reject)
- Add private notes when updating an applicant's status
- Candidate is notified automatically on every status change
- Close job posts when filled
- Rate candidates after interactions (1–5 stars + review)
- Public company profile visible to candidates

### Platform-wide
- Session-based authentication with 30-day login sessions
- In-app notification system with real-time unread badge (polls every 30 seconds)
- Notification links navigate directly to the relevant page (messages go to inbox, status changes go to application)
- Two-way ratings on both candidates and employers
- Social-style public profiles for both roles
- Teal dark-mode UI with Tailwind CSS

---

## Pages & Routes

### Public (no login required)
| Path | Description |
|------|-------------|
| `/` | Landing page |
| `/jobs` | Browse all active job posts |
| `/jobs/{id}` | Job detail page |
| `/auth/login` | Sign in |
| `/auth/register` | Create account (choose Candidate or Employer) |

### Candidate (login required)
| Path | Description |
|------|-------------|
| `/dashboard/candidate` | Candidate dashboard — applications, recommendations, notifications |
| `/profile/edit` | Edit profile, upload CV and photo |
| `/profile/candidate/{id}` | View any candidate's public profile |
| `/applications` | Application history with pipeline progress bars |
| `/outreach/inbox` | **Message inbox** — read and reply to employer messages |
| `/jobs/{id}` | Apply to a job or bookmark it |
| `/notifications` | All notifications |

### Employer (login required)
| Path | Description |
|------|-------------|
| `/dashboard/employer` | Employer dashboard — candidate search, recent applicants, job stats |
| `/profile/edit` | Edit company profile and logo |
| `/profile/employer/{id}` | View any company's public profile |
| `/employers/post-job` | Post a new job ad |
| `/applications/employer` | Manage all applicants — message, update pipeline, make offer |
| `/jobs/my` | All your job posts with applicant counts |
| `/outreach/employer-view` | **Sent messages** — view candidate replies |
| `/notifications` | All notifications |

### Shared
| Path | Description |
|------|-------------|
| `/profile/candidate/{id}` | Public candidate profile with ratings and outreach button |
| `/profile/employer/{id}` | Public employer profile with open jobs and ratings |

### API (JSON)
| Path | Description |
|------|-------------|
| `/candidates/search?q=<query>` | Search candidates by plain-English description |
| `/candidates/` | List searchable candidates (paginated) |
| `/employers/` | List all employers |
| `/notifications/count` | Unread notification count (used by nav badge) |
| `/schema/swagger` | Swagger UI — interactive API docs |
| `/schema/rapidoc` | RapiDoc UI |

---

## Database Schema

```
users
  id, email (unique), password_hash, role (CANDIDATE/EMPLOYER/ADMIN),
  is_active, created_at

user_sessions
  id, user_id, token (unique), expires_at, created_at

candidate_profiles
  id, user_id, full_name, age, birthday, phone, location, bio,
  avatar_data (binary), avatar_mime,
  title, profession, skills, life_skills, experience_years,
  education, certifications, languages, expected_salary, job_type_pref,
  linkedin_url, portfolio_url,
  cv_data (binary), cv_filename, cv_mime,
  resume_text, is_searchable, is_open_to_work, updated_at

employer_profiles
  id, user_id, company_name, industry, company_size, founded_year,
  website, description, work_environment, benefits, work_mode, location,
  logo_data (binary), logo_mime,
  contact_name, contact_phone, linkedin_url, updated_at

job_posts
  id, employer_id, title, description, skills_required, experience_min,
  job_type, work_mode, location, salary_range, industry,
  is_active, expires_at, created_at

applications
  id, candidate_id, job_id, cover_letter,
  status (APPLIED/SCREENING/INTERVIEW/TEST/OFFER/ONBOARDED/REJECTED/WITHDRAWN),
  employer_note, applied_at, updated_at

direct_outreaches
  id, employer_id, candidate_id, job_id,
  message (employer's original message),
  candidate_reply (candidate's reply text),
  replied_at, status (PENDING/ACCEPTED/REJECTED), created_at

job_bookmarks
  id, candidate_id, job_id, created_at

notifications
  id, user_id, type (OUTREACH/APPLICATION/JOB_MATCH/STATUS_CHANGE/RATING/SYSTEM),
  title, body, link, is_read, created_at

ratings
  id, rater_user_id, target_candidate_id, target_employer_id,
  target (CANDIDATE/EMPLOYER), score (1.0–5.0), review, created_at
```

---

## Configuration

All settings live in `.env`. The defaults work for local development:

```env
DATABASE_URL=postgresql+asyncpg://postgres:123321123@localhost:5432/recruitment_db
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=candidates
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
RELOAD=true
```

---

## Deployment (Railway — Free Tier)

> ⚠️ **Never commit your `.env` file or paste real API keys into the README.** The `.gitignore` already excludes `.env`. If you accidentally pushed credentials, rotate them immediately.

This project needs a **persistent server**, **PostgreSQL**, and **Qdrant**. The only platform that supports all three for free is **Railway**.

---

### What you will set up

| Service | Where | Cost |
|---------|-------|------|
| App hosting | Railway | Free ($5/month credit, no card required to start) |
| PostgreSQL database | **Neon** (NOT Railway addon) | Completely free, no credit usage |
| Qdrant vector search | Qdrant Cloud | Free (1 GB cluster, no card required) |

> **Why Neon instead of Railway's PostgreSQL addon?**
> Railway's built-in PostgreSQL counts against your $5/month credit and exhausts it fast.
> Neon is a separate free PostgreSQL service — it does not consume Railway credit at all.

---

### Part 1 — Create your `railway.json` file

Create a file named `railway.json` in the `recruitment_platform` folder with exactly this content:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

---

### Part 2 — Push the project to GitHub

**1. Install Git** (if not already installed)
Download from https://git-scm.com/download/win and install with default settings.

**2. Create a GitHub account** (if you don't have one)
Go to https://github.com and sign up.

**3. Create a new repository on GitHub**
- Go to https://github.com/new
- Name it `smartrecruit`
- Set to Public or Private — your choice
- Do NOT tick "Add README" or "Add .gitignore" — the project already has both
- Click **Create repository**

**4. Push from your terminal** (run from inside the `recruitment_platform` folder)

```powershell
git init
git add .
git commit -m "Initial commit — SmartRecruit platform"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/smartrecruit.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username. When prompted for a password, use a **Personal Access Token** (not your GitHub password). Create one at: https://github.com/settings/tokens → Generate new token → tick `repo` scope.

---

### Part 3 — Set up Qdrant Cloud (free vector search, no Docker)

**1.** Go to https://cloud.qdrant.io and sign up (Google or email).

**2.** Click **Create cluster** → choose **Free tier** → pick any region → name it `smartrecruit` → click **Create**.

**3.** Once created, copy two things:
- **Cluster URL** — looks like `https://xxxxxxxx.eu-central.aws.cloud.qdrant.io`
- **API Key** — a long string shown in the cluster dashboard

Store these somewhere safe. You will paste them as environment variables in Part 4. **Do not put them in any file you commit to GitHub.**

---

### Part 4 — Deploy on Railway

**1.** Go to https://railway.app and sign up with your GitHub account.

**2.** Click **New Project** → **Deploy from GitHub repo** → select your `smartrecruit` repository. Railway starts building automatically.

**3.** Set up your free PostgreSQL database on Neon (do this BEFORE setting environment variables):
- Go to https://neon.tech and sign up (free, no card needed)
- Click **New Project** → give it a name like `smartrecruit` → click **Create project**
- Neon shows you a **Connection string** — it looks like:
  ```
  postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
  ```
- Copy this string. You will paste it as `DATABASE_URL` in the next step.
- **Important:** Change `postgresql://` to `postgresql+asyncpg://` so it works with the async driver this project uses. Example:
  ```
  postgresql+asyncpg://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?ssl=require
  ```
  Note: also change `sslmode=require` to `ssl=require` for asyncpg compatibility.

**4.** Set environment variables:
- Click on your **app service**  → **Variables** tab
- Add each variable below:

```
DATABASE_URL     = postgresql+asyncpg://user:password@ep-xxx.neon.tech/neondb?ssl=require
                   (your Neon connection string — modified as described in step 3)
QDRANT_HOST      = xxxxxxxx.eu-central.aws.cloud.qdrant.io
                   (your cluster URL WITHOUT the https:// prefix)
QDRANT_PORT      = 6333
QDRANT_API_KEY   = paste your Qdrant API key here
QDRANT_COLLECTION = candidates
SESSION_SECRET   = (generate this — see below)
RELOAD           = false
SERVER_HOST      = 0.0.0.0
```

To generate `SESSION_SECRET`, run this locally and copy the output:
```powershell
python3 -c "import secrets; print(secrets.token_hex(32))"
```

You do NOT need to set `DATABASE_URL` via a Railway addon — you are using Neon instead, so paste your Neon connection string directly as shown above.

**5.** Click **Deploy** (or push any commit). Railway builds and starts the app in ~2 minutes.

**6.** Seed the database:
- In Railway, click your app service → **Shell** tab
- Run:
  ```bash
  python3 seed_db.py
  ```
  This creates all database tables and indexes candidate profiles in Qdrant Cloud.

**7.** Find your live URL:
- Click your app service → **Settings** → **Domains**
- Your app will be at something like: `https://smartrecruit-production.up.railway.app`

---

### Part 5 — Update the app after changes

Every time you change the code locally:

```powershell
git add .
git commit -m "Brief description of change"
git push
```

Railway detects the push and redeploys automatically within ~2 minutes.

---

### Troubleshooting deployment

**Build fails with "module not found"**
Check that `requirements.txt` is in the root of the repository (same level as `app.py`).

**App starts but Qdrant search returns no results**
You need to run `python3 seed_db.py` via the Railway shell after the first deployment to index the vectors.

**`DATABASE_URL` connection error**
Make sure you modified the Neon connection string correctly:
- Changed `postgresql://` → `postgresql+asyncpg://`
- Changed `sslmode=require` → `ssl=require`
- Pasted the full string as the `DATABASE_URL` environment variable in Railway

**QDRANT_HOST format**
Use the hostname only — no `https://` prefix. Example:
- ✅ `abc123.eu-central.aws.cloud.qdrant.io`
- ❌ `https://abc123.eu-central.aws.cloud.qdrant.io`

---

**`python` not found / Python 2.7 errors**
Always use `python3`. The system `python` command points to a BioTime Python 2.7 installation.

**`pip` errors**
Use `python3 -m pip install ...` instead of `pip install ...`.

**PowerShell script execution disabled**
Run `qdrant.exe` directly:
```powershell
.\qdrant.exe --config-path qdrant_config.yaml
```

**Enum type mismatch on seed**
The database has stale enum types from a previous run. Drop and recreate:
```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "DROP DATABASE recruitment_db;"
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -c "CREATE DATABASE recruitment_db;"
python3 seed_db.py
```

**Qdrant not reachable**
Make sure `qdrant.exe` is running in a separate terminal before starting `app.py` or `seed_db.py`.

**Notification links go to wrong page after a database restore**
Run this once to fix existing notification links:
```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -d recruitment_db -c "UPDATE notifications SET link = '/outreach/inbox' WHERE type = 'OUTREACH';"
```

**`candidate_reply` column missing error after upgrading from an older version**
The messaging reply columns were added after initial release. Run this once:
```powershell
& "C:\BioTime\pgsql\bin\psql.exe" -U postgres -d recruitment_db -c "ALTER TABLE direct_outreaches ADD COLUMN IF NOT EXISTS candidate_reply TEXT; ALTER TABLE direct_outreaches ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ;"
```
