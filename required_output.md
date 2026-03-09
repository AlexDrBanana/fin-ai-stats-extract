**Category 1: Firms' AI Investments**

Three sub-categories, each with the same output structure:

**1a. AI Infrastructure** (Data centers, chips, hardware, cloud compute, etc.)

* ai\_infra\_binary: 1/0 — does the firm mention investment in AI infrastructure?
* ai\_infra\_types: list of unique types mentioned (no repetition)
* ai\_infra\_count: count of unique types
* **ai\_infra\_dollar**: dollar value invested (or NaN)

**1b. AI Analytics** (Models, algorithms, AI-powered applications/products, etc.)

* ai\_analytics\_binary: 1/0
* ai\_analytics\_types: list of unique types
* ai\_analytics\_count: count of unique types
* **ai\_analytics\_dollar**: dollar value invested (or NaN)

**1c. AI Human Capital** (Hiring AI/ML engineers, data scientists, AI research talent, etc.)

* ai\_talent\_binary: 1/0
* ai\_talent\_types: list of unique roles/talent areas
* ai\_talent\_count: count of unique types
* **ai\_talent\_dollar**: dollar value invested (or NaN)
* **ai\_talent\_headcount**: number of AI workers (or NaN)

**1d. AI Other — Risks/Barriers/Challenges**

* ai\_risk\_binary: 1/0 — does the firm mention AI-related risks, barriers, or challenges?
* ai\_risk\_types: list of unique risk/barrier themes (e.g., regulatory, ethical, technical debt, talent shortage)
* ai\_risk\_count: count of unique themes
* Optionally: ai\_risk\_sentiment: a severity or tone indicator (positive framing vs. negative framing)

**Category 2: Non-AI Technology/Innovation Investments**

**2a. Physical Investment** (R&D facilities, labs, tech equipment — excluding AI)

* tech\_phys\_binary: 1/0
* tech\_phys\_dollar: actual dollar value (extracted or NaN if not disclosed)

**2b. Tech Human Capital** (Software engineers, IT staff, non-AI tech roles)

* tech\_talent\_binary: 1/0
* tech\_talent\_headcount: number of people (or NaN)
* tech\_talent\_dollar: dollar value of investment (or NaN)