# RenderKit Standalone Plugin Plan

## Overview
Promote renderkit's in-Blender N-panel (`blender_addon/renderkit_panel.py`) as the primary standalone surface. Renderkit already uses native Anthropic SDK and is production-ready.

## Current State
- **SDK:** Native `anthropic` SDK (agent.py:14, client at :61, model="claude-opus-4-8", thinking adaptive)
- **Tool base:** 20 tools in `core/tools.py:479`, screenshot at :150, run_blender_code at :32
- **Bridge:** `core/bridge.py` → socket to blender-mcp addon (127.0.0.1:9876)
- **In-Blender UI:** Commit 541a30a, N-panel addon with manifest
- **Status:** Essentially ready; needs final UI polish and standalone test

## Phase 1: Standalone Surface Hardening
1. Verify `blender_addon/renderkit_panel.py` is complete
   - [ ] Load in-panel, list available tools
   - [ ] Invoke a screenshot tool (test vision feedback loop)
   - [ ] Invoke a bpy code execution tool (test Blender command)
2. Test InProcessBridge mode (direct socket to blender-mcp, no external Python)
   - [ ] Confirm 127.0.0.1:9876 handshake
   - [ ] Confirm tool dispatch round-trip

## Phase 2: Asset Pipeline
1. Verify PolyHaven asset import flow (`core/tools.py`, likely around fetch tools)
2. Test one asset fetch end-to-end (e.g., sphere → PolyHaven → Blender scene)
3. Document prerequisite: user must have blender-mcp addon socket listening

## Phase 3: Packaging
1. [ ] Distribute as blender add-on zip or git clone instructions
2. [ ] Minimal README: how to load, how to set ANTHROPIC_API_KEY
3. [ ] (Optional) Wrap Python companion in PyInstaller for UI convenience

## Success Criteria
- Standalone N-panel loads in Blender without external companion ✓
- Screenshot + code execution + asset import all work end-to-end ✓
- User can set API key via panel UI or .env ✓
