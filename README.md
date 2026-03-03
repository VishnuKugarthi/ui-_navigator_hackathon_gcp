# Agentic UI Navigator

**Submission for the Gemini Live Agent Challenge & Amazon Nova Hackathon**

**Category:** UI Navigator (Focus: Visual UI Understanding & Interaction)

**The Hack:** We built an agent that becomes the user's hands on screen. The agent observes the browser or device display and interprets visual elements **without relying on DOM access**. Using Gemini 2.0 Flash's spatial understanding, it acts as a pure vision model to calculate XY coordinate clicks and manipulate a real headless Playwright browser to execute complex user intents autonomously.

## 🏗️ Architecture Diagram
*(Make sure to upload an image of your architecture diagram to Devpost as required!)*
**Flow:**
1. **React Frontend**: Captures screen frame every 500ms and records user audio via Web Speech API.
2. **FastAPI Backend (Google Cloud Run)**: Orchestrates the AI Agent and holds a stateful Playwright Chromium session.
3. **Gemini 2.0 Flash API**: Takes the user goal & the screenshot, outputs a spatial `[y, x]` array mapped to the UI element.
4. **Playwright Execution**: Converts the normalized coordinate to a physical mouse move and click.

## 🚀 How to Run Locally

### Prerequisites
- Node.js v18 or higher
- Python v3.9 or higher
- `playwright` dependencies

### 1. Setup Frontend
```bash
cd shared-core/frontend
npm install
npm run dev
```
Available at `http://localhost:5173`.

### 2. Setup GCP Gemini Backend (Port 8002)
```bash
cd providers/gcp-gemini
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```
Create a `.ENV` file in `providers/gcp-gemini` with your Gemini key:
`BACKEND_GEMINI_PY_KEY="AIza..."`
`GEMINI_MODEL_NAME="gemini-2.0-flash"`

Start the server:
```bash
python main.py
```

## ☁️ Google Cloud Deployment (Bonus Points!)
As required by the hackathon, the agent backend must be hosted on Google Cloud. We have written a 1-click **Infrastructure as Code automation script** (`deploy.sh`) to effortlessly push the Agent backend to **Google Cloud Run**.

1. Ensure you have the `gcloud` CLI installed and authenticated.
2. Ensure you have set an active project: `gcloud config set project YOUR_PROJECT_ID`
3. Make the script executable from the root of the repository:
```bash
chmod +x deploy.sh
./deploy.sh
```

This script automatically copies the shared interfaces into the docker context, packages the Microsoft Playwright headless container via `Dockerfile`, and securely deploys it to a managed Cloud Run instance.

## 🎥 Demonstration Video
*(Link your 4-minute maximum YouTube demo video here on Devpost, showing the UI acting WITHOUT mockups!)*

## 💡 How to Use the Application
1. **Visit the Dashboard**: Hit the running React frontend.
2. **Start Screen Capture**: The left panel will poll our GCP Python backend and display a literal live video feed of the headless Playwright window.
3. **Voice Command**: Click "Start Listening" and give it an intent (e.g., "Give me a list of double door refrigerators and sort by price low to high").
4. **Agentic Loop**: The app autonomously loops: capturing a frame, calling Gemini to predict screen coordinates without looking at the HTML DOM, and physically dragging the mouse to complete tasks. It automatically stops when the goal is achieved!
