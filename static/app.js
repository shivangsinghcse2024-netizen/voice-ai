const $ = (id) => document.getElementById(id);
let recorder = null, chunks = [], recorded = null;
let currentUtterance = null;
const INTERNAL_API_KEY = "WkKw9Dy12Bfv-ACX8_AiiIUk5q94o7Tktlver8BbJMyyd9xokHuUFk387JQeMgcc";

async function loadLangs() {
    try {
        const r = await fetch("/v1/languages", { 
            headers: { "X-API-Key": INTERNAL_API_KEY } 
        });
        
        if (!r.ok) {
            console.error("Failed to load languages. Status:", r.status, await r.text());
            return;
        }
        
        const data = await r.json();
        const target_languages = data.target_languages || [];
        
        const langNames = {
            "ar": "Arabic (العربية)", "bn": "Bengali (বাংলা)", "de": "German (Deutsch)",
            "en": "English", "es": "Spanish (Español)", "fr": "French (Français)",
            "gu": "Gujarati (ગુજરાતી)", "hi": "Hindi (हिन्दी)", "it": "Italian (Italiano)",
            "ja": "Japanese (日本語)", "ko": "Korean (한국어)", "mr": "Marathi (मराठी)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)", "pt": "Portuguese (Português)", "ru": "Russian (Русский)",
            "ta": "Tamil (தமிழ்)", "te": "Telugu (తెలుగు)", "tr": "Turkish (Türkçe)",
            "ur": "Urdu (اردو)", "zh": "Chinese (中文)"
        };

        const langSelect = $("lang");
        if (langSelect) {
            langSelect.replaceChildren(...target_languages.map(c => {
                const o = document.createElement("option"); 
                o.value = c; 
                o.textContent = langNames[c] || c; 
                return o;
            }));
            langSelect.value = "en";
        }
    } catch (err) {
        console.error("Network or parsing error loading languages:", err);
    }
}

// Only setup recording bindings if the record button exists on the page
if ($("rec")) {
    $("rec").addEventListener("click", async () => {
        if (recorder && recorder.state === "recording") { recorder.stop(); return; }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recorder = new MediaRecorder(stream); chunks = [];
            recorder.ondataavailable = (e) => chunks.push(e.data);
            recorder.onstop = () => {
                stream.getTracks().forEach((t) => t.stop());
                recorded = new Blob(chunks, { type: recorder.mimeType });
                $("player").src = URL.createObjectURL(recorded); $("player").hidden = false;
                $("rec").textContent = "🎙️ Record"; $("rec").classList.remove("live");
            };
            recorder.start(); $("rec").textContent = "⏹️ Stop"; $("rec").classList.add("live");
        } catch { $("status").textContent = "Microphone not available."; }
    });
}

if ($("go")) {
    $("go").addEventListener("click", async () => {
        const fileInput = $("file").files[0];
        const audioBlob = recorded || fileInput;
        if (!audioBlob) { $("status").textContent = "Choose or record audio first."; return; }
        const fd = new FormData();
        fd.append("file", audioBlob, "recording.webm"); 
        fd.append("target_language", $("lang").value || "en");
        $("go").disabled = true; $("status").textContent = "Processing..."; $("out").hidden = true;
        try {
            const r = await fetch("/v1/analyze", { method: "POST", headers: { "X-API-Key": INTERNAL_API_KEY }, body: fd });
            const d = await r.json();
            if (!r.ok) { $("status").textContent = `Error ${r.status}: ${d.detail || "failed"}`; return; }
            $("detected").textContent = `(detected: ${d.detected_language})`;
            $("transcript").textContent = d.transcript;
            $("translation").textContent = d.translation || "-";
            
            speakTranslation();

            // Store analysis results for the analytics page
            const analysisData = {
                detected: d.detected_language,
                transcript: d.transcript,
                translation: d.translation,
                voice_emotion: d.voice_emotion,
                text_emotion: d.text_emotion,
                sentiment: d.text_sentiment,
                warnings: d.warnings,
                duration: d.duration_seconds
            };
            localStorage.setItem("lastAnalysis", JSON.stringify(analysisData));

            $("out").hidden = false; $("status").textContent = `Done (${d.duration_seconds}s audio)`;
        } catch { $("status").textContent = "Network error."; }
        finally { $("go").disabled = false; }
    });
}

function speakTranslation() {
    if (!$("translation")) return;
    const text = $("translation").textContent;
    const rawLang = $("lang").value;
    
    if (!text || text === "-") return;
    if (!('speechSynthesis' in window)) return;
    
    const localeMap = {
        "ar": "ar-SA", "bn": "bn-IN", "de": "de-DE", "en": "en-US",
        "es": "es-ES", "fr": "fr-FR", "gu": "gu-IN", "hi": "hi-IN",
        "it": "it-IT", "ja": "ja-JP", "ko": "ko-KR", "mr": "mr-IN",
        "pa": "pa-IN", "pt": "pt-BR", "ru": "ru-RU", "ta": "ta-IN",
        "te": "te-IN", "tr": "tr-TR", "ur": "ur-PK", "zh": "zh-CN"
    };

    const targetLang = localeMap[rawLang] || "en-US";
    window.speechSynthesis.cancel();
    currentUtterance = new SpeechSynthesisUtterance(text);
    currentUtterance.lang = targetLang;
    window.speechSynthesis.speak(currentUtterance);
}

// Auto load languages on startup
loadLangs();

if ($("speak-btn")) $("speak-btn").addEventListener("click", speakTranslation);
if ($("replay-btn")) $("replay-btn").addEventListener("click", speakTranslation);

// --- SIDEBAR DRAWER & THEME LOGIC FOR TRANSLATOR / ANALYTICS PAGES ---

document.addEventListener("DOMContentLoaded", () => {
    const toggleBtn = document.getElementById("sidebar-toggle");
    const closeBtn = document.getElementById("close-sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    const drawer = document.getElementById("sidebar-drawer");

    if (toggleBtn && drawer && overlay) {
        function openSidebar() {
            overlay.classList.add("active");
            drawer.classList.add("active");
        }
        function closeSidebar() {
            overlay.classList.remove("active");
            drawer.classList.remove("active");
        }

        toggleBtn.addEventListener("click", openSidebar);
        if (closeBtn) closeBtn.addEventListener("click", closeSidebar);
        overlay.addEventListener("click", closeSidebar);
    }

    // Theme Toggle Logic
    const themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) {
        if (localStorage.getItem("theme") === "light") {
            document.body.classList.add("light-theme");
            themeBtn.textContent = "🌙 Switch to Dark Mode";
        }

        themeBtn.addEventListener("click", () => {
            document.body.classList.toggle("light-theme");
            const isLight = document.body.classList.contains("light-theme");
            localStorage.setItem("theme", isLight ? "light" : "dark");
            themeBtn.textContent = isLight ? "🌙 Switch to Dark Mode" : "☀️ Toggle Light / Dark";
        });
    }

    // Profile & History alerts
    const profileBtn = document.getElementById("profile-btn");
    if (profileBtn) {
        profileBtn.addEventListener("click", () => {
            const email = localStorage.getItem("userEmail") || "Logged in via Phone";
            alert(`Current User Profile:\nIdentifier: ${email}`);
        });
    }

    const historyBtn = document.getElementById("history-btn");
    if (historyBtn) {
        historyBtn.addEventListener("click", () => {
            alert("Translation history loaded from current session.");
        });
    }

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("isLoggedIn");
            window.location.href = "/";
        });
    }
});