# 🚀 The Migration - Marketing Intelligence Dashboard

A premium, high-performance marketing dashboard built with **Streamlit** and **Python Asyncio**. This dashboard consolidates data from GoHighLevel (GHL), Meta Ads, Google Analytics 4 (GA4), and Google Search Console (GSC) into a single, real-time intelligence interface.

## 🌟 Key Features

- **7 Dynamic Tabs**: Our Vision, Ads & Creatives, Traffic Behavior, SEO Performance, Pipeline Analysis, Attribution, and Consultant Capacity.
- **Direct Async Sync**: High-speed, concurrent data fetching from multiple APIs.
- **Advanced Theme System**: Support for both premium Dark and Light modes.
- **Cloud-Native**: Optimized for **Streamlit Community Cloud** with integrated Secrets management.
- **Executive Scorecards**: High-level OKR and KPI tracking.

## 🛠️ Local Setup

1.  **Clone the Repository**:
    ```bash
    git clone <your-repo-url>
    cd ghl-integration
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Secrets**:
    Create a `.streamlit/secrets.toml` file with your API credentials (refer to `secrets_template.toml`).

4.  **Run the App**:
    ```bash
    streamlit run app.py
    ```

## ☁️ Cloud Deployment

This app is designed to be deployed directly to [Streamlit Community Cloud](https://share.streamlit.io/).

1.  Push your code to a **Private** GitHub repository.
2.  Connect your GitHub account to Streamlit Cloud.
3.  Deploy a new app pointing to your `app.py`.
4.  Copy your `.streamlit/secrets.toml` content into the Streamlit Cloud **Secrets** settings.

---
© 2026 The Migration. All Rights Reserved.
