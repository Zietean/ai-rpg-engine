import streamlit as st
import requests
import json
import random
import re
import os

# --- 1. CONFIGURATION & RULES ---
XP_TABLE = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500}
CLASSES = {
    "Mage": {"baseHp": 6, "hpPerLevel": 4, "skills": {1: ["Fire Bolt", "Arcane Shield"], 3: ["Mage Armor"], 5: ["Fireball"]}},
    "Warrior": {"baseHp": 10, "hpPerLevel": 6, "skills": {1: ["Second Wind", "Power Strike"], 3: ["Shield Bash"], 5: ["Whirlwind"]}},
    "Rogue": {"baseHp": 8, "hpPerLevel": 5, "skills": {1: ["Sneak Attack", "Cunning Action"], 3: ["Evasion"], 5: ["Shadow Step"]}}
}
DND_SKILLS = [
    "Strength (Athletics)", "Dexterity (Acrobatics)", "Dexterity (Stealth)", "Dexterity (Sleight of Hand)",
    "Intelligence (Arcana)", "Intelligence (History)", "Intelligence (Investigation)", "Intelligence (Nature)",
    "Wisdom (Insight)", "Wisdom (Perception)", "Wisdom (Medicine)", "Wisdom (Survival)",
    "Charisma (Persuasion)", "Charisma (Deception)", "Charisma (Intimidation)", "General D20 Roll"
]

st.set_page_config(page_title="AI RPG Engine v14", layout="wide")

if "state" not in st.session_state: st.session_state.state = None
if "history" not in st.session_state: st.session_state.history = []
if "model_list" not in st.session_state: st.session_state.model_list = []

# --- 2. THE "FORGIVING" TAG PARSER ---
def parse_tags(text):
    s = st.session_state.state
    if not s: return
    
    # 1. XP PARSER (Looking for [XP: 10] or XP: 10)
    xp_m = re.search(r"\[?XP:\s*(\+?\d+)\]?", text, re.IGNORECASE)
    if xp_m:
        gain = int(xp_m.group(1).replace('+', ''))
        s['xp'] += gain
        st.toast(f"✨ +{gain} XP")
    
    # 2. DAMAGE PARSER
    dmg_m = re.search(r"\[?DAMAGE:\s*(\d+)\]?", text, re.IGNORECASE)
    if dmg_m:
        dmg = int(dmg_m.group(1))
        s['hp'] -= dmg
        st.toast(f"🩸 Taken {dmg} Damage!")

    # 3. FORGIVING ITEM PARSER (Works with or without brackets)
    # This regex looks for "ADD ITEM: something" and stops at a newline or bracket
    for item in re.findall(r"\[?(?:ADD|GAIN)\s*ITEM:\s*([^\n\]\)]+)(?:\]|\)|$)", text, re.IGNORECASE):
        clean = item.strip()
        # Clean up common AI artifacts like "20 gold coins (for rescuing)"
        clean = clean.split('(')[0].strip()
        if clean and clean not in s['inv']: 
            s['inv'].append(clean)
            st.toast(f"🎒 Item: {clean}")

    # 4. REMOVE ITEM
    for item in re.findall(r"\[?REMOVE\s*ITEM:\s*([^\n\]\)]+)(?:\]|\)|$)", text, re.IGNORECASE):
        clean = item.strip().split('(')[0].strip()
        for i in list(s['inv']):
            if clean.lower() in i.lower(): s['inv'].remove(i); st.toast(f"📤 Removed: {i}"); break

    # 5. LEVEL UP CHECK
    next_lv = s['level'] + 1
    if next_lv in XP_TABLE and s['xp'] >= XP_TABLE[next_lv]:
        s['level'] = next_lv
        s['hp'] += CLASSES[s['class']]['hpPerLevel']
        s['skills'].extend(CLASSES[s['class']]['skills'].get(next_lv, []))
        st.balloons(); st.success(f"🌟 LEVEL UP! You are now Level {next_lv}!")

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Settings")
    api_source = st.selectbox("Source", ["ollama", "openrouter"])
    ollama_url = st.text_input("Ollama URL", "http://127.0.0.1:11434") if api_source == "ollama" else ""
    api_key = st.text_input("Key", type="password") if api_source == "openrouter" else ""
    
    if st.button("Refresh Models"):
        try:
            if api_source == "ollama":
                r = requests.get(f"{ollama_url}/api/tags", timeout=5)
                st.session_state.model_list = [m['name'] for m in r.json().get('models', [])]
            else:
                r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
                st.session_state.model_list = sorted([m['id'] for m in r.json().get('data', [])])
            st.success("Connected!")
        except: st.error("Connection Failed")

    selected_model = st.selectbox("Model", st.session_state.model_list if st.session_state.model_list else ["Not Connected"])
    
    st.divider()
    if st.session_state.state:
        c1, c2 = st.columns(2)
        if c1.button("💾 Save"):
            with open("rpg_save.json", "w") as f: json.dump({"state": st.session_state.state, "history": st.session_state.history}, f)
            st.toast("Saved")
        if c2.button("📂 Load") and os.path.exists("rpg_save.json"):
            with open("rpg_save.json", "r") as f:
                d = json.load(f); st.session_state.state, st.session_state.history = d["state"], d["history"]
            st.rerun()

    if st.button("New Game", type="primary", use_container_width=True): st.session_state.show_modal = True

    if st.session_state.state:
        st.divider()
        s = st.session_state.state
        max_hp = CLASSES[s['class']]['baseHp'] + (s['level']-1) * CLASSES[s['class']]['hpPerLevel']
        st.subheader(f"{s['name']} (Lv {s['level']} {s['class']})")
        st.progress(min(1.0, max(0.0, s['hp']/max_hp)))
        st.write(f"❤️ **HP:** {s['hp']}/{max_hp} | ✨ **XP:** {s['xp']}")
        st.markdown("---")
        
        t1, t2 = st.tabs(["🎒 Inventory", "📜 Skills"])
        with t1:
            new_item = st.text_input("Add Item (Manual)", placeholder="E.g. Coin")
            if st.button("Add"): 
                if new_item and new_item not in s['inv']: s['inv'].append(new_item); st.rerun()
            st.write("---")
            for item in list(s['inv']):
                col = st.columns([0.6, 0.2, 0.2])
                col[0].write(f"• {item}")
                if col[1].button("🎁", key=f"g_{item}"):
                    st.session_state.history.append({"role":"user","content":f"[SYSTEM: {s['name']} gives '{item}'. REMOVE it from inventory.]"}); st.rerun()
                if col[2].button("🗑️", key=f"d_{item}"): s['inv'].remove(item); st.rerun()
        with t2:
            st.write("**Known Abilities:**")
            for sk in s['skills']: st.write(f"⚔️ {sk}")

# --- 4. CHAT ---
st.title("🐉 AI RPG Engine")
for msg in st.session_state.history:
    if not msg["content"].startswith("["):
        with st.chat_message(msg["role"]): st.write(msg["content"])

if prompt := st.chat_input("What do you do?"):
    st.session_state.history.append({"role": "user", "content": prompt}); st.rerun()

if st.session_state.history and st.session_state.history[-1]["role"] == "user":
    s = st.session_state.state
    
    # --- PROMPT: STRICT "DO NOT ROLL" INSTRUCTIONS ---
    sys = (f"ACT AS: Dungeon Master. Player: '{s['name']}' (Level {s['level']} {s['class']}). "
           f"Setting: {s['setting']}. "
           f"HARD RULES: \n"
           f"1. NEVER ROLL DICE FOR THE PLAYER. If an action is risky, stop and ASK the player to roll.\n"
           f"2. Use format [ADD ITEM: Name] for loot.\n"
           f"3. Use format [REMOVE ITEM: Name] for losses.\n"
           f"4. Use format [XP: +Amount] for rewards.\n"
           f"5. Always end with 'What do you do?'\n"
           f"Inv: {', '.join(s['inv'])}.")
    
    with st.chat_message("assistant"):
        with st.spinner("DM is thinking..."):
            try:
                ctx = [{"role":"system","content":sys}] + st.session_state.history[-10:]
                if api_source == "ollama":
                    r = requests.post(f"{ollama_url}/api/chat", json={"model": selected_model, "messages": ctx, "stream": False}, timeout=None)
                    reply = r.json()['message']['content']
                else:
                    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json={"model": selected_model, "messages": ctx}, timeout=60)
                    reply = r.json()['choices'][0]['message']['content']
                
                reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
                st.write(reply); st.session_state.history.append({"role": "assistant", "content": reply})
                parse_tags(reply); st.rerun()
            except Exception as e: st.error(f"Error: {str(e)}")

# --- 5. ACTION BAR ---
if st.session_state.state:
    st.markdown("---")
    c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
    
    with c1:
        my_skills = st.session_state.state['skills'] + ["--- General Checks ---"] + DND_SKILLS
        skill_choice = st.selectbox("Select Action/Skill:", my_skills, label_visibility="collapsed")
        if st.button(f"🎲 Roll {skill_choice.split('(')[0]}", use_container_width=True):
            if "---" in skill_choice: st.toast("⚠️ Select a skill!")
            else:
                roll = random.randint(1, 20)
                outcome = "CRITICAL FAIL!" if roll == 1 else "CRITICAL SUCCESS!" if roll == 20 else "Result"
                msg = f"[SYSTEM: Player uses {skill_choice}. Rolled D20: {roll} ({outcome}). Determine outcome.]"
                st.toast(f"🎲 {skill_choice}: {roll}")
                st.session_state.history.append({"role":"user","content":msg}); st.rerun()

    with c2:
        if st.button("🍃 Cozy Moment", use_container_width=True):
            st.session_state.history.append({"role":"user","content":"[SYSTEM: Trigger a peaceful moment.]"}); st.rerun()

    with c3:
        if st.button("⚔️ Combat", use_container_width=True):
            st.session_state.history.append({"role":"user","content":"[SYSTEM: Threat appears! Ask for Initiative.]"}); st.rerun()

# --- 6. START MODAL ---
if st.session_state.get("show_modal"):
    with st.form("new"):
        n = st.text_input("Name", "Rennie"); cl = st.selectbox("Class", list(CLASSES.keys())); w = st.text_area("World", "Oakhaven.")
        if st.form_submit_button("Start Adventure"):
            st.session_state.state = {"name":n,"class":cl,"level":1,"xp":0,"hp":CLASSES[cl]['baseHp'],"skills":list(CLASSES[cl]['skills'][1]),"inv":["Clothes"],"journal":[],"comps":[],"setting":w}
            st.session_state.history = [{"role":"user","content":f"[START: Player is {n}. Describe opening. If items found, output [ADD ITEM: Name]. End with 'What do you do?']"}]
            st.session_state.show_modal = False; st.rerun()
