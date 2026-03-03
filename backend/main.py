import sys
import os
import base64
import json
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "agent-core"))

from fastapi import FastAPI, HTTPException
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time

from dotenv import load_dotenv
from playwright.async_api import async_playwright

env_path = Path(__file__).parent / ".ENV"
load_dotenv(env_path)

from google import genai
from google.genai import types

# Import shared models
from interfaces import AgentBackend, VisionAnalysis, ActionPlan, UIAction, ExecutionResult

app = FastAPI(title="GCP Gemini Provider")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GcpGeminiAgent(AgentBackend):
    def __init__(self):
        self.api_key = os.getenv("BACKEND_GEMINI_PY_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            print("WARNING: BACKEND_GEMINI_PY_KEY not set in .ENV")
            
        self.playwright = None
        self.browser = None
        self.page = None
        self._lock = asyncio.Lock()

    async def initialize_browser(self):
        async with self._lock:
            if not self.playwright:
                self.playwright = await async_playwright().start()
            
            # Check if browser is actually open and connected
            browser_active = False
            if self.browser:
                try:
                    # A simple check to see if the browser is still responsive
                    await self.browser.version()
                    browser_active = True
                except:
                    browser_active = False

            if not browser_active:
                print("Initializing new browser instance...")
                # Run non-headless so user can see it interacting!
                self.browser = await self.playwright.chromium.launch(headless=False)
                context = await self.browser.new_context()
                self.page = await context.new_page()
                # For demonstration, starting at Google
                await self.page.goto("https://www.google.com")
                print("Browser initialized and navigated to Google.")

    async def analyze_vision(self, screenshot: str) -> VisionAnalysis:
        if not self.client:
            return VisionAnalysis(description="Gemini API Key missing.", elements=[])
            
        try:
            image_data = base64.b64decode(screenshot)
            response = self.client.models.generate_content(
                model=os.getenv("GEMINI_MODEL_NAME"),
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type='image/jpeg'),
                    "Describe this screen in exactly 2-3 very short and simple sentences. Avoid lists or details. Just tell me the main thing I'm looking at and where the search or login bar is."
                ]
            )
            return VisionAnalysis(
                description=response.text or "No description from model.",
                elements=[{"type": "info", "message": "Vision analysis complete"}]
            )
        except Exception as e:
            return VisionAnalysis(description=f"Error analyzing vision: {str(e)}", elements=[])

    async def plan_workflow(self, goal: str, context: VisionAnalysis, history: list[str] = None) -> ActionPlan:
        if not self.client:
            return ActionPlan(steps=[], reasoning="Gemini API Key missing.")

        # Extract visible interactive DOM elements for 100% reliable selectors
        dom_context = "No DOM available."
        if self.page:
            try:
                dom_context = await self.page.evaluate("""() => {
                    let elements = [];
                    // Look for interactive elements + data-attributes common in SaaS filters
                    document.querySelectorAll('a, button, input, select, option, [role="button"], li.s-navigation-item').forEach(el => {
                        let rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= window.innerHeight + 500) {
                            let id = el.id ? '#' + el.id : '';
                            let text = el.innerText ? el.innerText.trim().replace(/\\n/g, ' ').substring(0, 50) : '';
                            let placeholder = el.placeholder ? ` placeholder="${el.placeholder}"` : '';
                            let aria = el.getAttribute('aria-label') ? ` aria="${el.getAttribute('aria-label')}"` : '';
                            let selected = el.selected || el.getAttribute('aria-checked') === 'true' || el.classList.contains('s-facet-selected') ? ' [ACTIVE/SELECTED]' : '';
                            
                            // Build a robust CSS selector
                            let selector = el.tagName.toLowerCase();
                            if (id) selector += id;
                            else if (el.name) selector += `[name="${el.name}"]`;
                            
                            elements.push(`Selector: \`${selector}\` | Text: "${text}"${placeholder}${aria}${selected}`);
                        }
                    });
                    return elements.slice(0, 80).join('\\n');
                }""")
            except Exception as e:
                dom_context = f"Failed to extract DOM: {str(e)}"

        history_text = "\n".join(history[-5:]) if history else "None"

        prompt = f"""Goal: {goal}
Context: {context.description}
Recent Action History:
{history_text}

Visible Interactive DOM Elements Extract:
{dom_context}

You are an advanced Browser Assistant Agent operating on behalf of a user.
Based ONLY on the CURRENT screenshot, the Visible DOM Elements above, and Recent Action History, what is the immediate NEXT logical action to take?

STRATEGY FOR THIS TASK:
1. Follow the user's instructions EXACTLY. Do not add extra filters or steps that the user didn't ask for.
2. If the user asks to "find" and "sort" items, once you have performed the search and applied the correct sort, THE TASK IS COMPLETE. Do not try to click into products unless they specifically asked to "buy", "view details", or "select" a product.
3. If you see an element marked '[ACTIVE/SELECTED]' in the DOM extract that matches the requested sort/filter, it is already applied.
4. If an action fails multiple times, try a different approach or a different element that achieves the same goal.

IMPORTANT:
- Output only 1 step at a time.
- For 'target', prefer the exact CSS selector from the DOM list provided above.
- For 'reasoning', explain what you are doing in very simple terms.
- Use 'action_type' of: 'goto', 'click_element', 'type_text', 'select_dropdown', or 'press_key'.
Return a valid JSON. If the requested search and sort are visible, return an empty steps list [] to signal completion."""

        try:
            response = self.client.models.generate_content(
                model=os.getenv("GEMINI_MODEL_NAME"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ActionPlan,
                ),
            )
            try:
                return ActionPlan.model_validate_json(response.text)
            except Exception:
                data = json.loads(response.text)
                return ActionPlan(**data)
        except Exception as e:
            return ActionPlan(steps=[], reasoning=f"I'm sorry, I'm having trouble thinking of what to do next. (Error: {str(e)})")

    async def execute_ui_action(self, action: UIAction) -> ExecutionResult:
        if not self.page:
            await self.initialize_browser()
            
        try:
            if action.action_type == 'select_dropdown':
                locator = self.page.locator(action.target).first
                await locator.wait_for(state="visible", timeout=10000)
                await locator.select_option(action.value, timeout=5000)
                await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                msg = f"I selected '{action.value}' from the '{action.target}' dropdown."
                
            elif action.action_type == 'press_key':
                await self.page.keyboard.press(action.target)
                await asyncio.sleep(1)
                msg = f"I pressed the '{action.target}' key on the keyboard."
                
            elif action.action_type == 'click_element':
                locator = self.page.locator(action.target).first
                await locator.wait_for(state="visible", timeout=10000)
                # Scroll into view if needed
                await locator.scroll_into_view_if_needed()
                await locator.click(timeout=5000)
                
                try:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=4000)
                except:
                    pass
                # Try to get a friendly name for the element
                try:
                    element_text = await locator.inner_text()
                    element_text = element_text.strip().split('\n')[0][:30]
                    if not element_text:
                        element_text = await locator.get_attribute("aria-label") or await locator.get_attribute("placeholder") or action.target
                except:
                    element_text = action.target
                
                msg = f"I clicked on '{element_text}'"
                
            elif action.action_type == 'type_text':
                locator = self.page.locator(action.target).first
                await locator.wait_for(state="visible", timeout=10000)
                await locator.scroll_into_view_if_needed()
                await locator.fill(action.value or '', timeout=5000)
                await locator.press('Enter')
                
                try:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=4000)
                except:
                    pass
                # Try to get a friendly name for the element
                try:
                    element_label = await locator.get_attribute("placeholder") or await locator.get_attribute("aria-label") or action.target
                except:
                    element_label = action.target

                msg = f"I typed '{action.value}' into the {element_label} field."

            elif action.action_type == 'goto':
                await self.page.goto(action.target, timeout=15000)
                msg = f"I went to the website: {action.target}"
                
            else:
                await asyncio.sleep(1)
                msg = f"Simulated {action.action_type} for {action.target}"
                
            return ExecutionResult(success=True, message=msg)
            
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            return ExecutionResult(success=False, message=f"I ran into a problem while trying that step: {err_msg}")

    async def generate_voice(self, text: str) -> str:
        # Stub for Gemini Live / TTS
        return f"http://dummy-audio-url.com/gemini.mp3?t={text}"

    async def interrupt_handler(self) -> None:
        async with self._lock:
            print("Gemini Agent Interrupted")
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
            # Reset everything so it can be re-initialized cleanly
            self.browser = None
            self.page = None
            # Keep playwright alive to speed up re-init, but we could also stop it
            # if self.playwright: await self.playwright.stop(); self.playwright = None

agent = GcpGeminiAgent()

@app.on_event("startup")
async def startup_event():
    await agent.initialize_browser()

class GoalRequest(BaseModel):
    goal: str
    screenshot: str # base64
    history: list[str] = []

@app.post("/plan")
async def plan_endpoint(req: GoalRequest):
    vision = await agent.analyze_vision(req.screenshot)
    plan = await agent.plan_workflow(req.goal, vision, req.history)
    return {"plan": plan, "vision": vision}

@app.post("/execute")
async def execute_endpoint(action: UIAction):
    result = await agent.execute_ui_action(action)
    return result

@app.post("/interrupt")
async def interrupt_endpoint():
    await agent.interrupt_handler()
    return {"message": "Agent interrupted successfully"}

@app.get("/")
def read_root():
    return {"message": "GCP Gemini Provider APIs active"}

@app.get("/screenshot")
async def get_screenshot():
    if not agent.page:
        try:
            await agent.initialize_browser()
        except Exception as e:
            print(f"Failed to initialize browser on screenshot request: {str(e)}")
            return {"screenshot": None}
            
    try:
        image_bytes = await agent.page.screenshot(type="jpeg", quality=50)
        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
        return {"screenshot": base64_encoded}
    except Exception as e:
        print(f"Failed to capture screenshot: {str(e)}")
        # If screenshot fails, maybe the browser crashed. Reset state so it can re-init next time.
        agent.page = None
        return {"screenshot": None}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
