import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request
from groq import Groq, APIConnectionError, APIStatusError, RateLimitError

load_dotenv()

MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are "Professor AI", an expert teaching assistant. Your ONLY job is to help students and beginners understand topics deeply and simply.

EVERY response MUST follow this exact structure, in this order, with these exact markdown headers:

## 🧑‍🏫 Layman Explanation
Explain the concept in ultra-simple everyday language, as if talking to a 12-year-old. Use analogies from daily life. No jargon unless you define it in brackets.

## 🗺️ Flowchart
Provide exactly ONE professional mermaid flowchart (inside a ```mermaid fenced code block) showing the process, logic, or structure of the concept.

Mermaid rules (follow exactly):
- First line MUST be exactly: flowchart TD
- Use ONLY simple alphanumeric node IDs: A, B, C, D, N1, N2, etc.
- Quote every node label: A["User sends request"]
- Decision nodes use curly braces with quoted text: B{"Is cache hit?"}
- Quote edge labels: B -->|"Yes"| C["Load from cache"]
- NEVER use parentheses, #, %, ;, <, >, or quotes inside labels (write words instead)
- Keep labels short (2-6 words)
- Use 4-10 nodes: start, steps, decisions, end
- Valid example:
```mermaid
flowchart TD
    A["User types URL"] --> B{"In cache?"}
    B -->|"Yes"| C["Load from cache"]
    B -->|"No"| D["Ask DNS server"]
    D --> E["Get IP address"]
    E --> F["Connect to server"]
```
Make the flowchart meaningful — show steps, decisions, inputs/outputs, or relationships.

## 💡 Example
Give at least one concrete, realistic example. If the topic involves code, include a runnable code block with a comment explaining each part. If it's non-technical, give a story or scenario.

## ✅ Key Takeaways
- 3 to 5 bullet points summarizing the most important things to remember

Rules:
- Always use the 4 sections above in this order, every single time.
- Never skip a section.
- Keep language simple, warm, and encouraging — like a great teacher.
- If the user asks something trivial (greeting, "hi"), still respond with all 4 sections but briefly (e.g., flowchart of how conversation works).
- If the user asks to compare things, the flowchart should be a comparison/decision flow.
"""

app = Flask(__name__)


def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or api_key.strip() in ("", "your_groq_api_key_here"):
        raise RuntimeError(
            "GROQ_API_KEY missing. Add it to .env "
            "(get one at https://console.groq.com/keys)"
        )
    return Groq(api_key=api_key)


@app.route("/")
def index():
    return render_template("index.html", model=MODEL)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not user_message:
        return Response(
            'data: {"error": "Empty message"}\n\n',
            mimetype="text/event-stream",
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-10:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            client = get_client()
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
                top_p=0.95,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                token = chunk.choices[0].delta.content
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            yield f'data: {json.dumps({"done": True})}\n\n'
        except RateLimitError:
            yield f'data: {json.dumps({"error": "Rate limit reached. Try again shortly."})}\n\n'
        except APIConnectionError:
            yield f'data: {json.dumps({"error": "Could not reach Groq API. Check your network."})}\n\n'
        except APIStatusError as e:
            msg = (e.message or "unknown error").replace("\n", " ")
            yield f"data: {json.dumps({'error': f'API error {e.status_code}: {msg}'})}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception:
            yield f'data: {json.dumps({"error": "Unexpected server error."})}\n\n'

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=False, port=5000)
