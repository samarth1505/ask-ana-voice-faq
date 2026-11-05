"use strict";
const $ = (id) => document.getElementById(id);
const callBtn = $("call"), statusEl = $("status"), levelEl = $("level"),
      logEl = $("log"), variantSel = $("variant"), backendsEl = $("backends");

// ---- tunables (energy-based VAD; tune for your room, headphones recommended) ----
const SILENCE_MS = 900;      // trailing silence that ends a turn
const MIN_UTTER_MS = 350;    // ignore sub-blips
const MAX_UTTER_MS = 15000;  // safety cap
const START_FRAMES = 7;      // consecutive loud frames to begin a turn (~120ms)
const BARGE_FRAMES = 7;      // frames of speech needed to interrupt Priya (barge-in)

let calling = false, state = "idle";   // idle|listening|recording|thinking|speaking
let stream, audioCtx, analyser, buf, raf;
let rec, chunks = [], recStart = 0, lastLoud = 0, loudStreak = 0, emaNoise = 0.01;
let player = null;

// ---------- helpers ----------
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) });
  return r.json();
}
function setState(s, msg) {
  state = s;
  if (msg) { statusEl.textContent = msg; statusEl.classList.toggle("live", calling); }
}
function addMsg(role, text, trace, alt) {
  const d = document.createElement("div");
  d.className = "msg " + (role === "me" ? "me" : "her");
  d.textContent = text;
  if (trace) { const t = document.createElement("span"); t.className = "trace"; t.innerHTML = trace; d.appendChild(t); }
  if (alt) { const a = document.createElement("span"); a.className = "alt"; a.textContent = alt; d.appendChild(a); }
  logEl.appendChild(d); logEl.scrollTop = logEl.scrollHeight;
}
function traceLine(d) {
  const esc = d.outcome.startsWith("escalated") || d.outcome === "no_input";
  const badge = `<span class="badge ${esc ? "esc" : "ok"}">${d.outcome}</span>`;
  return `${badge} path=${d.served_path} · ${d.latency_ms} ms · variant=${d.variant}`;
}
function altLine(d) {
  const served = (d.served_path || "").startsWith("lexical") ? "lexical" : "semantic";
  const other = served === "lexical" ? d.semantic_candidate : d.lexical_candidate;
  const name = served === "lexical" ? "semantic" : "lexical";
  return other ? `A/B — ${name} path would say: ${other}` : "";
}

// ---------- audio playback (with barge-in support) ----------
function stopPlayback() { if (player) { player.pause(); player = null; } }
function play(b64, onEnd) {
  stopPlayback();
  if (!b64) { onEnd && onEnd(); return null; }
  player = new Audio("data:audio/mpeg;base64," + b64);
  player.onended = () => { player = null; onEnd && onEnd(); };
  player.play().catch(() => onEnd && onEnd());
  return player;
}

// ---- speculative filler: a short spoken ack so there's never a silent gap ----
let fillers = [];
async function prefetchFillers() {
  fillers = [];
  for (let i = 0; i < 3; i++) {
    try { const f = await (await fetch("/api/filler")).json(); if (f.audio_b64) fillers.push(f.audio_b64); } catch (e) {}
  }
}
function playFiller() {
  if (!fillers.length || !calling) return;
  setState("speaking", "…");
  play(fillers[Math.floor(Math.random() * fillers.length)],
       () => { if (calling && state === "speaking") setState("listening", "Listening…"); });
}
// wraps a turn: if the answer isn't back in 400 ms, speak a filler; the answer cuts it off
async function runTurn(fetchPromise) {
  setState("thinking", "…");
  let responded = false;
  const timer = setTimeout(() => { if (!responded) playFiller(); }, 400);
  let d;
  try { d = await fetchPromise; }
  catch (e) { clearTimeout(timer); if (calling) setState("listening", "Listening…"); return; }
  responded = true; clearTimeout(timer);
  speakThen(d);   // play() stops any filler and speaks the answer
}

// ---------- turn handling ----------
function render(d) {
  if (d.outcome === "no_input") return;           // false trigger — stay listening
  if (d.transcript) addMsg("me", d.transcript);
  if (d.response) addMsg("her", d.response, traceLine(d), altLine(d));
}
function speakThen(d) {
  render(d);
  if (calling && d.response && d.audio_b64) {
    setState("speaking", "Priya is speaking… (just talk to interrupt)");
    play(d.audio_b64, () => { if (calling) setState("listening", "Listening…"); });
  } else if (calling) {
    setState("listening", "Listening…");
  }
}

function sendAudio(blob) {
  runTurn(fetch("/api/turn_audio", { method: "POST",
    headers: { "Content-Type": blob.type || "audio/webm", "X-Variant": variantSel.value }, body: blob })
    .then((r) => r.json()));
}

// ---------- recording lifecycle ----------
function startRecording() {
  chunks = [];
  let mime = "audio/webm;codecs=opus";
  if (!(window.MediaRecorder && MediaRecorder.isTypeSupported(mime))) mime = "audio/webm";
  try { rec = new MediaRecorder(stream, { mimeType: mime }); }
  catch (e) { rec = new MediaRecorder(stream); }
  rec.ondataavailable = (ev) => { if (ev.data.size) chunks.push(ev.data); };
  rec.onstop = () => {
    const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
    if (blob.size > 1800 && calling) sendAudio(blob);
    else if (calling) setState("listening", "Listening…");
  };
  rec.start();
  recStart = performance.now(); lastLoud = recStart;
  setState("recording", "Listening to you…");
}
function stopRecording() { if (rec && rec.state !== "inactive") rec.stop(); }

// ---------- VAD loop ----------
function rms() {
  analyser.getFloatTimeDomainData(buf);
  let s = 0; for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return Math.sqrt(s / buf.length);
}
function loop() {
  if (!calling) return;
  const e = rms();
  levelEl.style.width = Math.min(100, e * 450) + "%";
  const startTh = Math.max(0.045, emaNoise * 3.2);
  const stopTh = Math.max(0.02, emaNoise * 2.0);
  const now = performance.now();

  if (state === "listening" || state === "speaking") {
    if (state === "listening" && e < startTh) emaNoise = 0.9 * emaNoise + 0.1 * e; // adapt to room
    const need = state === "speaking" ? BARGE_FRAMES : START_FRAMES;
    loudStreak = e > startTh ? loudStreak + 1 : 0;
    if (loudStreak >= need) {
      if (state === "speaking") stopPlayback();   // barge-in
      loudStreak = 0; startRecording();
    }
  } else if (state === "recording") {
    if (e > stopTh) lastLoud = now;
    const dur = now - recStart;
    if ((dur > MIN_UTTER_MS && now - lastLoud > SILENCE_MS) || dur > MAX_UTTER_MS) stopRecording();
  }
  raf = requestAnimationFrame(loop);
}

// ---------- call control ----------
async function startCall() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  } catch (e) { setState("idle", "Mic permission denied — allow the microphone and retry."); return; }
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaStreamSource(stream);
  analyser = audioCtx.createAnalyser(); analyser.fftSize = 1024;
  buf = new Float32Array(analyser.fftSize); src.connect(analyser);

  calling = true;
  callBtn.textContent = "End call"; callBtn.className = "call live";
  setState("speaking", "Connecting…");
  try {
    const g = await (await fetch("/api/greeting")).json();
    addMsg("her", g.response);
    play(g.audio_b64, () => { if (calling) setState("listening", "Listening…"); });
  } catch (e) { setState("listening", "Listening…"); }
  prefetchFillers();
  raf = requestAnimationFrame(loop);
}
function endCall() {
  calling = false;
  stopRecording(); stopPlayback();
  if (raf) cancelAnimationFrame(raf);
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (audioCtx) audioCtx.close().catch(() => {});
  callBtn.textContent = "Start call"; callBtn.className = "call idle";
  setState("idle", "Call ended. Tap “Start call” to talk again.");
  levelEl.style.width = "0%";
}
callBtn.onclick = () => (calling ? endCall() : startCall());

// ---------- A/B switch + text fallback + health ----------
variantSel.onchange = () => postJSON("/api/variant", { variant: variantSel.value });
$("textForm").onsubmit = (ev) => {
  ev.preventDefault();
  const t = $("textIn").value.trim(); if (!t) return;
  $("textIn").value = "";
  runTurn(postJSON("/api/turn_text", { text: t, variant: variantSel.value })
    .then((d) => { if (!d.transcript) d.transcript = t; return d; }));
};
(async () => {
  try {
    const h = await (await fetch("/api/health")).json();
    variantSel.value = h.variant || "auto";
    const b = h.backends || {};
    backendsEl.textContent = `stt=${h.stt ? "Deepgram" : "off"} · tts=${h.tts ? "ElevenLabs" : "off"} · `
      + `llm=${b.llm} · ${b.lexical} / ${b.semantic} · ${b.embedder} · ${b.reranker}`;
  } catch (e) { backendsEl.textContent = "server not reachable"; }
})();
