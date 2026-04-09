"""
Run this script from D:\\ai\\central-think-tank to patch agents.py:
    cd D:\\ai\\central-think-tank && python patch_agents_chat.py
"""
import pathlib, re
 
path = pathlib.Path("api/routes/agents.py")
content = path.read_text(encoding="utf-8")
 
# Fix the chat_with_agent endpoint to pass settings to _build_system_prompt
OLD = '''    system_prompt = _build_system_prompt(agent, chat_mode=True)'''
NEW = '''    from api.routes.settings import _load as _load_settings
    settings = await _load_settings()
    system_prompt = _build_system_prompt(agent, chat_mode=True, settings=settings)'''
 
if OLD in content:
    content = content.replace(OLD, NEW)
    path.write_text(content, encoding="utf-8")
    print("✓ agents.py patched: _build_system_prompt now receives settings")
else:
    print("⚠ Pattern not found — chat route may already be patched or different")
    # Try to find the line
    for i, line in enumerate(content.splitlines(), 1):
        if "_build_system_prompt" in line:
            print(f"  Line {i}: {line.strip()}")
 