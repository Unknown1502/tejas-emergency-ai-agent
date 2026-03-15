"""Quick smoke test for the Tejas /ws/stream WebSocket endpoint (direct GenAI SDK path)."""
import asyncio
import json
import sys

async def test_adk_websocket():
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "--quiet"])
        import websockets

    url = "wss://tejas-backend-ic3swxkwda-uc.a.run.app/ws/stream"
    print(f"Connecting to: {url}")

    try:
        async with websockets.connect(url, ping_interval=None, open_timeout=30) as ws:
            print("✅ WebSocket connected!")

            # Send session_init
            init_msg = json.dumps({
                "type": "session_init",
                "data": {
                    "incident_id": "test_smoke_001",
                    "gps_lat": 37.4219983,
                    "gps_lng": -122.084
                }
            })
            await ws.send(init_msg)
            print("Sent session_init")

            # Wait for up to 15 seconds to get a response
            import asyncio
            received = []
            deadline = asyncio.get_event_loop().time() + 15

            while asyncio.get_event_loop().time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    msg_type = data.get("type", "?")
                    received.append(msg_type)
                    print(f"  → Received: {msg_type}: {json.dumps(data)[:120]}")

                    # Check if we got the connected + session_initialized flow
                    if msg_type in ("status", "connected"):
                        status_data = data.get("data", {})
                        status_val = status_data.get("status", "")
                        if status_val in ("connected", "session_initialized"):
                            print(f"\n✅ Stream session started successfully! Status: {status_val}")
                            if status_val == "session_initialized":
                                print("✅ /ws/stream session fully initialized - WebSocket pipeline is WORKING!")
                                break
                except asyncio.TimeoutError:
                    print("  (5s timeout, waiting for more messages...)")
                    if received:
                        break

            if received:
                print(f"\n✅ RESULT: Received {len(received)} messages: {received}")
            else:
                print("\n❌ RESULT: No messages received within 15 seconds")

    except Exception as e:
        print(f"\n❌ Connection FAILED: {type(e).__name__}: {e}")
        return False

    return True

if __name__ == "__main__":
    result = asyncio.run(test_adk_websocket())
    sys.exit(0 if result else 1)
