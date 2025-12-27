import streamlit as st
import random
import requests
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# =========================================================
# -------------------- RULES ------------------------------
# =========================================================

ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

SKILLS = {
    "Athletics": "STR",
    "Acrobatics": "DEX",
    "Stealth": "DEX",
    "Arcana": "INT",
    "History": "INT",
    "Perception": "WIS",
    "Investigation": "INT",
    "Survival": "WIS",
    "Persuasion": "CHA",
}

DC_TABLE = {"easy": 10, "medium": 15, "hard": 20}

# Modified: Added more verbs to catch player intents
ACTION_RULES = {
    "look": {"skills": ["Perception"], "dc": "easy"},
    "inspect": {"skills": ["Investigation"], "dc": "medium"},
    "search": {"skills": ["Perception"], "dc": "medium"},
    "gather": {"skills": ["Survival"], "dc": "medium"},
    "take": {"skills": ["Acrobatics", "Survival"], "dc": "medium"},
    "pick": {"skills": ["Acrobatics", "Survival"], "dc": "medium"},
    "grab": {"skills": ["Athletics", "Acrobatics"], "dc": "medium"},
    "touch": {"skills": ["Investigation", "Survival"], "dc": "medium"},
    "open chest": {"skills": ["Investigation"], "dc": "medium"},
}

CLASSES = {
    "Fighter": {"hp": 10, "proficiencies": ["Athletics"], "spell_slots": 0},
    "Rogue": {"hp": 8, "proficiencies": ["Stealth", "Acrobatics"], "spell_slots": 0},
    "Wizard": {"hp": 6, "proficiencies": ["Arcana", "History"], "spell_slots": 2},
}

# =========================================================
# -------------------- UTILITIES --------------------------
# =========================================================

def mod(score: int) -> int:
    return (score - 10) // 2

def roll_d20() -> int:
    return random.randint(1, 20)

# =========================================================
# -------------------- DATA MODELS ------------------------
# =========================================================

@dataclass
class Character:
    name: str
    cls: str
    level: int = 1
    xp: int = 0
    max_hp: int = 10
    hp: int = 10
    stats: Dict[str, int] = field(default_factory=dict)
    proficiencies: List[str] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=dict)
    spell_slots: int = 0

    def prof_bonus(self) -> int:
        return 2 + (self.level - 1) // 4

    def roll_check(self, skill: str):
        stat = SKILLS[skill]
        d20 = roll_d20()
        total = d20 + mod(self.stats[stat])
        if skill in self.proficiencies:
            total += self.prof_bonus()
        return d20, total

@dataclass
class WorldObject:
    name: str
    description: str
    looted: bool = False
    contents: Dict[str, int] = field(default_factory=dict)

# =========================================================
# -------------------- GAME SETUP -------------------------
# =========================================================

def new_character(name: str, cls: str) -> Character:
    stats = {a: random.randint(8, 15) for a in ATTRS}
    base_hp = CLASSES[cls]["hp"]
    hp = base_hp + mod(stats["CON"])
    return Character(
        name=name,
        cls=cls,
        max_hp=hp,
        hp=hp,
        stats=stats,
        proficiencies=CLASSES[cls]["proficiencies"],
        inventory={"Clothes": 1},
        spell_slots=CLASSES[cls]["spell_slots"],
    )

def starting_objects():
    return {}

# =========================================================
# -------------------- LLM (LOCKED) -----------------------
# =========================================================

def build_system_prompt():
    inv = st.session_state.char.inventory
    objs = st.session_state.objects
    setting = st.session_state.setting

    inventory_text = ", ".join(
        f"{k} x{v}" for k, v in inv.items()
    ) if inv else "none"

    object_text = ", ".join(
        f"{o.name}" for o in objs.values()
    ) if objs else "none"

    return f"""
You are the Dungeon Master.
GAME SETTING: {setting}

STRICT, NON-NEGOTIABLE RULES:

INVENTORY:
- The player inventory is: {inventory_text}
- You may ONLY mention or describe items from this list.
- You may NOT invent weapons, armor, tools, gear, food, or equipment.

WORLD OBJECTS:
- The following interactive objects exist: {object_text}
- You may describe the environment freely based on the '{setting}' setting.
- However, standard interactable items (that go into inventory) are currently: {object_text}.
- You may NOT resolve interactions without rolls.

MECHANICS:
- Never roll dice
- Never decide success or failure
- Never change inventory, HP, XP, or levels
- Only narrate outcomes AFTER results are provided
- Always end with: What do you do?
"""

def call_dm(history):
    model = st.session_state.selected_model
    if not model:
        return "The world waits quietly. What do you do?"

    ctx = [{"role": "system", "content": build_system_prompt()}] + history[-10:]

    try:
        if st.session_state.api_source == "ollama":
            r = requests.post(
                f"{st.session_state.ollama_url}/api/chat",
                json={"model": model, "messages": ctx, "stream": False},
                timeout=60,
            )
            try:
                return r.json()["message"]["content"].strip()
            except json.JSONDecodeError:
                return r.text.strip()
        else:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {st.session_state.openrouter_key}"},
                json={"model": model, "messages": ctx},
                timeout=60,
            )
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(DM error: {e})"

# =========================================================
# -------------------- STREAMLIT STATE -------------------
# =========================================================

st.set_page_config("Solo Adventure", layout="wide")

defaults = {
    "char": None,
    "setting": "Fantasy Adventure",
    "history": [],
    "objects": {},
    "pending_action": None,
    "pending_skills": None,
    "pending_dc": None,
    "api_source": "ollama",
    "ollama_url": "http://127.0.0.1:11434",
    "openrouter_key": "",
    "model_list": [],
    "selected_model": "",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# -------------------- SIDEBAR ----------------------------
# =========================================================

with st.sidebar:
    st.title("🧙 Character Sheet")

    if st.session_state.char:
        c = st.session_state.char
        st.write(f"**{c.name} — Lv {c.level} {c.cls}**")
        st.caption(f"Setting: {st.session_state.setting}")
        st.progress(c.hp / c.max_hp)
        st.write(f"HP: {c.hp}/{c.max_hp}")
        
        st.markdown("**Inventory**")
        for item, qty in c.inventory.items():
            st.write(f"{item} x{qty}")

        st.divider()

        # --- NEW FEATURE: Manual Roll ---
        st.subheader("🎲 Manual Check")
        st.info("Use this if the DM asks for a roll and no buttons appear.")
        man_skill = st.selectbox("Skill", list(SKILLS.keys()))
        if st.button("Roll Manual Check"):
            roll, total = c.roll_check(man_skill)
            st.session_state.history.append({
                "role": "user",
                "content": f"[Manual Roll] I rolled {man_skill}. Result: {total} (Natural {roll})."
            })
            st.rerun()
        # --------------------------------

    st.divider()
    st.subheader("⚙ LLM Settings")

    st.session_state.api_source = st.selectbox(
        "API Source",
        ["ollama", "openrouter"],
        index=0 if st.session_state.api_source == "ollama" else 1,
    )

    if st.session_state.api_source == "ollama":
        st.session_state.ollama_url = st.text_input(
            "Ollama URL", st.session_state.ollama_url
        )
    else:
        st.session_state.openrouter_key = st.text_input(
            "OpenRouter API Key",
            st.session_state.openrouter_key,
            type="password",
        )

    if st.button("🔄 Refresh Models"):
        try:
            if st.session_state.api_source == "ollama":
                r = requests.get(f"{st.session_state.ollama_url}/api/tags", timeout=5)
                st.session_state.model_list = [m["name"] for m in r.json().get("models", [])]
            else:
                r = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {st.session_state.openrouter_key}"},
                    timeout=10,
                )
                st.session_state.model_list = sorted(
                    [m["id"] for m in r.json().get("data", [])]
                )
            st.success("Models loaded")
        except Exception as e:
            st.error(str(e))

    if st.session_state.model_list:
        st.session_state.selected_model = st.selectbox(
            "Model", st.session_state.model_list
        )

# =========================================================
# -------------------- CHARACTER CREATION ----------------
# =========================================================

if st.session_state.char is None:
    st.title("Create Character")
    
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", "Renn")
        cls = st.selectbox("Class", list(CLASSES))
    with col2:
        setting_input = st.text_input("Game Setting", "Fantasy Adventure")

    if st.button("Begin Adventure"):
        st.session_state.char = new_character(name, cls)
        st.session_state.setting = setting_input
        st.session_state.objects = starting_objects()
        
        st.session_state.history = [
            {"role": "user", "content": f"Begin the adventure in a {setting_input} setting. Describe where I start."}
        ]
        st.rerun()

    st.stop()

# =========================================================
# -------------------- TURN ENGINE -----------------------
# =========================================================

if st.session_state.history:
    last = st.session_state.history[-1]

    # Check for keyword triggers in user text
    if last["role"] == "user" and st.session_state.pending_action is None:
        # Skip if this was a manual roll (contains [Manual Roll])
        if "[Manual Roll]" not in last["content"]:
            for key, rule in ACTION_RULES.items():
                if key in last["content"].lower():
                    st.session_state.pending_action = key
                    st.session_state.pending_skills = rule["skills"]
                    st.session_state.pending_dc = DC_TABLE[rule["dc"]]
                    st.session_state.history.append(
                        {
                            "role": "assistant",
                            "content": f"This requires a roll ({rule['dc']} DC). Choose one: {', '.join(rule['skills'])}.",
                        }
                    )
                    st.rerun()

    # If no pending action, get DM response
    if last["role"] == "user" and st.session_state.pending_action is None:
        reply = call_dm(st.session_state.history)
        st.session_state.history.append(
            {"role": "assistant", "content": reply}
        )
        st.rerun()

# =========================================================
# -------------------- MAIN UI ----------------------------
# =========================================================

st.title("🐉 Solo Adventure")

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

char = st.session_state.char

if st.session_state.pending_action:
    skill = st.selectbox("Select skill", st.session_state.pending_skills)
    if st.button("🎲 Roll"):
        roll, total = char.roll_check(skill)
        success = total >= st.session_state.pending_dc

        if st.session_state.pending_action == "open chest" and success:
            if "chest" in st.session_state.objects:
                chest = st.session_state.objects["chest"]
                if not chest.looted:
                    for item, qty in chest.contents.items():
                        char.inventory[item] = char.inventory.get(item, 0) + qty
                    chest.looted = True

        st.session_state.history.append(
            {
                "role": "user",
                "content": f"Rolled {roll} ({'success' if success else 'failure'}). Resolve the outcome.",
            }
        )

        st.session_state.pending_action = None
        st.session_state.pending_skills = None
        st.session_state.pending_dc = None
        st.rerun()
else:
    if prompt := st.chat_input("What do you do?"):
        st.session_state.history.append(
            {"role": "user", "content": prompt}
        )
        st.rerun()
