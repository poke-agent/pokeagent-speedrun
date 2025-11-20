# LMStudio Streaming Enhancement

## Overview

Enhanced the web interface to display **LMStudio backend API responses** in the "AGENT_THINKING" panel with better formatting and backend identification.

## Changes Made

### File: `server/stream.html`

#### 1. **Backend Type Detection** ✅

Added automatic backend detection based on interaction type:

```javascript
const backendType = data.type?.toLowerCase().includes('lmstudio') ? 'LMStudio' :
                  data.type?.toLowerCase().includes('gemini') ? 'Gemini' :
                  data.type?.toLowerCase().includes('openai') ? 'OpenAI' :
                  data.type?.toLowerCase().includes('anthropic') ? 'Claude' : 'VLM';
```

Supported backends:
- **LMStudio** (local models)
- **Gemini** (Google)
- **OpenAI** (GPT-4, etc.)
- **Claude** (Anthropic)
- **VLM** (fallback/generic)

#### 2. **Enhanced Display Format** ✅

**Before**:
```
Step 5:
<response text>
lmstudio_simple_mode (12.45s)
```

**After**:
```
Step 5 [LMStudio]:
<response text>
lmstudio_simple_mode (12.45s)
```

The backend type is now clearly shown in brackets `[LMStudio]` next to the step number.

#### 3. **Enhanced Console Logging** ✅

Added detailed debug logging to browser console:

```javascript
console.log("New agent message received:", data);
console.log("  Step:", data.step);
console.log("  Type:", data.type);
console.log("  Duration:", data.duration);
console.log("  Response length:", data.response?.length || 0);
```

**How to access**:
- Open browser developer tools (F12 or Cmd+Option+I)
- Go to "Console" tab
- Watch for real-time logging of LMStudio responses

#### 4. **Both Streaming and Fallback** ✅

Enhanced **BOTH** display modes:
- **Streaming mode**: Real-time Server-Sent Events (SSE)
- **Fallback mode**: Polling-based updates

Both now show the backend type and improved logging.

## How It Works

### Data Flow

```
[Simple Agent]
    ↓
[LMStudio Backend (vlm.py)]
    ↓ log_llm_interaction()
[LLM Logger (llm_logs/*.jsonl)]
    ↓
[FastAPI /agent_stream endpoint]
    ↓ Server-Sent Events
[Web Interface stream.html]
    ↓
[AGENT_THINKING Panel]
```

### LMStudio Logging (Already Existed)

**File**: `utils/vlm.py` (line 1095-1102)

```python
# Log the interaction
log_llm_interaction(
    interaction_type=f"lmstudio_{module_name}",  # e.g., "lmstudio_simple_mode"
    prompt=text,
    response=result,
    duration=duration,
    metadata={"model": self.model_name, "backend": "lmstudio", "has_image": True, "token_usage": token_usage},
    model_info={"model": self.model_name, "backend": "lmstudio"}
)
```

This creates entries in `llm_logs/llm_log_YYYYMMDD_HHMMSS.jsonl`.

### Server Streaming (Already Existed)

**File**: `server/app.py` (line 1205-1319)

The `/agent_stream` endpoint:
1. Reads from LLM log files
2. Detects new interactions (by timestamp)
3. Streams them via Server-Sent Events (SSE)
4. Sends to web interface in real-time

### Web Display (ENHANCED)

**File**: `server/stream.html` (line 827-905)

Now extracts backend type and displays it prominently.

## What You'll See

### In Web Interface (`http://localhost:8000/stream`)

When LMStudio makes a call, the "AGENT_THINKING" panel shows:

```
Step 1 [LMStudio]:
ANALYSIS:
The player is in LITTLEROOT_TOWN at coordinates (8, 7)...

OBJECTIVES:
Current objective is to enter the player's house...

PLAN:
Move UP to reach the door at (8, 6)...

REASONING:
The movement preview shows UP is walkable...

ACTION:
UP

lmstudio_simple_mode (15.3s)
```

**Key elements**:
- `Step 1` - Agent step number
- `[LMStudio]` - Backend identifier (NEW!)
- Response text - Full LLM response
- `lmstudio_simple_mode (15.3s)` - Interaction type and duration

### In Browser Console (F12)

When a new message arrives:

```
New agent message received: {step: 1, type: "lmstudio_simple_mode", duration: 15.3, response: "...", is_new: true}
  Step: 1
  Type: lmstudio_simple_mode
  Duration: 15.3
  Response length: 1247
```

This helps debug if responses aren't showing up.

## Testing

### 1. Start the Agent

```bash
python run.py \
  --backend lmstudio \
  --model-name "qwen3-vl-4b-instruct-mlx" \
  --scaffold simple \
  --agent-auto
```

### 2. Open Web Interface

```
http://localhost:8000/stream
```

### 3. Open Browser Console

Press `F12` (or `Cmd+Option+I` on Mac) → Console tab

### 4. Watch for LMStudio Responses

- **AGENT_THINKING panel**: Shows `Step X [LMStudio]: <response>`
- **Console**: Shows detailed logging

### 5. Verify Logs Are Created

```bash
# Check latest LLM log
ls -t llm_logs/*.jsonl | head -1 | xargs tail -3 | python -m json.tool

# Should show:
# {
#   "type": "interaction",
#   "interaction_type": "lmstudio_simple_mode",
#   "response": "ANALYSIS: ...",
#   ...
# }
```

## Troubleshooting

### Problem: "Agent streaming connected..." but no responses

**Cause**: No LLM calls being made yet (agent not active)

**Solution**:
- Wait for agent to start acting (in auto mode)
- Check if agent is stuck (look at pygame window)
- Verify LMStudio is responding (run `python test_lmstudio.py`)

### Problem: Responses not showing backend type

**Cause**: Old cache, need to refresh

**Solution**:
1. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
2. Clear browser cache
3. Restart server

### Problem: Console shows errors

**Common errors**:

```javascript
// Error: "data.type is undefined"
// Solution: LLM log might be malformed, check llm_logs/ files
```

**Debug**:
```javascript
// In browser console, check raw event data:
streamingSource.onmessage = function(e) {
  console.log("Raw SSE:", e.data);
};
```

### Problem: Shows "VLM" instead of "LMStudio"

**Cause**: Interaction type doesn't contain "lmstudio"

**Solution**: Check LLM logs:
```bash
tail -1 llm_logs/llm_log_*.jsonl | python -m json.tool | grep interaction_type

# Should show: "interaction_type": "lmstudio_simple_mode"
```

If it shows something else, the backend might not be LMStudio.

## Backend Detection Logic

The system detects backend by checking the `interaction_type` field:

| Interaction Type | Displayed As |
|-----------------|--------------|
| `lmstudio_*` | [LMStudio] |
| `gemini_*` | [Gemini] |
| `openai_*` | [OpenAI] |
| `anthropic_*` | [Claude] |
| anything else | [VLM] |

This is **case-insensitive** matching.

## Benefits

✅ **Clear Backend Identification** - Know which backend is responding
✅ **Better Debugging** - Console logs help troubleshoot issues
✅ **Consistent Display** - Works in both streaming and fallback modes
✅ **Backward Compatible** - Doesn't break existing functionality
✅ **Real-time Updates** - See LMStudio responses as they happen

## File Changes Summary

| File | Changes | Lines |
|------|---------|-------|
| `server/stream.html` | Added backend detection (streaming) | 848-856 |
| `server/stream.html` | Added backend detection (fallback) | 947-952 |
| `server/stream.html` | Enhanced console logging | 846-850 |

## No Changes Needed

These already work correctly:
- ✅ `utils/vlm.py` - LMStudio logging (line 1095-1102)
- ✅ `server/app.py` - Streaming endpoint (line 1205-1319)
- ✅ `utils/llm_logger.py` - Log file management

## Usage Example

When the agent is running with LMStudio:

1. **Web UI**: Shows `Step 1 [LMStudio]: ANALYSIS: ...`
2. **Console**: Logs detailed response info
3. **LLM Logs**: Saves full interaction to `llm_logs/llm_log_YYYYMMDD_HHMMSS.jsonl`

This provides **three levels** of visibility:
- **Visual** (web UI)
- **Debug** (browser console)
- **Permanent** (log files)

## Next Steps

Once the agent is running:
1. Open `http://localhost:8000/stream`
2. Open browser console (F12)
3. Watch for `[LMStudio]` tags in AGENT_THINKING
4. Check console logs for detailed info

The enhancements are now live! 🎉
