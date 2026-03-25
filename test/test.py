import os
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# Point to LiteLLM proxy (not Anthropic)
os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:4000"
os.environ["ANTHROPIC_API_KEY"] = "dummy"  # LiteLLM ignores it

# Configure agent with a model from your LiteLLM config.yaml
options = ClaudeAgentOptions(
    system_prompt="You are a helpful AI assistant.",
    model="gpt5",  # nombre del modelo en config.yaml
    max_turns=20
)

async def main():
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Explain what LiteLLM does in one paragraph")
        
        async for msg in client.receive_response():
            if hasattr(msg, 'content'):
                for content_block in msg.content:
                    if hasattr(content_block, 'text'):
                        print(content_block.text, end='', flush=True)

asyncio.run(main())