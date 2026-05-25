"""SAGE — Strategic Adversarial Generative Engine · Chat Interface"""
from __future__ import annotations
import os, json, re, asyncio
from pathlib import Path
from datetime import datetime
import httpx
import gradio as gr

SAGE_API_URL  = os.environ.get("SAGE_API_URL", "http://localhost:8000").rstrip("/")
HISTORY_FILE  = Path(os.environ.get("HISTORY_FILE", "/data/sage_history.json"))
MAX_CONTEXT   = 20

# ── Agent display styles ──────────────────────────────────────────────────────
AGENT_STYLES = {
    "SYSTEM":      {"icon": "○", "color": "#444444"},
    "Architect":   {"icon": "◈", "color": "#FF6B1A"},
    "Implementer": {"icon": "◆", "color": "#FF8C42"},
    "Red-Team":    {"icon": "◉", "color": "#FF4444"},
    "Synthesizer": {"icon": "◇", "color": "#FFA040"},
    "COUNCIL":     {"icon": "◎", "color": "#22C55E"},
    "ERROR":       {"icon": "✕", "color": "#FF4444"},
}

# ── Persistent history ────────────────────────────────────────────────────────
def load_history():
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text())
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def save_history(history):
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    except Exception:
        pass

def backend_live():
    try:
        r = httpx.get(f"{SAGE_API_URL}/healthz", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False

# ── HTML builders ─────────────────────────────────────────────────────────────
def format_answer(text):
    text = re.sub(r'```(\w*)\n(.*?)```',
        lambda m: f'<pre><code class="lang-{m.group(1)}">{m.group(2)}</code></pre>',
        text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = text.replace('\n', '<br>')
    return text

def render_history(history):
    if not history:
        return '''<div id="empty-state">
          <div style="font-size:48px;color:#181818;margin-bottom:16px;">◎</div>
          <div style="font-size:20px;font-weight:700;color:#fff;margin-bottom:8px;">Ask SAGE anything</div>
          <div style="font-size:13px;color:#333;max-width:440px;margin:0 auto;line-height:1.8;">
            Simple queries load one fast model. Complex problems trigger the full council.
          </div>
        </div>'''
    html = ""
    for msg in history:
        role = msg.get("role")
        text = msg.get("text", "")
        deliberation = msg.get("deliberation", [])
        if role == "user":
            html += f'''<div class="msg-user">
              <div class="msg-user-bubble">{text}</div>
            </div>'''
        elif role == "sage":
            delib_html = ""
            if deliberation:
                lines = ""
                for agent, content in deliberation:
                    st = AGENT_STYLES.get(agent, {"icon":"○","color":"#444"})
                    lines += f'''<div class="d-line">
                      <span class="d-agent" style="color:{st["color"]};">{st["icon"]} {agent}</span>
                      <span class="d-msg">{content[:120]}</span>
                    </div>'''
                delib_html = f'<div class="deliberation">{lines}</div>'
            html += f'''<div class="msg-sage">
              <div class="msg-sage-avatar">◎</div>
              <div class="msg-sage-content">
                {delib_html}
                <div class="msg-sage-bubble">{format_answer(text)}</div>
              </div>
            </div>'''
    return html + '<div id="chat-bottom"></div>'

def navbar_html(live):
    color = "#22C55E" if live else "#818CF8"
    mode  = "LIVE" if live else "DEMO"
    return f'''<div id="sage-navbar">
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-size:20px;font-weight:800;color:#fff;letter-spacing:-0.03em;">SAGE</span>
        <span style="width:5px;height:5px;border-radius:50%;background:#FF6B1A;"></span>
        <span style="font-family:monospace;font-size:10px;color:#2A2A2A;letter-spacing:0.1em;">STRATEGIC ADVERSARIAL GENERATIVE ENGINE</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-family:monospace;font-size:10px;background:rgba(255,107,26,0.08);border:1px solid rgba(255,107,26,0.2);color:{color};padding:3px 10px;border-radius:4px;">{mode}</span>
        <span style="font-size:11px;color:#2A2A2A;">AMD MI300X · 192 GB HBM3</span>
      </div>
    </div>'''

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');
:root{--bg:#080808;--bg2:#0D0D0D;--card:#111111;--bd:#1E1E1E;--bd2:#2A2A2A;--tx:#BBBBBB;--txd:#333333;--txh:#FFFFFF;--ora:#FF6B1A;--ora2:#FF8C42;--green:#22C55E;--red:#FF4444;--F:'Inter',sans-serif;--M:'JetBrains Mono',monospace;}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body,.gradio-container{background:var(--bg)!important;font-family:var(--F)!important;color:var(--tx)!important;}
.gradio-container{max-width:100%!important;padding:0!important;}
footer,.built-with{display:none!important;}
#sage-navbar{background:rgba(8,8,8,0.97);border-bottom:1px solid var(--bd);padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:999;backdrop-filter:blur(12px);}
#chat-wrap{max-width:860px;margin:0 auto;padding:24px 16px 160px;}
#empty-state{text-align:center;padding:80px 24px;}
.msg-user{display:flex;justify-content:flex-end;margin:16px 0 4px;}
.msg-user-bubble{background:var(--ora);color:#000;border-radius:18px 18px 4px 18px;padding:12px 18px;max-width:72%;font-size:14px;line-height:1.65;font-weight:500;}
.msg-sage{display:flex;gap:12px;margin:4px 0 16px;align-items:flex-start;}
.msg-sage-avatar{width:32px;height:32px;border-radius:50%;background:rgba(255,107,26,0.12);border:1px solid rgba(255,107,26,0.25);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;margin-top:2px;color:#FF6B1A;}
.msg-sage-content{flex:1;max-width:calc(100% - 44px);}
.deliberation{padding:6px 0 6px 12px;border-left:2px solid #1A1A1A;margin-bottom:8px;}
.d-line{display:flex;gap:8px;align-items:baseline;margin:3px 0;opacity:0.35;font-family:var(--M);font-size:11px;}
.d-line:hover{opacity:0.65;transition:opacity 0.15s;}
.d-agent{font-size:10px;font-weight:600;letter-spacing:0.06em;min-width:88px;flex-shrink:0;}
.d-msg{color:#444;}
.msg-sage-bubble{background:var(--card);border:1px solid var(--bd);border-radius:4px 18px 18px 18px;padding:14px 18px;font-size:14px;line-height:1.75;color:var(--txh);white-space:pre-wrap;word-wrap:break-word;}
.msg-sage-bubble code{font-family:var(--M);background:#0D0D0D;border:1px solid var(--bd);border-radius:4px;padding:2px 6px;font-size:12px;color:#FF8C42;}
.msg-sage-bubble pre{background:#0A0A0A;border:1px solid var(--bd);border-radius:8px;padding:14px 16px;overflow-x:auto;margin:10px 0;font-family:var(--M);font-size:12px;line-height:1.7;color:#E8A87C;}
#input-bar{position:fixed;bottom:0;left:0;right:0;background:rgba(8,8,8,0.97);border-top:1px solid var(--bd);padding:14px 24px 18px;backdrop-filter:blur(12px);z-index:998;}
#input-inner{max-width:860px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;}
#msg-input textarea{background:var(--card)!important;border:1px solid var(--bd)!important;border-radius:12px!important;color:var(--txh)!important;font-family:var(--F)!important;font-size:14px!important;padding:12px 16px!important;resize:none!important;min-height:48px!important;max-height:160px!important;transition:border-color 0.2s!important;}
#msg-input textarea:focus{border-color:var(--ora)!important;outline:none!important;box-shadow:0 0 0 3px rgba(255,107,26,0.08)!important;}
#send-btn button{background:var(--ora)!important;color:#000!important;border:none!important;border-radius:12px!important;height:48px!important;width:48px!important;font-size:18px!important;font-weight:700!important;padding:0!important;min-width:48px!important;transition:all 0.2s!important;}
#send-btn button:hover{background:var(--ora2)!important;transform:scale(1.05)!important;}
#send-btn button:disabled{background:var(--bd2)!important;color:var(--txd)!important;transform:none!important;}
#clear-btn button{background:transparent!important;border:1px solid #2A2A2A!important;color:#444!important;border-radius:8px!important;font-size:11px!important;padding:4px 12px!important;font-family:var(--M)!important;}
#clear-btn button:hover{border-color:var(--red)!important;color:var(--red)!important;}
::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:4px;}
.tabitem{background:transparent!important;border:none!important;}
"""

SCROLL_JS = """
<script>
function scrollToBottom(){
  var el = document.getElementById('chat-bottom');
  if(el) el.scrollIntoView({behavior:'smooth'});
}
setTimeout(scrollToBottom, 100);
</script>
"""

# ── Core chat function ────────────────────────────────────────────────────────
async def chat(user_msg, history):
    if not user_msg or not user_msg.strip():
        yield render_history(history) + SCROLL_JS, history, ""
        return

    history = history or []
    history.append({"role": "user", "text": user_msg.strip()})

    # Show user message immediately with thinking dots
    thinking = render_history(history) + '''
    <div class="msg-sage">
      <div class="msg-sage-avatar">◎</div>
      <div class="msg-sage-content">
        <div style="padding:10px 0;display:flex;gap:4px;align-items:center;">
          <div style="width:6px;height:6px;border-radius:50%;background:#FF6B1A;animation:bounce 1.4s infinite ease-in-out;"></div>
          <div style="width:6px;height:6px;border-radius:50%;background:#FF6B1A;animation:bounce 1.4s infinite ease-in-out;animation-delay:0.2s;"></div>
          <div style="width:6px;height:6px;border-radius:50%;background:#FF6B1A;animation:bounce 1.4s infinite ease-in-out;animation-delay:0.4s;"></div>
        </div>
      </div>
    </div>
    <style>@keyframes bounce{0%,80%,100%{transform:scale(0.6);opacity:0.35;}40%{transform:scale(1);opacity:1;}}</style>
    ''' + SCROLL_JS
    yield thinking, history, ""

    live = backend_live()
    deliberation = []
    final_answer = ""

    if not live:
        await asyncio.sleep(0.5)
        final_answer = f"[DEMO MODE] Backend offline. Your query was: **{user_msg}**\n\nConnect the backend at {SAGE_API_URL} to get real responses."
    else:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{SAGE_API_URL}/v1/sage/stream",
                    json={"query": user_msg.strip(), "max_cycles": 1},
                ) as resp:
                    resp.raise_for_status()
                    current_delib = list(deliberation)
                    async for raw_line in resp.aiter_lines():
                        line = raw_line.strip()
                        if not line or line.startswith(":"): continue
                        if line.startswith("data: "): line = line[6:]
                        elif line.startswith("data:"): line = line[5:]
                        else: continue
                        try:
                            evt = json.loads(line)
                        except Exception:
                            continue
                        event_type = evt.get("event", "")
                        agent      = evt.get("agent", "SYSTEM")
                        content    = evt.get("content", "")
                        if event_type == "pipeline_done":
                            final_answer = content
                            break
                        elif event_type == "error":
                            final_answer = f"Pipeline error: {content}"
                            break
                        elif content:
                            current_delib.append((agent, content))
                            deliberation = current_delib
                            # Yield live deliberation update
                            partial = render_history(history[:-1] + [{"role":"user","text":user_msg}]) + f'''
                            <div class="msg-sage">
                              <div class="msg-sage-avatar">◎</div>
                              <div class="msg-sage-content">
                                <div class="deliberation">{"".join(
                                    f'<div class="d-line"><span class="d-agent" style="color:{AGENT_STYLES.get(a,{"color":"#444"})["color"]};">{AGENT_STYLES.get(a,{"icon":"○"})["icon"]} {a}</span><span class="d-msg">{c[:120]}</span></div>'
                                    for a,c in current_delib[-6:]
                                )}</div>
                                <div style="padding:8px 0;display:flex;gap:4px;align-items:center;">
                                  <div style="width:5px;height:5px;border-radius:50%;background:#FF6B1A;opacity:0.6;"></div>
                                  <div style="width:5px;height:5px;border-radius:50%;background:#FF6B1A;opacity:0.6;"></div>
                                  <div style="width:5px;height:5px;border-radius:50%;background:#FF6B1A;opacity:0.6;"></div>
                                </div>
                              </div>
                            </div>''' + SCROLL_JS
                            yield partial, history, ""
        except Exception as e:
            final_answer = f"Connection error: {str(e)}"

    if not final_answer:
        final_answer = "No response received from pipeline."

    history.append({"role": "sage", "text": final_answer, "deliberation": deliberation})
    save_history(history)
    yield render_history(history) + SCROLL_JS, history, ""


def clear_chat():
    save_history([])
    return render_history([]), [], ""


# ── Build UI ──────────────────────────────────────────────────────────────────
def build():
    live = backend_live()
    init_history = load_history()

    with gr.Blocks(
        title="SAGE — Strategic Adversarial Generative Engine",
        css=CSS,
        theme=gr.themes.Base(),
    ) as demo:
        history_state = gr.State(init_history)

        gr.HTML(navbar_html(live))

        with gr.Column(elem_id="chat-wrap"):
            chat_display = gr.HTML(
                value=render_history(init_history) + SCROLL_JS
            )

        with gr.Row(elem_id="input-bar"):
            with gr.Column(elem_id="input-inner"):
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="Ask anything — code, analysis, creative writing, life advice...",
                        show_label=False,
                        lines=1,
                        max_lines=6,
                        elem_id="msg-input",
                        scale=9,
                    )
                    send_btn = gr.Button("↑", elem_id="send-btn", scale=1)
                with gr.Row():
                    clear_btn = gr.Button("Clear conversation", elem_id="clear-btn", size="sm")

        send_btn.click(
            fn=chat,
            inputs=[msg_input, history_state],
            outputs=[chat_display, history_state, msg_input],
        )
        msg_input.submit(
            fn=chat,
            inputs=[msg_input, history_state],
            outputs=[chat_display, history_state, msg_input],
        )
        clear_btn.click(
            fn=clear_chat,
            outputs=[chat_display, history_state, msg_input],
        )

    return demo


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    app = build()
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        show_error=True,
        favicon_path=None,
    )
