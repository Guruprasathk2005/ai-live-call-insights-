import asyncio
import websockets
import json

sample_chunks = [
    "Hello, thanks for calling customer support. My name is Alex. How can I help you today?",
    "Yeah, hi Alex. My internet service has been down since 6 AM and I'm missing critical work meetings.",
    "Sure, account number is 555-0199. Please hurry up, if I don't get online in 10 minutes I am going to lose a major contract!",
    "The emergency 5G hotspot pass worked. Yes, please activate that right away! Thank you so much.",
    "No, that's perfect. You saved my meeting. Thanks, Alex. Goodbye."
]

async def stream_call():
    uri = "ws://127.0.0.1:8000/ws/live-call"
    print(f"Connecting to live engine endpoint: {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Streaming speech recognition text blocks...\n")
            
            for chunk in sample_chunks:
                await asyncio.sleep(2.5)
                
                await websocket.send(json.dumps({"text": chunk}))
                response = await websocket.recv()
                data = json.loads(response)
                
                analysis = data["realtime_analysis"]
                print(f" Spoken Segment: \"{data['chunk']}\"")
                print(f"   └─ [Sentiment]: {analysis.get('sentiment')} | [Urgent]: {analysis.get('urgent_flag')} | [Intent]: {analysis.get('intent')}\n")
                
            print("All streams evaluated. Dropping socket connection...")
    except Exception as e:
        print(f"Connection aborted: {e}. Confirm your backend app.py server is up.")

if __name__ == "__main__":
    asyncio.run(stream_call())
