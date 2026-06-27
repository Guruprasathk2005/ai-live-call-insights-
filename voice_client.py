import asyncio
import websockets
import json
import speech_recognition as sr

recognizer = sr.Recognizer()
microphone = sr.Microphone()

def listen_from_microphone() -> str:
    """Capture voice from mic and convert to text using Google Speech Recognition (free)."""
    with microphone as source:
        print("\n🎤 Listening... (speak now)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            print("   [Could not understand audio, try again]")
            return ""
        except sr.RequestError as e:
            print(f"   [Speech Recognition error: {e}]")
            return ""


async def voice_call():
    uri = "ws://127.0.0.1:8000/ws/live-call"
    print(f"\n{'='*55}")
    print("   🤖 AI LIVE CALL ASSISTANT")
    print(f"{'='*55}")
    print("   Speak your question after the prompt.")
    print("   Say 'goodbye' or 'exit' to end the call.")
    print(f"{'='*55}\n")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to AI Call Engine!\n")

            while True:
                # Step 1: Capture voice
                spoken_text = listen_from_microphone()

                if not spoken_text:
                    continue

                print(f"📝 You said: \"{spoken_text}\"")

                # Step 2: Check for exit command
                if any(word in spoken_text.lower() for word in ["goodbye", "exit", "bye", "quit", "end call"]):
                    print("\n👋 Ending call...")
                    break

                # Step 3: Send to server
                await websocket.send(json.dumps({"text": spoken_text}))

                # Step 4: Receive AI response
                response = await websocket.recv()
                data = json.loads(response)

                analysis = data["realtime_analysis"]
                answer = data["answer"]

                print(f"\n🤖 AI Answer: {answer}")
                print(f"   └─ [Sentiment]: {analysis.get('sentiment')} | "
                      f"[Urgent]: {analysis.get('urgent_flag')} | "
                      f"[Intent]: {analysis.get('intent')}\n")
                print("-" * 55)

    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        print("   Make sure app.py server is running in Terminal 1.")

    print("\n📋 Call ended. Check Terminal 1 for the full Call Summary Report.")


if __name__ == "__main__":
    asyncio.run(voice_call())
