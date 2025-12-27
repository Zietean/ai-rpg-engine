import streamlit as st
import requests
import json
import random
import re
import os

# --- 1. DATA & CONFIGURATION ---
XP_TABLE = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500}
CLASSES = {
    "Mage": {"baseHp": 6, "hpPerLevel": 4, "skills": {1: ["Fire Bolt", "Arcane Shield"], 3: ["Mage Armor"], 5: ["Fireball"]}},
    "Warrior": {"baseHp": 10, "hpPerLevel": 6, "skills": {1: ["Second Wind", "Power Strike"], 3: ["Shield Bash"], 5: ["Whirlwind"]}},
    "Rogue": {"baseHp": 8, "hpPerLevel": 5, "skills": {1: ["Sneak Attack", "Cunning Action"], 3: ["Evasion"], 5: ["Shadow Step"]}}
}

st.set_page_config(page_title="AI RPG Engine v9.0", layout="wide")

if "state" not in st.session_state: st.session_state.state = None
if "history" not in st.session_state: st.session_state.history = []
if "model_list" not in st.session_state: st.session_state.model_list = []

# --- 2. TAG PARSER ---
def parse_tags(text):
    s = st.session_state.state
    if not s: return
    # XP
    xp_m = re.search(r"\[XP:\s*(\d+)\]", text, re.IGNORECASE)
    if xp_m:
        gain = int(xp_m.group(1))
        s['xp'] += gain
        st.toast(f"✨ +{gain} XP")
    # Removal (Trade Safety)
    for item in re.findall(r"\[REMOVE\s*ITEM:\s*(.*?)\]", text, re.IGNORECASE):
        clean_name = item.strip().lower()
        for i in list(s['inv']):
            if clean_name in i.lower():
                s['inv'].remove(i); st.toast(f"📤 Removed: {i}"); break
    # Add Item
    for item in re.findall(r"\[(?:ADD|GAIN)\s*ITEM:\s*(.*?)\]", text, re.IGNORECASE):
        if item.strip() and item.strip() not in s['inv']:
            s['inv'].append(item.strip()); st.toast(f"🎒 Item: {item.strip()}")
    # Companions & Journal
    for comp in re.findall(r"\[ADD\s*COMPANION:\s*(.*?)\]", text, re.IGNORECASE):
        if comp.strip() not in s['comps']: s['comps'].append(comp.strip()); st.toast(f"🤝 Companion: {comp.strip()}")
    for entry in re.findall(r"\[(?:UPDATE|ADD TO)\s*JOURNAL:\s*(.*?)\]", text, re.IGNORECASE):
        if entry.strip() not in s['journal']: s['journal'].append(entry.strip()); st.toast("📔 Journal Updated")

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ AI Settings")
    api_source = st.selectbox("Source", ["ollama", "openrouter"])
    ollama_url = st.text_input("Ollama URL", "http://127.0.0.1:11434") if api_source == "ollama" else ""
    api_key = st.text_input("Key", type="password") if api_source == "openrouter" else ""
    
    if st.button("Refresh Models"):
        try:
            if api_source == "ollama":
                r = requests.get(f"{ollama_url}/api/tags", timeout=10)
                st.session_state.model_list = [m['name'] for m in r.json().get('models', [])]
            else:
                r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
                st.session_state.model_list = sorted([m['id'] for m in r.json().get('data', [])])
            st.success("Connected!"); st.rerun()
        except Exception as e: st.error(f"Failed: {str(e)}")

    selected_model = st.selectbox("Model", st.session_state.model_list if st.session_state.model_list else ["Not Connected"])
    
    if st.session_state.state:
        cs1, cs2 = st.columns(2)
        if cs1.button("💾 Save"):
            with open("rpg_save.json", "w") as f: json.dump({"state": st.session_state.state, "history": st.session_state.history}, f)
            st.toast("Saved!")
        if cs2.button("📂 Load") and os.path.exists("rpg_save.json"):
            with open("rpg_save.json", "r") as f:
                d = json.load(f); st.session_state.state, st.session_state.history = d["state"], d["history"]
            st.rerun()

    if st.button("New Game", type="primary", use_container_width=True): st.session_state.show_modal = True

    if st.session_state.state:
        st.divider()
        t1, t2 = st.tabs(["📜 Sheet", "📔 Journal"])
        with t1:
            s = st.session_state.state
            max_hp = CLASSES[s['class']]['baseHp'] + (s['level']-1) * CLASSES[s['class']]['hpPerLevel']
            st.write(f"**{s['name']}** (Lv {s['level']} {s['class']})")
            st.progress(max(0.0, min(1.0, s['hp']/max_hp)))
            st.write(f"**Skills:** {', '.join(s['skills'])}")
            
            if s['comps']:
                st.write("**Companions:**")
                for c_name in s['comps']:
                    cc = st.columns([0.6, 0.2, 0.2])
                    cc[0].write(f"🤝 {c_name}")
                    if cc[1].button("💬", key=f"tk_{c_name}"):
                        st.session_state.history.append({"role":"user","content":f"[SYSTEM: Talk to {c_name}]"}); st.rerun()
                    if cc[2].button("🚶", key=f"lv_{c_name}"):
                        st.session_state.history.append({"role":"user","content":f"[SYSTEM: {c_name} leaves party. use [REMOVE COMPANION: {c_name}]]"}); st.rerun()

            st.write("**Inventory:**")
            for item in list(s['inv']):
                ic = st.columns([0.6, 0.2, 0.2])
                ic[0].write(f"• {item}")
                if ic[1].button("🎁", key=f"g_{item}"):
                    st.session_state.history.append({"role":"user","content":f"[SYSTEM: {s['name']} hands over {item}. React and use [REMOVE ITEM: {item}].]"}); st.rerun()
                if ic[2].button("🗑️", key=f"d_{item}"): s['inv'].remove(item); st.rerun()
        with t2:
            for note in s['journal']: st.write(f"• {note}")

# --- 4. CHAT ---
st.title("🐉 AI RPG Engine")
for msg in st.session_state.history:
    if not msg["content"].startswith("["):
        with st.chat_message(msg["role"]): st.write(msg["content"])

if prompt := st.chat_input("What do you do?"):
    st.session_state.history.append({"role": "user", "content": prompt}); st.rerun()

if st.session_state.history and st.session_state.history[-1]["role"] == "user":
    s = st.session_state.state
    # ULTRA-STRICT ROLEPLAY INSTRUCTIONS
    sys = (f"ACT AS: Dungeon Master (Narrator). "
           f"IMPORTANT: The User is playing as '{s['name']}'. "
           f"NEVER treat '{s['name']}' as an NPC or merchant. "
           f"NEVER speak for '{s['name']}'. Always address the user as 'You'. "
           f"SETTING: {s['setting']}. Reward actions with [XP: n]. "
           f"TAGS: [XP: n], [DAMAGE: n], [ADD ITEM: n], [REMOVE ITEM: n], [UPDATE JOURNAL: text].")
    
    with st.chat_message("assistant"):
        with st.spinner("DM Thinking..."):
            try:
                ctx = [{"role":"system","content":sys}] + st.session_state.history[-10:]
                if api_source == "ollama":
                    r = requests.post(f"{ollama_url}/api/chat", json={"model": selected_model, "messages": ctx, "stream": False}, timeout=120)
                    reply = r.json()['message']['content']
                else:
                    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json={"model": selected_model, "messages": ctx}, timeout=60)
                    reply = r.json()['choices'][0]['message']['content']
                
                reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
                st.write(reply); st.session_state.history.append({"role": "assistant", "content": reply})
                parse_tags(reply); st.rerun()
            except Exception as e: st.error(f"Error: {str(e)}")

# --- 5. MODAL ---
if st.session_state.get("show_modal"):
    with st.form("new"):
        n = st.text_input("Name", "Rennie"); cl = st.selectbox("Class", list(CLASSES.keys())); w = st.text_area("World", "Oakhaven.")
        if st.form_submit_button("Start"):
            st.session_state.state = {"name":n,"class":cl,"level":1,"xp":0,"hp":CLASSES[cl]['baseHp'],"skills":list(CLASSES[cl]['skills'][1]),"inv":["Clothes"],"journal":[],"comps":[],"setting":w}
            # Explicit start command to prevent identity confusion
            st.session_state.history = [{"role":"user","content":f"[START GAME: You are the DM. The player is '{n}'. Describe the opening scene. DO NOT make '{n}' an NPC.]"}]
            st.session_state.show_modal = False; st.rerun()

if st.session_state.state:
    b1, b2, b3 = st.columns(3)
    if b1.button("🎲 Skill Check"):
        roll = random.randint(1, 20); st.session_state.history.append({"role":"user","content":f"[SYSTEM: Roll D20. Result: {roll}.]"}); st.rerun()
    if b2.button("🍃 Cozy Event"): st.session_state.history.append({"role":"user","content":"[SYSTEM: Trigger cozy event.]"}); st.rerun()
    if b3.button("⚔️ Adventure!"): st.session_state.history.append({"role":"user","content":"[SYSTEM: Trigger adventure.]"}); st.rerun()
