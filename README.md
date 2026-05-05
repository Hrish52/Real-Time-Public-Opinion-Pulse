# Real-Time Public Opinion Pulse

> **A multi-platform opinion tracking system that ingests live data, performs multi-level NLP analysis, and visualizes cross-platform trends on an interactive dashboard.**

---

## 🚀 Project Overview
**Real-Time Public Opinion Pulse** is a data engineering and NLP project designed to monitor the "vibe" of the internet across disparate platforms. It captures live posts from social media, news outlets, and forums to analyze how public sentiment, stance, and emotion shift in response to global events.

Built entirely with **zero-cost** tools, this project demonstrates end-to-end capabilities in automated data ingestion, machine learning pipeline construction, and editorial-grade data visualization.

## ✨ Key Features
* **Three-Level NLP Analysis:** Goes beyond basic sentiment to include **Stance Detection** (In Favor/Against/Neutral) and **Emotion Classification** (7 distinct emotions).
* **Cross-Platform Divergence:** Compare how the same topic is discussed on Bluesky vs. The Guardian vs. YouTube to reveal platform-specific biases.
* **Temporal Shift Detection:** A sliding window algorithm that identifies sudden swings in opinion and links them to triggering events.
* **NYT-Themed Dashboard:** A clean, editorial-style Streamlit interface designed for clarity and impact.

## 🛠️ Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Language** | Python 3.11+ |
| **Ingestion** | ATProto (Bluesky), yt-dlp (YouTube), Feedparser (RSS), Guardian API |
| **NLP Models** | HuggingFace Transformers (`twitter-roberta`, `bart-large-mnli`, `distilroberta-base`) |
| **Database** | Supabase (PostgreSQL) |
| **Dashboard** | Streamlit + Plotly |
| **Automation** | GitHub Actions (Cron-scheduled runs) |

## 📊 Pipeline Architecture
The system operates in a 4-phase automated pipeline:
1.  **Ingestion:** Pulls live posts from 5+ sources (Bluesky, YouTube, The Guardian, Dev.to, and 20+ RSS feeds).
2.  **NLP Processing:** Runs sentiment scoring, zero-shot stance classification (threshold: 0.40), and emotion mapping.
3.  **Cleaning & Feature Engineering:** Validates data, deduplicates entries using TF-IDF, and derives features like engagement tiers and length categories.
4.  **Visualization:** Serves data to a Streamlit dashboard with dedicated views for Topic Drill-downs and Source Analysis.

## 📈 Tracked Topics
The system monitors 9 high-impact domains using curated keyword sets:
- 🤖 Artificial Intelligence
- 🌍 Climate Policy
- 🛡️ Data Privacy
- 📉 Tech Layoffs
- 💼 Business
- 🏛️ US Politics
- 🎬 Hollywood
- 🌐 World News
- 💻 Tech News

## ⚙️ Automation & Deployment
- **GitHub Actions:** Configured to run the pipeline every 6 hours to stay within free-tier limits (~1,440 minutes/month).
- **Hosting:** The dashboard is live on **Streamlit Community Cloud**, auto-deploying on every push to the main branch.

## 📝 Known Issues & Lessons Learned
- **API Realities:** Transitioned from X (Twitter) to Bluesky due to API cost barriers.
- **Data Quality:** Implemented specific keyword tightening to prevent generic terms (like "war" or "business") from flooding the dataset with irrelevant results.
- **Scalability:** Optimized Supabase queries using pagination to bypass the default 1000-row limit.

---
*This project was built as a portfolio-grade demonstration of full-stack data science and engineering.*
