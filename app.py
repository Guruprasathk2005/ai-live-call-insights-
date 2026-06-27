import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from groq import AsyncGroq, RateLimitError

load_dotenv()

app = FastAPI(title="AI Live Call Insights Engine")

api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
    print("\n[🚨 WARNING]: GROQ_API_KEY is not configured in your .env file!\n")

client = AsyncGroq(api_key=api_key)
MODEL = "llama-3.3-70b-versatile"

INSIGHT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_insight",
        "description": "Extract structured real-time insight from a live call transcript chunk.",
        "parameters": {
            "type": "object",
            "properties": {
                "sentiment": {
                    "type": "string",
                    "description": "Customer Sentiment: one of Positive, Neutral, Negative, or Escalated"
                },
                "intent": {
                    "type": "string",
                    "description": "Core Intent / Main Problem (brief summary)"
                },
                "urgent_flag": {
                    "type": "boolean",
                    "description": "True if immediate supervisor intervention is needed, otherwise False"
                }
            },
            "required": ["sentiment", "intent", "urgent_flag"]
        }
    }
}


async def analyze_chunk(transcript_chunk: str, retries: int = 3, delay: float = 5.0) -> dict:
    for attempt in range(retries):
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert AI operations supervisor monitoring a live call. "
                            "Analyze the incoming transcript chunk and extract the required fields "
                            "by calling the extract_insight tool."
                        )
                    },
                    {"role": "user", "content": transcript_chunk}
                ],
                tools=[INSIGHT_TOOL],
                tool_choice={"type": "function", "function": {"name": "extract_insight"}},
                max_tokens=512
            )
            tool_call = response.choices[0].message.tool_calls[0]
            return json.loads(tool_call.function.arguments)

        except RateLimitError:
            if attempt < retries - 1:
                print(f"[RATE LIMIT] Retrying in {delay}s... (attempt {attempt + 1}/{retries})")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise


async def answer_question(question: str, conversation_history: list, retries: int = 3, delay: float = 5.0) -> str:
    """Generate a helpful AI answer to the user's spoken question."""
    for attempt in range(retries):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and friendly AI customer support assistant on a live call. "
                        "Answer the customer's question clearly and concisely in 2-3 sentences. "
                        "Be empathetic and professional."
                    )
                }
            ] + conversation_history + [
                {"role": "user", "content": question}
            ]

            response = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=256
            )
            return response.choices[0].message.content

        except RateLimitError:
            if attempt < retries - 1:
                print(f"[RATE LIMIT] Retrying in {delay}s... (attempt {attempt + 1}/{retries})")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise


async def generate_summary(full_transcript: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an advanced quality assurance engine. Review the entire transcript. "
                    "Generate an executive summary containing:\n"
                    "1. Call Overview\n"
                    "2. Key Customer Pain Points\n"
                    "3. Agent Performance / Resolution Status\n"
                    "4. Recommended Actionable Next Steps"
                )
            },
            {
                "role": "user",
                "content": f"Full Call Transcript:\n{full_transcript}"
            }
        ],
        max_tokens=1024
    )
    return response.choices[0].message.content


class CallSession:
    def __init__(self):
        self.full_transcript: list[str] = []
        self.conversation_history: list[dict] = []

    def add_exchange(self, question: str, answer: str):
        self.full_transcript.append(f"User: {question}")
        self.full_transcript.append(f"Agent: {answer}")
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer})

    def get_full_text(self) -> str:
        return "\n".join(self.full_transcript)


@app.websocket("/ws/live-call")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = CallSession()
    print("\n[CONNECTED] Live voice call session started.")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            transcript_chunk = payload.get("text", "").strip()

            if not transcript_chunk:
                continue

            print(f"\n[USER SPOKE]: {transcript_chunk}")

            # Step 1: Analyze sentiment and intent
            try:
                analysis = await analyze_chunk(transcript_chunk)
            except Exception as e:
                print(f"[ANALYSIS ERROR]: {e}")
                analysis = {"sentiment": "Unknown", "intent": "Error", "urgent_flag": False}

            # Step 2: Generate AI answer
            try:
                answer = await answer_question(transcript_chunk, session.conversation_history)
            except Exception as e:
                print(f"[ANSWER ERROR]: {e}")
                answer = "I'm sorry, I'm having trouble processing your request right now."

            # Step 3: Save to session
            session.add_exchange(transcript_chunk, answer)

            print(f"[AI ANSWER]: {answer}")

            # Step 4: Send everything back to client
            await websocket.send_json({
                "chunk": transcript_chunk,
                "answer": answer,
                "realtime_analysis": analysis
            })

    except WebSocketDisconnect:
        print("\n[DISCONNECTED] Call ended. Generating call summary...")
        full_text = session.get_full_text()

        if full_text:
            try:
                summary = await generate_summary(full_text)
                print("\n" + "=" * 50 + "\nCALL SUMMARY REPORT\n" + "=" * 50)
                print(summary)
                print("=" * 50 + "\n")
            except Exception as e:
                print(f"[SUMMARY ERROR]: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
