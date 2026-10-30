# 🚀 CBIT Hacktoberfest '26 — Project Starter Repository

> **Official Public Starter Repository for CBIT Hacktoberfest '26**  
> *Chaitanya Bharathi Institute of Technology (CBIT), Hyderabad*

---

## 📋 Team Information

| Attribute | Details |
| :--- | :--- |
| **Team Name** | **Fork Knights** |
| **Team Number** | `TEAM-28` (`HFT26-TEAM-28`) |
| **Registration ID** | `HFEST26-BYPPL4R8` |
| **Problem Track** | **Track Selection in Progress** |
| **Domain** | `General Track` |
| **Team Leader** | Yuvaraj Tirumalasetty (yuvaraj.trsy@gmail.com) |
| **Institution** | VNR Hyderabad |

### 👥 Team Members

| # | Name | Email | Institution |
| :--- | :--- | :--- | :--- |
| 1 | Gogula Ajitesh | gamingajitesh9@gmail.com | VNR Hyderabad |
| 2 | A. Srikar | srikarreddy4538@gmail.com | VNR Hyderabad |
| 3 | Tejasvi Acharya | bhattertejasvi27@gmail.com | VNR Hyderabad |
| 4 | Utkarsh S | usingh51219@gmail.com | VNR Hyderabad |

---

## 🎯 Problem Statement: CodeLens — Intelligent Repository Search

Large codebases are difficult for developers to explore quickly. Keyword search tools (like naive grep or text search) often match irrelevant comments, build artifacts, or strings while missing syntactic context.

**CodeLens** is a lightweight, AST-powered repository inspection tool that:
1. **Safely extracts** GitHub repository ZIP files (with Zip Slip prevention).
2. **Filters noise** by ignoring `node_modules`, `.git`, `build`, `dist`, `__pycache__`, and virtual environments.
3. **Parses Python syntax trees (AST)** to extract exact functions, methods, classes, signatures, docstrings, and line numbers.
4. **Ranks relevant definitions** using a transparent multi-signal scoring algorithm.
5. **Displays actual code and line ranges** (`L{start}–L{end}`) with syntax highlighting.
6. **Explains search relevance** using a dual-mode engine: works 100% out of the box with zero external dependencies via AST heuristics, with optional LLM API support (Gemini/OpenAI) if an API key is configured.
7. **Exports the indexed codebase** to portable JSON.

---

## ⚡ Quick Start & How to Run

### 1. Install Dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2. Launch CodeLens Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 3. Run Automated Tests
```bash
python3 -m unittest discover tests/
python3 tests/verify_e2e.py
```

---

## 🏗️ Architecture & Project Structure

```
CBITHACKATHON-28/
├── app.py                     # Streamlit web interface & developer dashboard
├── requirements.txt           # Minimal dependencies (streamlit, requests)
├── sample_repo.zip            # Built-in demo repository for 1-click evaluation
├── core/
│   ├── scanner.py             # Safe ZIP extraction & Python AST code parser
│   ├── search.py              # Keyword search & relevance ranking engine
│   └── explainer.py           # Dual-mode relevance explainer (Heuristic + Optional LLM)
├── tests/
│   ├── test_codelens.py       # Unit tests for AST, safety, search & explanations
│   ├── verify_e2e.py          # End-to-end pipeline verification script
│   └── create_sample_zip.py   # Script to package sample_repo.zip
└── README.md                  # Project documentation
```

---

## 🛠️ Contribution & Submission Workflow

All teams must follow the official fork-and-pull-request workflow:

1. **Fork this Repository**:
   - One team member should click the **Fork** button at the top right to fork this upstream repository to your personal/team GitHub account.
2. **Add Collaborators**:
   - In your forked repository, navigate to **Settings > Collaborators** and invite all your registered team members.
3. **Clone & Develop Locally**:
   ```bash
   git clone https://github.com/<your-username>/HFT26-TEAM-28.git
   cd HFT26-TEAM-28
   git checkout -b feature/prototype
   ```
4. **Commit & Push Regularly**:
   - Make atomic, descriptive commits throughout the hackathon.
   ```bash
   git add .
   git commit -m "feat: implement core solution architecture"
   git push origin feature/prototype
   ```
5. **Open Pull Request (PR) for Final Submission**:
   - When ready for evaluation, open a **Pull Request** from your fork's `main` branch back to this upstream repository's `main` branch.
   - **PR Title Format**: `[SUBMISSION] TEAM-28 - Fork Knights - Track Selection in Progress`
   - **PR Description Checklist**:
     - 📌 Solution Overview & Approach
     - 🏗️ Architecture & Tech Stack Details
     - 🚀 Local Setup & Installation Instructions
     - 🎥 Demo Video Link / Live Deployment URL
     - 📸 Key Screenshots & Visuals

---

## 📁 Recommended Project Structure

```
.
├── src/                  # Source code (Frontend / Backend / ML)
├── docs/                 # Documentation, architecture diagrams, slides
├── tests/                # Test suites & verification scripts
├── README.md             # Your project documentation & presentation
└── LICENSE               # Open-source license (MIT recommended)
```

---

## ⚠️ Important Rules & Code of Conduct
* **Upstream Protection**: Do not push directly to this repository's main branch. All evaluation will be conducted on your submitted Pull Request.
* **Original Work**: All code submitted must be developed during the hackathon timeline. Open-source libraries and frameworks are welcomed with proper attribution.
* **Code Freeze**: Final Pull Requests must be submitted before the designated hackathon submission deadline.
