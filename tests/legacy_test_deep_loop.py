#!/usr/bin/env python3
"""
Manual tool-calling loop test for Noorak Search CLI with DeepSeek-V4-Flash on ArvanCloud.
"""
import os, json, urllib.request, ssl, subprocess, sys, time, shutil
from pathlib import Path

API_KEY = os.environ['NOORAK_API_KEY']
BASE_URL = os.environ['NOORAK_BASE_URL']
MODEL = os.environ['NOORAK_MODEL']

SCRIPT_DIR = Path('/workspace/Noorak-Search-CLI')
sys.path.insert(0, str(SCRIPT_DIR))

# Import TOOLS and helper functions
import importlib.util
spec = importlib.util.spec_from_file_location('ns', SCRIPT_DIR / 'noorak_search.py')
ns = importlib.util.module_from_spec(spec)
exec_globals = {}
with open(SCRIPT_DIR / 'noorak_search.py') as f:
    code = f.read()
toi = code.find('TOOLS = [')
depth = 0
end = toi
for i in range(toi, len(code)):
    if code[i] == '[': depth += 1
    elif code[i] == ']':
        depth -= 1
        if depth == 0:
            end = i + 1
            break
exec(f'TOOLS = {code[toi:end]}', exec_globals)
TOOLS = exec_globals['TOOLS']

# Import deepsearch helper
from noorak_search import run_deepsearch, exec_tool

def chat(messages, tools=None, tool_choice='auto', max_tokens=2000):
    payload = json.dumps({
        'model': MODEL, 'messages': messages,
        'tools': tools or TOOLS, 'tool_choice': tool_choice,
        'temperature': 0.4, 'max_tokens': max_tokens
    }).encode()
    req = urllib.request.Request(BASE_URL + '/chat/completions', data=payload,
        headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=90,
        context=ssl._create_unverified_context()).read()
    data = json.loads(resp)
    return data['choices'][0]['message']

def parse_tool_calls(msg):
    if 'tool_calls' in msg:
        return msg['tool_calls']
    content = msg.get('content', '')
    # Check if content mentions tool usage (fallback)
    if not content or not content.strip():
        return []
    return None  # No tool_calls key means model didn't use tools

def run_loop(query, max_iterations=6):
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    messages = [
        {'role': 'system', 'content': 'You are a deep research assistant. Use the available tools to search the web, fetch pages, and write a final Markdown report. Always call save_research at the end.'},
        {'role': 'user', 'content': query}
    ]
    
    for iteration in range(1, max_iterations + 1):
        print(f"\n--- Iteration {iteration} ---")
        msg = chat(messages, tool_choice='auto', max_tokens=2000)
        
        # Print response summary
        content = msg.get('content', '')[:200]
        print(f"Model says: {content}...")
        
        if 'tool_calls' not in msg:
            if content.strip():
                print("\nFinal answer (no more tools):")
                print(content)
                return content
            else:
                print("No tool calls and no content. Trying with different prompt...")
                break
        
        tool_calls = msg['tool_calls']
        print(f"Tool calls: {[tc['function']['name'] for tc in tool_calls]}")
        
        # Execute each tool call
        for tc in tool_calls:
            name = tc['function']['name']
            args = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']
            print(f"  Executing {name}({json.dumps(args, ensure_ascii=False)[:100]}...)")
            
            if name == 'web_search':
                result = exec_tool(name, args)
            elif name == 'fetch_page':
                result = exec_tool(name, args)
            elif name == 'pdna':
                # Call pdna tool
                p = subprocess.run([sys.executable, str(SCRIPT_DIR / 'pdna_tool.py')],
                    capture_output=True, text=True, timeout=30)
                result = p.stdout[-400:] if p.stdout else 'pdna tool executed'
            else:
                result = f"Unknown tool: {name}"
            
            # Add tool result to messages
            messages.append({
                'role': 'tool',
                'content': json.dumps({'tool_call_id': tc['id'], 'name': name, 'result': result[:2000]})
            })
            # Also add assistant's message with tool_calls back
            if len([m for m in messages if m['role'] == 'assistant']) == 0 or messages[-1]['role'] != 'assistant':
                pass  # assistant msg already in messages from first call
        
        # Add assistant message back (for proper conversation flow)
        # Actually need to add assistant response with tool_calls and tool results
        # Let's restructure: add assistant response, then tool results
        
        # Wait - actually we need to send the assistant's tool_calls back AND the tool results
        # Build proper messages:
        # 1. Original messages (user query)
        # 2. Assistant message with tool_calls
        # 3. Tool results
        
        # For next iteration, the chat function already received previous messages
        # Let's fix this by rebuilding properly
        
        # Add assistant tool call response
        messages.append(msg)  # assistant's tool_calls response
        
        # Now add tool results
        for tc in tool_calls:
            name = tc['function']['name']
            args = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']
            if name == 'web_search':
                result = exec_tool(name, args)
            elif name == 'fetch_page':
                result = exec_tool(name, args)
            else:
                result = f"Executed {name}"
            messages.append({
                'role': 'tool',
                'content': result[:2000] if isinstance(result, str) else str(result)[:2000]
            })
        
        # Now remove the duplicate assistant message we added
        # Actually let's restructure the loop
    
    return None

# Better approach: proper conversation flow
def run_loop_proper(query, max_iterations=8):
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    messages = [
        {'role': 'system', 'content': 'You are a deep research assistant. Use available tools (web_search, fetch_page, save_research) to find and analyze information. Call save_research when done.'},
        {'role': 'user', 'content': query}
    ]
    
    for iteration in range(1, max_iterations + 1):
        print(f"\n--- Iteration {iteration} ---")
        msg = chat(messages, tool_choice='auto', max_tokens=2000)
        print(f"Model: {msg.get('content', '')[:150]}")
        
        if 'tool_calls' not in msg or not msg['tool_calls']:
            if msg.get('content', '').strip():
                print("\n=== FINAL ANSWER ===")
                print(msg['content'])
            else:
                print("\nModel refused to use tools. Returning content.")
                print(msg.get('content', '(empty)'))
            return msg.get('content', '')
        
        tool_calls = msg['tool_calls']
        print(f"Tools called: {[tc['function']['name'] for tc in tool_calls]}")
        
        # Add assistant's tool_calls to messages
        messages.append(msg)
        
        # Execute each tool and add results
        for tc in tool_calls:
            name = tc['function']['name']
            args_str = tc['function']['arguments']
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
            
            print(f"  ➜ {name}({json.dumps(args, ensure_ascii=False)[:80]}...)")
            
            try:
                if name == 'web_search':
                    result = exec_tool(name, args)
                elif name == 'fetch_page':
                    result = exec_tool(name, args)
                else:
                    result = f"Tool {name} not executed locally"
                
                # Add tool result as tool message
                tool_result = {
                    'role': 'tool',
                    'content': f"Result from {name}: {result[:1500]}" if isinstance(result, str) else str(result)[:1500]
                }
                messages.append(tool_result)
                print(f"  ✓ Result received ({len(str(result))} chars)")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                messages.append({
                    'role': 'tool',
                    'content': f"Error executing {name}: {e}"
                })
    
    return None

if __name__ == '__main__':
    query = sys.argv[1] if len(sys.argv) > 1 else 'قیمت تتر و تأثیر اخبار روی آن'
    result = run_loop_proper(query, max_iterations=8)
    if result:
        print(f"\n{'='*60}")
        print("FINAL OUTPUT:")
        print(result)
