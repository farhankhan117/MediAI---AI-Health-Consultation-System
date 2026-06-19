from groq import Groq
from config import GROQ_API_KEY
import base64, os, json, re, io

client = Groq(api_key=GROQ_API_KEY)

# ── GUARANTEED QUESTION BANK (fallback if AI misbehaves) ─────────────────
QUESTION_BANK = [
    ("Do you have a fever?",
     ["Yes — high fever (above 102°F)", "Yes — mild fever", "No fever", "Not sure"]),
    ("How long have you had this problem?",
     ["Just started today", "1-2 days", "3-5 days", "More than a week"]),
    ("Do you have a headache or body aches?",
     ["Yes — headache", "Yes — body aches", "Both headache and body aches", "No"]),
    ("Are you coughing or having trouble breathing?",
     ["Yes — coughing", "Yes — breathing difficulty", "Both", "No"]),
    ("Do you feel weak, tired, or have no appetite?",
     ["Yes — very weak/tired", "Yes — no appetite", "Both", "No"]),
    ("Any nausea, vomiting, or stomach pain?",
     ["Yes — nausea", "Yes — vomiting", "Yes — stomach pain", "None of these"]),
    ("Any skin rash, redness, or swelling?",
     ["Yes — rash", "Yes — redness/itching", "Yes — swelling", "No"]),
    ("Any chills, shivering, or night sweats?",
     ["Yes — chills/shivering", "Yes — night sweats", "Both", "No"]),
]

# ── PROMPTS ───────────────────────────────────────────────────────────────

DOCTOR_QUESTION_PROMPT = """You are MediAI, a friendly AI doctor collecting patient symptoms.

Your ONLY job right now is to ask ONE follow-up symptom question based on what the patient told you.

STRICT OUTPUT FORMAT — your entire response must be exactly this:
QUESTION: [one short question in plain English]
OPTIONS: ["option1", "option2", "option3", "option4"]

Examples of valid responses:
QUESTION: Do you have a fever?
OPTIONS: ["Yes, high fever", "Yes, mild fever", "No fever", "Not sure"]

QUESTION: How long have you had this problem?
OPTIONS: ["1-2 days", "3-5 days", "About 1 week", "More than 1 week"]

QUESTION: Do you feel nauseous or have you vomited?
OPTIONS: ["Yes, nauseous", "Yes, vomited", "Both", "No"]

RULES:
- Start your response with QUESTION: — nothing before it
- ONE question only
- 3-4 short option choices
- Ask about symptoms you have NOT asked yet
- Do NOT give any diagnosis, advice, or analysis"""

CONCLUSION_PROMPT = """You are MediAI, an expert AI health consultation assistant.

Based on ALL the symptoms the patient described, give the FINAL health report.

Use EXACTLY this structure with all sections:

🔍 ANALYSIS:
[Thorough analysis connecting all the symptoms the patient described]

🦠 POSSIBLE CONDITIONS:
[List 2-3 most likely conditions. For each: name + brief explanation of why it fits]

⚠️ SEVERITY ASSESSMENT:
[State Mild / Moderate / Severe clearly and explain the reasoning]

✅ PRECAUTIONS & RECOMMENDATIONS:
[Practical steps the patient should take — rest, hydration, monitoring etc.]

💊 COMMON MEDICINES:
[List common OTC medicines that may help. Always add: consult a doctor before taking any medicine]

🚨 WHEN TO SEE A DOCTOR IMMEDIATELY:
[List specific warning signs that require urgent medical attention]

⚠️ DISCLAIMER:
This is AI-generated health information only and NOT a medical diagnosis. Always consult a qualified and licensed doctor for proper medical advice, diagnosis, and treatment.

OPTIONS: ["Tell me more about the top condition", "What diet should I follow?", "Show home remedies", "How can I prevent this?"]"""

FOLLOWUP_PROMPT = """You are MediAI, a helpful health assistant.

The patient already received their full diagnosis report. They are now asking ONE specific follow-up question.

Your response must:
- Answer ONLY the specific thing they asked
- Write in plain readable sentences — NO emoji section headers
- NO 🔍 ANALYSIS or ⚠️ SEVERITY or any section formatting
- Be concise — 4 to 6 sentences maximum
- End with: OPTIONS: ["option1", "option2", "option3"]"""

IMAGE_ANALYSIS_PROMPT = """You are a medical image analysis AI. Carefully examine this medical image.

Provide a thorough analysis using this exact structure:

🔍 ANALYSIS:
[Describe precisely what you observe — colors, textures, shapes, any abnormalities, location and size]

🦠 POSSIBLE CONDITIONS:
[List 2-3 possible medical conditions that match what you see, with brief explanation for each]

⚠️ SEVERITY ASSESSMENT:
[State Mild / Moderate / Severe and explain why]

✅ PRECAUTIONS & RECOMMENDATIONS:
[What steps the patient should take next]

💊 COMMON MEDICINES:
[Medicines that may help — always say consult doctor before taking]

🚨 WHEN TO SEE A DOCTOR IMMEDIATELY:
[Urgent signs that need immediate medical attention]

⚠️ DISCLAIMER:
This is AI image analysis only and NOT a medical diagnosis. Always consult a qualified doctor for proper examination and diagnosis.

OPTIONS: ["Tell me more about the likely condition", "What medicines may help?", "Home remedies", "Is this serious?"]"""

IMAGE_QA_PROMPT = """You are MediAI — a doctor asking questions about a medical image that could not be analyzed automatically.

Ask ONE clear question to understand what the patient uploaded.

STRICT FORMAT — start with QUESTION: immediately:
QUESTION: [your question about the image]
OPTIONS: ["choice1", "choice2", "choice3", "choice4"]"""


# ── PARSER ────────────────────────────────────────────────────────────────

def parse_response(raw):
    """Returns (type, text, options) — type is 'question' or 'conclusion'"""
    if not raw:
        return "conclusion", "No response received. Please try again.", []

    raw = raw.strip()
    first_line = raw.split("\n")[0].upper()

    # Check if it's a question
    if first_line.startswith("QUESTION:") or first_line.startswith("QUESTION :"):
        question, options = "", []
        qm = re.search(r'QUESTION\s*:\s*(.+?)(?=OPTIONS\s*:|$)', raw, re.IGNORECASE | re.DOTALL)
        if qm:
            question = qm.group(1).strip()
        om = re.search(r'OPTIONS\s*:\s*(\[.*?\])', raw, re.IGNORECASE | re.DOTALL)
        if om:
            try:
                options = json.loads(om.group(1))
            except Exception:
                options = ["Yes", "No", "Sometimes"]
        if not question:
            question = raw.replace("QUESTION:", "").split("OPTIONS:")[0].strip()
        if not options:
            options = ["Yes", "No", "Sometimes"]
        return "question", question, options

    # It's a conclusion/answer
    options, text = [], raw
    om = re.search(r'OPTIONS\s*:\s*(\[.*?\])', raw, re.IGNORECASE | re.DOTALL)
    if om:
        try:
            options = json.loads(om.group(1))
        except Exception:
            pass
        text = raw[:om.start()].strip()
    if not options:
        options = ["Tell me more", "Home remedies", "See a doctor?"]
    return "conclusion", text, options


# ── CORE: ASK QUESTION ────────────────────────────────────────────────────

def ask_question(history, profile=None, q_number=0):
    """
    Returns a QUESTION: format response — guaranteed.
    Tries AI twice, then falls back to hardcoded bank.
    """
    ctx  = _profile(profile)
    msgs = [{"role": "system", "content": DOCTOR_QUESTION_PROMPT}]
    if ctx:
        msgs.append({"role": "system", "content": f"Patient info: {ctx}"})
    msgs.extend(history[-10:])

    # Attempt 1 — normal AI call
    try:
        r1 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs, max_tokens=160, temperature=0.4)
        text1 = r1.choices[0].message.content.strip()
        if text1.upper().startswith("QUESTION:"):
            print(f"[Q] AI success: {text1[:80]}")
            return text1
        print(f"[Q] AI wrong format: {text1[:80]}")
    except Exception as e:
        print(f"[Q] Attempt 1 error: {e}")

    # Attempt 2 — ultra strict
    try:
        summary = " | ".join(
            m.get("content","")[:50]
            for m in history[-4:]
            if m.get("role") in ("user","assistant")
        )
        r2 = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":(
                    "Respond with ONLY these two lines, nothing else:\n"
                    "QUESTION: [a short symptom question]\n"
                    'OPTIONS: ["Yes","No","Sometimes","Not sure"]\n'
                    "First word must be QUESTION:"
                )},
                {"role":"user","content":f"Context: {summary}. Ask one new symptom question."}
            ],
            max_tokens=100, temperature=0.2)
        text2 = r2.choices[0].message.content.strip()
        if text2.upper().startswith("QUESTION:"):
            print(f"[Q] Strict AI success: {text2[:80]}")
            return text2
    except Exception as e:
        print(f"[Q] Attempt 2 error: {e}")

    # Fallback — hardcoded bank
    idx = q_number % len(QUESTION_BANK)
    q, opts = QUESTION_BANK[idx]
    print(f"[Q] Using bank #{idx}: {q}")
    return f"QUESTION: {q}\nOPTIONS: {json.dumps(opts)}"


# ── CORE: GIVE CONCLUSION ─────────────────────────────────────────────────

def give_conclusion(history, profile=None):
    """Generate full structured conclusion report"""
    ctx  = _profile(profile)
    msgs = [{"role": "system", "content": CONCLUSION_PROMPT}]
    if ctx:
        msgs.append({"role": "system", "content": f"Patient info: {ctx}"})
    msgs.extend(history[-14:])
    msgs.append({
        "role": "user",
        "content": (
            "I have answered all your questions. "
            "Now please give me the complete final health report with all sections."
        )
    })
    print("[CONCLUSION] Generating full report...")
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs, max_tokens=1800, temperature=0.5)
        result = r.choices[0].message.content
        print(f"[CONCLUSION] length={len(result)}")
        return result
    except Exception as e:
        print(f"[CONCLUSION ERROR] {e}")
        return (
            "🔍 ANALYSIS:\nCould not reach AI server.\n\n"
            f"⚠️ SEVERITY ASSESSMENT:\nError: {str(e)}\n\n"
            "✅ PRECAUTIONS & RECOMMENDATIONS:\n• Check internet connection and try again.\n\n"
            "⚠️ DISCLAIMER:\nAlways consult a qualified doctor.\n\n"
            'OPTIONS: ["Try again"]'
        )


# ── FOLLOWUP (short plain answer) ─────────────────────────────────────────

def ask_followup(question, diagnosis, profile=None):
    ctx = _profile(profile)
    MAP = {
        "tell me more":   "Explain the most likely condition in detail — what it is, what causes it, how it progresses.",
        "home remedies":  "Give 5 specific practical home remedies the patient can try.",
        "diet":           "Give a specific diet plan — 4 foods to eat, 4 to avoid, and hydration advice.",
        "prevent":        "Give 4-5 specific ways to prevent this condition.",
        "medicine":       "List 4 common medicines with what each does. Say consult doctor before taking.",
        "exercise":       "Describe 3 safe exercises and 2 things to avoid.",
        "contagious":     "Explain whether this spreads to others and how.",
        "serious":        "Explain what complications can arise if this is left untreated.",
        "doctor":         "Explain when to urgently visit a doctor and which specialist.",
    }
    inst = "Answer specifically what was asked in 4-5 plain sentences."
    for k, v in MAP.items():
        if k in question.lower():
            inst = v
            break

    prompt = (
        f"{ctx}"
        f"The patient's diagnosis: {diagnosis[:400]}\n\n"
        f"Patient's question: {question}\n\n"
        f"Instruction: {inst}\n\n"
        "Write plain sentences only. Zero emoji. Zero section headers.\n"
        "After your answer write on a new line:\n"
        'OPTIONS: ["related option 1", "related option 2", "related option 3"]'
    )
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content": FOLLOWUP_PROMPT},
                {"role":"user",  "content": prompt}
            ],
            max_tokens=400, temperature=0.6)
        return r.choices[0].message.content
    except Exception as e:
        return f"Could not retrieve that information.\n\nOPTIONS: [\"Try again\"]"


# ── GENERAL QUERY ─────────────────────────────────────────────────────────

def ask_groq(msg, profile=None):
    ctx = _profile(profile)
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content": CONCLUSION_PROMPT},
                {"role":"user",  "content": ctx + msg}
            ],
            max_tokens=1600, temperature=0.6)
        return r.choices[0].message.content
    except Exception as e:
        return (f"🔍 ANALYSIS:\nError: {str(e)}\n\n"
                "⚠️ DISCLAIMER:\nAlways consult a doctor.\n\nOPTIONS: [\"Try again\"]")


# ── GREET ─────────────────────────────────────────────────────────────────

def greet_patient(profile):
    name = profile.get("name","").strip()
    cond = profile.get("known_conditions","").strip()
    age  = profile.get("age","").strip()
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"You are MediAI, a warm and professional health assistant."},
                {"role":"user","content":(
                    f"Patient profile saved — Name: {name or 'Unknown'}, "
                    f"Age: {age or 'Unknown'}, Known conditions: {cond or 'None'}.\n"
                    "Write a warm 3-sentence greeting. Address by first name. "
                    "Confirm profile is saved and responses will be personalized. "
                    "End by asking how you can help today."
                )}
            ],
            max_tokens=120, temperature=0.8)
        return r.choices[0].message.content
    except Exception:
        return (f"✅ Profile saved! "
                f"{'Hello ' + name + '! ' if name else ''}"
                f"Your details are saved. How can I help you today?")


# ── IMAGE ANALYSIS ────────────────────────────────────────────────────────

def analyze_image_with_groq(image_path, profile=None):
    """Read → resize → base64 → Groq vision → full structured report"""
    print(f"[IMAGE] Path: {image_path}")
    clean = os.path.normpath(image_path.strip())

    if not os.path.isfile(clean):
        return "conclusion", (
            "🔍 ANALYSIS:\nImage file not found.\n\n"
            "✅ PRECAUTIONS & RECOMMENDATIONS:\n"
            "• Click the Image button again and reselect your image.\n\n"
            "⚠️ DISCLAIMER:\nAlways consult a qualified doctor."
        ), ["Try again"]

    try:
        with open(clean, "rb") as f:
            raw = f.read()
        print(f"[IMAGE] Read {len(raw)/1024:.1f} KB")

        ext  = os.path.splitext(clean)[1].lower().lstrip(".")
        mime_map = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png",
                    "webp":"image/webp","bmp":"image/png","gif":"image/gif"}
        mime = mime_map.get(ext, "image/jpeg")

        # Resize with PIL
        try:
            from PIL import Image as PILImg
            img = PILImg.open(io.BytesIO(raw))
            if img.mode not in ("RGB","L"):
                img  = img.convert("RGB")
                mime = "image/jpeg"
            w, h = img.size
            if max(w, h) > 1024:
                scale = 1024 / max(w, h)
                img   = img.resize((int(w*scale), int(h*scale)), PILImg.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG" if "jpeg" in mime else "PNG", quality=85)
            raw  = buf.getvalue()
            print(f"[IMAGE] After resize: {len(raw)/1024:.1f} KB, size={img.size}")
        except ImportError:
            print("[IMAGE] PIL not found — using raw bytes (run: pip install Pillow)")
        except Exception as pe:
            print(f"[IMAGE] PIL error: {pe}")

        b64    = base64.b64encode(raw).decode("utf-8")
        ctx    = _profile(profile)
        prompt = (ctx + "\n" + IMAGE_ANALYSIS_PROMPT) if ctx else IMAGE_ANALYSIS_PROMPT
        print(f"[IMAGE] MIME={mime}, b64={len(b64)} chars")

        for model in ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"]:
            print(f"[IMAGE] Trying {model}...")
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"user","content":[
                        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}},
                        {"type":"text","text":prompt}
                    ]}],
                    max_tokens=1400, temperature=0.5)
                result = resp.choices[0].message.content
                print(f"[IMAGE] {model} → {len(result)} chars")
                if len(result.strip()) > 60:
                    print("[IMAGE] ✅ Vision success!")
                    _, text, opts = parse_response(result)
                    return "conclusion", text, opts or ["Tell me more","What medicines?","Is this serious?"]
            except Exception as e:
                print(f"[IMAGE] {model} error: {e}")

        # Vision unavailable → Q&A session
        return "image_qa_start", "", []

    except Exception as e:
        print(f"[IMAGE ERROR] {e}")
        return "conclusion", (
            f"🔍 ANALYSIS:\nError reading image: {str(e)}\n\n"
            "✅ PRECAUTIONS & RECOMMENDATIONS:\n• Use a JPG or PNG file under 4MB.\n\n"
            "⚠️ DISCLAIMER:\nAlways consult a qualified doctor."
        ), ["Try different image"]


def start_image_qa(profile=None):
    ctx  = _profile(profile)
    msgs = [{"role":"system","content": IMAGE_QA_PROMPT}]
    if ctx:
        msgs.append({"role":"system","content": ctx})
    msgs.append({"role":"user","content":"I uploaded a medical image for analysis."})
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs, max_tokens=160, temperature=0.5)
        return r.choices[0].message.content.strip()
    except Exception:
        return ('QUESTION: What part of your body does the image show?\n'
                'OPTIONS: ["Skin / rash", "Eye", "Throat / mouth", "Wound", "X-ray or scan"]')


# ── PDF ───────────────────────────────────────────────────────────────────

def analyze_pdf_with_groq(pdf_text, profile=None):
    ctx    = _profile(profile)
    prompt = (
        f"{ctx}"
        "Analyze this medical report carefully. Explain every test value in simple language. "
        "Mark any abnormal values clearly.\n\n"
        "Use ALL sections: 🔍 ANALYSIS, 🦠 POSSIBLE CONDITIONS, ⚠️ SEVERITY ASSESSMENT, "
        "✅ PRECAUTIONS & RECOMMENDATIONS, 💊 COMMON MEDICINES, "
        "🚨 WHEN TO SEE A DOCTOR IMMEDIATELY, ⚠️ DISCLAIMER\n\n"
        'After DISCLAIMER add: OPTIONS: ["Explain abnormal values", "What diet?", "Need follow-up tests?", "Is this serious?"]\n\n'
        f"=== MEDICAL REPORT ===\n{pdf_text[:3000]}"
    )
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content": CONCLUSION_PROMPT},
                      {"role":"user",  "content": prompt}],
            max_tokens=1800, temperature=0.5)
        return r.choices[0].message.content
    except Exception as e:
        return (f"🔍 ANALYSIS:\nError: {str(e)}\n\n"
                "⚠️ DISCLAIMER:\nAlways consult your doctor.\n\nOPTIONS: [\"Try again\"]")


# ── HELPER ────────────────────────────────────────────────────────────────

def _profile(p):
    if not p: return ""
    n = p.get("name",""); a = p.get("age",""); g = p.get("gender","")
    b = p.get("blood_pressure",""); c = p.get("known_conditions","")
    if any([n,a,g,b,c]):
        return f"Patient — Name: {n}, Age: {a}, Gender: {g}, BP: {b}, Conditions: {c}\n\n"
    return ""