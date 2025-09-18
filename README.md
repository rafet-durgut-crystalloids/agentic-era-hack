# PromoSphere

PromoSphere is an **AI-powered Marketing Operations Assistant** for
retail businesses.\
It helps create, monitor, and optimize **budgets, promotions, campaigns,
and strategies** by leveraging Google Cloud services like **BigQuery,
Firestore, Cloud Storage, and Cloud Functions**.

------------------------------------------------------------------------

## 🚀 Features

-   **Campaign & Promotion Management**
    -   Create, update, and track campaigns & promotions with linked
        budgets.
    -   Automatic performance updates (impressions, clicks, conversions,
        ROI, etc.).
-   **Budget Guardrails**
    -   Monitors overspending (`amount_left < 0`) and suggests pausing
        or reallocating.
    -   Supports predefined daily costs for multiple ad platforms.
-   **Data-Driven Insights**
    -   Analyzes BigQuery data (customers, orders, products) for trends
        and opportunities.
    -   Recommends promotions, campaigns, and target audiences.
-   **Business Config & Strategies**
    -   Centralized storage of **business configuration** and
        **strategies** in Cloud Storage.
    -   Full CRUD support (create, read, update, delete).
-   **Proactive Assistant**
    -   Suggests actions based on data (e.g., overspending budgets,
        top-selling products).
    -   Creative but grounded recommendations.

------------------------------------------------------------------------

## 🛠️ Architecture

-   **BigQuery** → Data analytics (customers, orders, products). (inspired from Google's Example ADK Big Query Agent Example. Tailored the BigQuery tool according to our needs.)
-   **Firestore** → Stores campaigns, promotions, budgets, audience
    groups.
-   **Cloud Storage** → Stores `business_config.json` and
    `strategies.json`.
-   **Cloud Functions** → Automates updates (e.g., campaign performance
    every 12 hours).
-   **PromoSphere Agent** → AI interface orchestrating all operations.
- **Seach Agent** → Searches using ADK's built in search tool.


------------------------------------------------------------------------

## 📂 Firestore Collections

-   **budgets**
-   **promotions**
-   **campaigns**
-   **audience_groups**

Each collection supports structured fields with `performanceData`
objects for tracking effectiveness.

------------------------------------------------------------------------

## ⚡ Cloud Function: Performance Updater

A scheduled Cloud Function runs every **12 hours** to: - Query all
campaigns & promotions. - Update or insert `performanceData` fields with
realistic metrics. - Adjust linked budgets accordingly.

------------------------------------------------------------------------

## 📊 Daily Cost Defaults

-   google_search: 120
-   youtube: 80
-   tiktok: 60
-   instagram: 70
-   facebook: 65
-   x_twitter: 40
-   linkedin: 90
-   display: 50
-   email: 20
-   sms: 15

------------------------------------------------------------------------

## ▶️ Demo Workflow

1.  **Ask for a campaign idea**: "Create a weekend campaign targeting
    customers who ordered in the last month."
2.  **PromoSphere suggests** audience group, budget, and promotion.
3.  **User approves → Firestore updated.**
4.  **Performance monitored & budgets auto-adjusted.**

------------------------------------------------------------------------

## 📌 Setup

1.  Clone the repo.
2.  Configure Google Cloud project & authentication.
3.  Deploy Firestore, BigQuery datasets, and Cloud Storage buckets.
4.  Deploy Cloud Function `update_performance_data`.
5.  Run PromoSphere agent.

------------------------------------------------------------------------