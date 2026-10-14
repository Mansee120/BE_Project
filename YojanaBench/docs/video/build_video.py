"""
build_video.py
--------------
Builds YojanaBench_Explained_Hindi.mp4 — a narrated explainer video covering
every dashboard tab and the mathematical calculations used in the project.

Pipeline (all local, offline after first run):
    1. Each SCENE -> an HTML slide  -> screenshot (Chrome headless) -> PNG
    2. Each SCENE -> Hindi narration -> MP3 (edge-tts, hi-IN-MadhurNeural)
    3. PNG + MP3 -> MP4 segment (ffmpeg)  -> concatenated into the final video

Run:
    python docs/video/build_video.py
"""
import asyncio
import os
import shutil
import subprocess
import sys

import edge_tts

# Console may default to cp1252 on Windows; force UTF-8 for Hindi prints.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# --------------------------------------------------------------------------
# Paths / tools
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))

CHROME = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
FFMPEG = os.path.join(PROJECT, "tools", "ffmpeg-9.0.2-essentials_build", "bin", "ffmpeg.exe")
FFPROBE = os.path.join(PROJECT, "tools", "ffmpeg-9.0.2-essentials_build", "bin", "ffprobe.exe")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or FFMPEG
    FFPROBE = shutil.which("ffprobe") or FFPROBE

VOICE = "hi-IN-MadhurNeural"          # male Hindi neural voice
WORK = os.path.join(HERE, "work")
OUT_MP4 = os.path.join(PROJECT, "docs", "YojanaBench_Explained_Hindi.mp4")

os.makedirs(WORK, exist_ok=True)

# --------------------------------------------------------------------------
# Scenes: dashboard tabs + maths.  Hindi narration (voice), bilingual slide.
# --------------------------------------------------------------------------
SCENES = [
    {
        "kicker": "FINAL YEAR ENGINEERING PROJECT",
        "title": "YojanaBench",
        "subtitle": "भारत की कल्याणकारी योजनाओं के लिए दस्तावेज़-तर्क बेंचमार्क",
        "bullets": ["India Welfare-Scheme Document Reasoning",
                    "Multi-Agent Audit Pipeline",
                    "Fully offline · reproducible · zero cost"],
        "eq": "",
        "voice": "नमस्ते। पेश है योजनाबेंच — भारत की कल्याणकारी योजनाओं के लिए बनाया गया "
                 "पहला दस्तावेज़-तर्क बेंचमार्क और बहु-एजेंट ऑडिट पाइपलाइन। यह पूरी तरह ऑफ़लाइन, "
                 "दोहराने योग्य और शून्य लागत पर चलता है।",
    },
    {
        "kicker": "OVERVIEW",
        "title": "यह सिस्टम क्या करता है?",
        "subtitle": "आवेदन → निर्णय → लाभ → अपील",
        "bullets": ["आवेदक की स्थिति और दस्तावेज़ पढ़ता है",
                    "eligible / ineligible / needs_info का फ़ैसला",
                    "लाभ राशि (entitlement) की गणना",
                    "ज़रूरी दस्तावेज़ और अपील का रास्ता"],
        "eq": "",
        "voice": "यह सिस्टम आवेदक की स्थिति और जमा किए गए दस्तावेज़ों को पढ़ता है और बताता है "
                 "कि वह योजना के लिए पात्र है या नहीं — पात्र, अपात्र, या जानकारी अपूर्ण। साथ ही "
                 "यह लाभ राशि की गणना करता है, ज़रूरी दस्तावेज़ बताता है, और अपील की प्रक्रिया भी दिखाता है।",
    },
    {
        "kicker": "DASHBOARD",
        "title": "डैशबोर्ड — अवलोकन",
        "subtitle": "कोष आँकड़े · मुख्य मीट्रिक · एजेंट पाइपलाइन",
        "bullets": ["Corpus statistics — 10 schemes, 56 QA pairs",
                    "Run full benchmark button",
                    "Metric cards + accuracy by category chart",
                    "Agent pipeline diagram + Accuracy report"],
        "eq": "",
        "voice": "डैशबोर्ड सबसे पहला पेज है। यहाँ कोष से जुड़े आँकड़े दिखते हैं — दस योजनाएँ और "
                 "छप्पन मानव-सत्यापित प्रश्न-उत्तर जोड़े। रन फुल बेंचमार्क बटन दबाने पर मुख्य मीट्रिक "
                 "कार्ड और श्रेणी-वार चार्ट भर जाते हैं, और नीचे एजेंट पाइपलाइन तथा सटीकता रिपोर्ट दिखती है।",
    },
    {
        "kicker": "ARCHITECTURE",
        "title": "आठ-एजेंट पाइपलाइन",
        "subtitle": "प्रत्येक एजेंट स्वतंत्र रूप से निरीक्षण योग्य",
        "bullets": ["1 Corpus   2 Intake   3 RAG   4 Entitlement",
                    "5 Verification   6 Orchestrator",
                    "7 Evaluation   8 Appeal",
                    "कम भरोसे पर human-approval gate"],
        "eq": "",
        "voice": "पूरा सिस्टम आठ एजेंट से बना है — कोर्पस, इंटेक, रैग, एंटाइटलमेंट, वेरिफिकेशन, "
                 "ऑर्केस्ट्रेटर, इवैल्यूएशन और अपील। हर एजेंट को अलग से जाँचा जा सकता है, और "
                 "ऑर्केस्ट्रेटर कम भरोसे पर मानव-स्वीकृति गेट खोल देता है।",
    },
    {
        "kicker": "MATHS 1 / 4",
        "title": "पात्रता नियम इंजन",
        "subtitle": "त्रि-अवस्था तर्क: True / False / Unknown",
        "bullets": ["सभी शर्तें True  →  eligible",
                    "कोई भी शर्त False  →  ineligible",
                    "कोई भी शर्त Unknown  →  needs_info"],
        "eq": "verdict = eligible if all(True)  |  ineligible if any(False)  |  else needs_info",
        "voice": "अब गणित। पात्रता इंजन हर नियम की जाँच तीन अवस्थाओं में करता है — सत्य, असत्य, "
                 "या अज्ञात। यदि सभी शर्तें सत्य हों तो पात्र; कोई एक भी असत्य हो तो अपात्र; और यदि "
                 "कोई जानकारी अज्ञात हो तो निर्णय होता है — जानकारी अपूर्ण।",
    },
    {
        "kicker": "MATHS 2 / 4",
        "title": "लाभ राशि की गणना",
        "subtitle": "नियम-आधारित, अनुमान नहीं",
        "bullets": ["प्रति-सदस्य और श्रेणी-आधारित सूत्र",
                    "राशि हमेशा कोड में गिनी जाती है",
                    "इसीलिए entitlement error लगभग शून्य"],
        "eq": "benefit = Σ (rate × members)   e.g.  PDS = ₹(rice + wheat) × family_size",
        "voice": "लाभ राशि की गणना नियमों और सूत्रों से होती है, अनुमान से नहीं। उदाहरण के लिए "
                 "खाद्य सुरक्षा योजना में प्रति व्यक्ति चावल और गेहूँ की दर परिवार के सदस्यों की "
                 "संख्या से गुणा होती है। यह पूरा गणित कोड में होता है, इसलिए त्रुटि लगभग शून्य रहती है।",
    },
    {
        "kicker": "MATHS 3 / 4",
        "title": "मूल्यांकन मेट्रिक्स",
        "subtitle": "मॉडल को कैसे मापते हैं",
        "bullets": ["Token F1 = 2 · P · R / (P + R)",
                    "Exact Match = prediction == reference",
                    "Verdict accuracy = correct / total",
                    "Entitlement error = mean |pred − ref|"],
        "eq": "ECE = Σ (|Bm| / N) · |acc(Bm) − conf(Bm)|",
        "voice": "मूल्यांकन के लिए कई मेट्रिक्स हैं। टोकन एफ-वन, प्रिसीजन और रिकॉल का संतुलित औसत है। "
                 "एग्जैक्ट मैच तब एक होता है जब जवाब पूरी तरह मेल खाए। वरडिक्ट एक्सुरेसी सही निर्णयों "
                 "का अनुपात है, और एंटाइटलमेंट एरर औसत राशि-अंतर बताता है। कैलिब्रेशन ई-सी-ई बताता है "
                 "कि विश्वास कितना ईमानदार है।",
    },
    {
        "kicker": "MATHS 4 / 4",
        "title": "हाइब्रिड रिट्रीवल",
        "subtitle": "BM25 + TF-IDF का मिश्रण",
        "bullets": ["BM25 — term frequency और rarity",
                    "TF-IDF — शब्दों का महत्व",
                    "मिश्रण सर्वोत्तम clause चुनता है"],
        "eq": "score(q, d) = 0.5 · BM25 + 0.5 · TF-IDF",
        "voice": "सही नियम खोजने के लिए हम हाइब्रिड रिट्रीवल इस्तेमाल करते हैं। बी-एम-ट्वेंटी-फाइव और "
                 "टी-एफ-आई-डी-एफ दोनों स्कोर को मिलाकर सबसे प्रासंगिक शर्त चुनी जाती है, जिससे हर "
                 "निर्णय का स्रोत स्पष्ट रहता है।",
    },
    {
        "kicker": "PAGE",
        "title": "ऑडिट अ केस",
        "subtitle": "एक आवेदन पर पूरी पाइपलाइन",
        "bullets": ["फ़ॉर्म भरें · दस्तावेज़ चुनें · Run audit",
                    "Verdict card + confidence bar",
                    "Evidence citations · Agent trace timeline",
                    "Auto-generated appeal letter"],
        "eq": "",
        "voice": "ऑडिट अ केस पेज पर एक असली आवेदन चलाया जाता है। फ़ॉर्म में जानकारी भरें, दस्तावेज़ "
                 "चुनें और ऑडिट चलाएँ। नतीजे में निर्णय, भरोसा-स्तर, हर निर्णय के पीछे के साक्ष्य, "
                 "एजेंट ट्रेस और अपील पत्र दिखते हैं।",
    },
    {
        "kicker": "PAGE",
        "title": "बेंचमार्क पेज",
        "subtitle": "56 प्रश्न-उत्तर जोड़ों पर स्कोरिंग",
        "bullets": ["फ़िल्टर: scheme और category",
                    "प्रति-आइटम परिणाम तालिका",
                    "Ground truth · Prediction · EM · F1"],
        "eq": "",
        "voice": "बेंचमार्क पेज पर योजना और श्रेणी के फ़िल्टर लगाकर छप्पन प्रश्न-उत्तर जोड़ों पर "
                 "स्कोरिंग की जाती है, और हर आइटम का सत्य बनाम अनुमान, एग्जैक्ट मैच तथा एफ-वन दिखता है।",
    },
    {
        "kicker": "RESEARCH",
        "title": "एब्लेशन अध्ययन",
        "subtitle": "हर भाग का योगदान मापना",
        "bullets": ["full — पूरी पाइपलाइन (baseline)",
                    "no_verification — सत्यापन हटाया",
                    "llm_math — अनुमान आधारित गणित",
                    "no_counterfactuals — केवल आधार आइटम"],
        "eq": "Δ verdict accuracy = full − variant      e.g.  −6.1 pp",
        "voice": "एब्लेशन अध्ययन हमारा शोध योगदान है। हम एक-एक भाग हटाकर देखते हैं कि प्रदर्शन कितना "
                 "गिरता है। सत्यापन हटाने पर सटीकता लगभग छह प्रतिशत गिरती है, और अनुमान आधारित गणित "
                 "अपनाने पर लाभ-राशि की त्रुटि कई सौ रुपये तक बढ़ जाती है।",
    },
    {
        "kicker": "PAGE",
        "title": "स्कीम कॉर्पस और अपील रूटिंग",
        "subtitle": "10 योजनाओं का संरचित डेटा",
        "bullets": ["Eligibility · Entitlement · Documents · Appeal",
                    "Grievance hierarchy, प्रत्येक स्तर पर deadline",
                    "ड्राफ़्ट अपील पत्र"],
        "eq": "",
        "voice": "स्कीम कॉर्पस पेज पर दस योजनाओं का संरचित विवरण है — पात्रता, लाभ, दस्तावेज़ और "
                 "अपील श्रेणी। अपील रूटिंग पेज शिकायत-व्यवस्था और ड्राफ़्ट अपील पत्र दिखाता है।",
    },
    {
        "kicker": "EVIDENCE",
        "title": "सटीकता रिपोर्ट",
        "subtitle": "चार तालिकाएँ · CSV निर्यात",
        "bullets": ["Overall metrics",
                    "Per-scheme accuracy",
                    "Edge-case vs base-case",
                    "Ablation comparison"],
        "eq": "python report.py  →  reports/*.csv",
        "voice": "डैशबोर्ड की सटीकता रिपोर्ट चार तालिकाएँ बनाती है — समग्र मीट्रिक, प्रति-योजना "
                 "सटीकता, कठिन बनाम सामान्य मामले, और एब्लेशन तुलना। यही रिपोर्ट सी-एस-वी फ़ाइलों में "
                 "भी निकाली जा सकती है।",
    },
    {
        "kicker": "THANK YOU",
        "title": "धन्यवाद",
        "subtitle": "YojanaBench — India Welfare-Scheme Document Reasoning",
        "bullets": ["Offline · Reproducible · Explainable",
                    "Deterministic maths · Optional LLM polish"],
        "eq": "",
        "voice": "यह था योजनाबेंच का परिचय। यह ऑफ़लाइन, दोहराने योग्य और स्पष्ट है, जहाँ फ़ैसले "
                 "नियमों से होते हैं और भाषा को केवल वैकल्पिक रूप से सजाया जाता है। धन्यवाद।",
    },
]


def slide_html(scene, idx, total):
    bullets = "".join(f"<li>{b}</li>" for b in scene.get("bullets", []))
    eq = (f'<div class="eq">{scene["eq"]}</div>' if scene.get("eq") else "")
    sub = (f'<p class="sub">{scene["subtitle"]}</p>' if scene.get("subtitle") else "")
    return f"""<!DOCTYPE html><html lang="hi"><head><meta charset="UTF-8">
<style>
  html,body{{margin:0;width:1280px;height:720px;overflow:hidden;
    font-family:"Nirmala UI","Mangal",sans-serif;}}
  body{{background:linear-gradient(135deg,#0f3460 0%,#16213e 60%,#1a1a2e 100%);
    color:#fff;position:relative;padding:70px 90px;box-sizing:border-box;}}
  .bar{{position:absolute;top:0;left:0;height:8px;width:100%;
    background:linear-gradient(90deg,#2b6cb0,#7fd4a0);}}
  .kicker{{font-size:19px;letter-spacing:3px;color:#7fd4a0;font-weight:700;margin-bottom:14px;}}
  h1{{font-size:60px;line-height:1.12;margin:0 0 12px;font-weight:800;}}
  .sub{{font-size:27px;color:#c7d3ee;margin:0 0 22px;}}
  ul{{list-style:none;padding:0;margin:14px 0 0;}}
  li{{font-size:25px;color:#e6ecff;margin:12px 0;padding-left:40px;position:relative;}}
  li:before{{content:"";position:absolute;left:0;top:11px;width:15px;height:15px;
    background:#7fd4a0;border-radius:50%;}}
  .eq{{margin-top:26px;font-size:27px;color:#0f3460;background:#7fd4a0;
    display:inline-block;padding:14px 22px;border-radius:10px;font-weight:700;
    font-family:Consolas,"Nirmala UI",monospace;}}
  .foot{{position:absolute;bottom:26px;right:90px;font-size:18px;color:#8ea2c9;}}
  .idx{{position:absolute;bottom:26px;left:90px;font-size:18px;color:#8ea2c9;}}
</style></head>
<body>
  <div class="bar"></div>
  <div class="kicker">{scene.get('kicker','')}</div>
  <h1>{scene['title']}</h1>
  {sub}
  <ul>{bullets}</ul>
  {eq}
  <div class="idx">{idx} / {total}</div>
  <div class="foot">YojanaBench · Final Year Project</div>
</body></html>"""


async def _tts(text, out_path):
    communicate = edge_tts.Communicate(text, VOICE, rate="-8%")
    await communicate.save(out_path)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def chrome_screenshot(html_path, png_path, profile):
    url = "file:///" + html_path.replace("\\", "/")
    run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=1280,720",
         f"--user-data-dir={profile}", f"--screenshot={png_path}", url])


def audio_duration(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", path],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def build_segment(png, mp3, seg_path):
    dur = audio_duration(mp3) + 0.7          # small tail padding
    run([FFMPEG, "-y", "-loop", "1", "-framerate", "25", "-i", png, "-i", mp3,
         "-vf", "scale=1280:720,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
         "-tune", "stillimage", "-r", "25", "-c:a", "aac", "-b:a", "192k",
         "-af", "apad=pad_dur=0.7", "-t", f"{dur:.3f}", seg_path])


async def main():
    total = len(SCENES)
    segments = []
    profile = os.path.join(WORK, "chrome-profile")

    for i, scene in enumerate(SCENES, start=1):
        tag = f"scene_{i:02d}"
        html_path = os.path.join(WORK, tag + ".html")
        png_path = os.path.join(WORK, tag + ".png")
        mp3_path = os.path.join(WORK, tag + ".mp3")
        seg_path = os.path.join(WORK, tag + ".mp4")

        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(slide_html(scene, i, total))

        print(f"[{i}/{total}] {scene['title']} — slide")
        chrome_screenshot(html_path, png_path, profile)

        print(f"[{i}/{total}] {scene['title']} — voice")
        await _tts(scene["voice"], mp3_path)

        print(f"[{i}/{total}] {scene['title']} — segment")
        build_segment(png_path, mp3_path, seg_path)
        segments.append(seg_path)

    # concatenate all segments
    list_path = os.path.join(WORK, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as fh:
        for seg in segments:
            fh.write(f"file '{seg.replace(chr(92), '/')}'\n")

    print("Assembling final video ...")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
         "-c", "copy", OUT_MP4])
    print("DONE ->", OUT_MP4)


if __name__ == "__main__":
    asyncio.run(main())
