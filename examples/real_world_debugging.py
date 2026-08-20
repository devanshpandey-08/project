"""
Real-World Example: Debugging a 10-Node Flow That Fails at Step 7

This is what developers actually care about - not microsecond optimizations.
"""

import asyncio
from flomind import FlowBuilder, State, RetryPolicy

# Simulate a real production workflow
async def fetch_user_data(state: State) -> State:
    """Step 1: Fetch user from DB"""
    await asyncio.sleep(0.05)
    return state.update(user={"id": 123, "name": "Alice"})

async def validate_user(state: State) -> State:
    """Step 2: Validate user exists"""
    await asyncio.sleep(0.01)
    if not state.data.get("user"):
        raise ValueError("User not found")
    return state.update(validated=True)

async def fetch_preferences(state: State) -> State:
    """Step 3: Get user preferences"""
    await asyncio.sleep(0.05)
    return state.update(preferences={"theme": "dark"})

async def check_permissions(state: State) -> State:
    """Step 4: Check user permissions"""
    await asyncio.sleep(0.02)
    return state.update(permissions=["read", "write"])

async def fetch_documents(state: State) -> State:
    """Step 5: Get user documents"""
    await asyncio.sleep(0.1)
    return state.update(documents=[{"id": 1, "title": "Doc1"}])

async def analyze_documents(state: State) -> State:
    """Step 6: Analyze with LLM"""
    await asyncio.sleep(0.5)
    return state.update(analysis="Documents are valid")

async def generate_summary(state: State) -> State:
    """Step 7: Generate summary (THIS FAILS in production)"""
    await asyncio.sleep(0.3)
    if state.data.get("attempt_count", 0) == 0:
        state = state.update(attempt_count=1)
        raise Exception("Rate limit exceeded")
    return state.update(summary="Generated summary here")

async def save_results(state: State) -> State:
    """Step 8: Save to database"""
    await asyncio.sleep(0.05)
    return state.update(saved=True)

async def notify_user(state: State) -> State:
    """Step 9: Send notification"""
    await asyncio.sleep(0.02)
    return state.update(notified=True)

async def log_completion(state: State) -> State:
    """Step 10: Log completion"""
    await asyncio.sleep(0.01)
    return state.update(completed_at="2024-01-01T00:00:00Z")


async def main():
    print("=" * 80)
    print("REAL-WORLD SCENARIO: 10-Node Flow Failing at Step 7")
    print("=" * 80)
    
    flow = (FlowBuilder("user_workflow")
        .add_node("fetch_user", fetch_user_data)
        .add_node("validate_user", validate_user)
        .add_node("fetch_prefs", fetch_preferences)
        .add_node("check_perms", check_permissions)
        .add_node("fetch_docs", fetch_documents)
        .add_node("analyze", analyze_documents)
        .add_node("generate_summary", generate_summary, retry_policy=RetryPolicy(max_retries=3))
        .add_node("save", save_results)
        .add_node("notify", notify_user)
        .add_node("log", log_completion)
        .build())
    
    print("\n🚀 Executing flow (will fail at step 7, then retry)...")
    initial_state = State(data={})
    
    try:
        result_state = await flow.execute(initial_state)
        print("\n✅ Flow completed successfully after retry!")
        print(f"   Final state keys: {list(result_state.data.keys())}")
        
        print("\n📊 EXECUTION TRACE:")
        for snapshot in result_state.history[-5:]:
            print(f"   Step {snapshot.step}: {snapshot.node_id} - {snapshot.status}")
            if snapshot.error:
                print(f"      Error: {snapshot.error}")
        
    except Exception as e:
        print(f"\n❌ Flow failed: {e}")
    
    print("\n" + "=" * 80)
    print("KEY TAKEAWAY: When flows fail, you need:")
    print("  1. Full state history (what happened at steps 1-6)")
    print("  2. Automatic retry with backoff (step 7 succeeds on retry)")
    print("  3. Replay capability (resume from checkpoint)")
    print("  4. Clear error messages")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
