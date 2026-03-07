let requestCount = 0;
let lastEventId = 0;

const ui = {
  status: document.getElementById("status"),
  statusSub: document.getElementById("statusSub"),
  heroCaption: document.getElementById("heroCaption"),
  voiceCore: document.getElementById("voiceCore"),
  wave: document.getElementById("wave"),
  sessionState: document.getElementById("sessionState"),
  heard: document.getElementById("heard"),
  response: document.getElementById("response"),
  lastAction: document.getElementById("lastAction"),
  inputMode: document.getElementById("inputMode"),
  telemetry: document.getElementById("telemetry"),
  requestCount: document.getElementById("requestCount"),
  latencyValue: document.getElementById("latencyValue"),
  micStatus: document.getElementById("micStatus"),
  netStatus: document.getElementById("netStatus"),
  footerMic: document.getElementById("footerMic"),
  footerNet: document.getElementById("footerNet"),
  clockTop: document.getElementById("clockTop"),
  clockBottom: document.getElementById("clockBottom"),
  cpuVal: document.getElementById("cpuVal"),
  tempVal: document.getElementById("tempVal")
};

function stickToBottom(element) {
  element.scrollTop = element.scrollHeight;
}

function setBoxText(element, text) {
  element.innerText = text;
  stickToBottom(element);
}

function setStatus(state, subtext) {
  ui.status.className = "status-value";
  ui.voiceCore.classList.remove("busy");
  ui.wave.classList.remove("active");

  if (state === "Idle") {
    ui.status.classList.add("status-idle");
    ui.heroCaption.innerText = "Touch interface engaged";
    ui.sessionState.innerText = "Stable";
  } else if (state === "Listening...") {
    ui.status.classList.add("status-listening");
    ui.voiceCore.classList.add("busy");
    ui.wave.classList.add("active");
    ui.heroCaption.innerText = "Capturing audio input";
    ui.sessionState.innerText = "Input active";
  } else if (state === "Thinking...") {
    ui.status.classList.add("status-thinking");
    ui.voiceCore.classList.add("busy");
    ui.wave.classList.add("active");
    ui.heroCaption.innerText = "Processing intent";
    ui.sessionState.innerText = "Inference";
  } else if (state === "Speaking...") {
    ui.status.classList.add("status-speaking");
    ui.voiceCore.classList.add("busy");
    ui.heroCaption.innerText = "Delivering response";
    ui.sessionState.innerText = "Output active";
  } else if (state === "Error") {
    ui.status.classList.add("status-error");
    ui.heroCaption.innerText = "Attention required";
    ui.sessionState.innerText = "Fault";
  }

  ui.status.innerText = state;
  ui.statusSub.innerText = subtext || "";
}

function appendTelemetry(text) {
  const stamp = new Date().toLocaleTimeString();
  ui.telemetry.innerText = `${ui.telemetry.innerText}\n[${stamp}] ${text}`;
  stickToBottom(ui.telemetry);
}

function updateClocks() {
  const now = new Date().toLocaleTimeString();
  ui.clockTop.innerText = now;
  ui.clockBottom.innerText = now;
}

function updateLatency(t0) {
  const latency = `${((performance.now() - t0) / 1000).toFixed(1)}s`;
  ui.latencyValue.innerText = latency;
}

function handleVoiceResult(data) {
  if (data.ok) {
    requestCount += 1;
    ui.requestCount.innerText = String(requestCount);
    setBoxText(ui.heard, data.text || "(No transcript)");
    setBoxText(ui.response, data.response || "(No response)");
    setStatus("Speaking...", "Response ready");
    appendTelemetry(
      data.source === "wake_word"
        ? "Wake word request completed."
        : "Voice response generated."
    );

    setTimeout(() => {
      setStatus("Idle", "Touch the core to speak");
    }, 900);
    return;
  }

  if (data.wake_word_missing || data.wake_word_only) {
    setBoxText(ui.heard, data.text || "(No transcript)");
    setBoxText(ui.response, data.error || "Wake word required.");
    setStatus("Idle", data.error || "Say the wake word to begin");
    appendTelemetry(
      data.wake_word_missing
        ? "Wake word not detected."
        : "Wake word detected without follow-up command."
    );
    return;
  }

  if (data.busy) {
    setStatus("Idle", "Previous request still running");
    appendTelemetry("Voice request skipped: pipeline busy.");
    return;
  }

  setBoxText(ui.response, data.error || "Unknown error");
  setBoxText(ui.heard, "Input unavailable.");
  setStatus("Error", data.error || "Voice request failed");
  ui.micStatus.innerText = "Check input";
  ui.footerMic.innerText = "Issue";
  appendTelemetry(`Error: ${data.error || "Unknown error"}`);
}

function handleServerEvent(event) {
  if (event.type === "wake_detected") {
    ui.lastAction.innerText = "Wake word request";
    ui.inputMode.innerText = "Voice";
    appendTelemetry(`Wake word detected: ${event.payload.keyword}`);
    return;
  }

  if (event.type === "voice_state") {
    setStatus(event.payload.state || "Thinking...", event.payload.subtext || "");
    return;
  }

  if (event.type === "voice_result") {
    handleVoiceResult(event.payload || {});
  }
}

async function pollEvents() {
  try {
    const response = await fetch(`/events?since=${lastEventId}`);
    const data = await response.json();
    if (!data.ok || !Array.isArray(data.events)) {
      return;
    }

    for (const event of data.events) {
      if (typeof event.id === "number" && event.id > lastEventId) {
        lastEventId = event.id;
      }
      handleServerEvent(event);
    }
  } catch (err) {
    // Keep polling silently; transient network hiccups are expected.
  }
}

async function listen() {
  const t0 = performance.now();

  setStatus("Listening...", "Recording request");
  setBoxText(ui.heard, "Listening for speech...");
  setBoxText(ui.response, "");
  ui.lastAction.innerText = "Voice request";
  ui.inputMode.innerText = "Voice";
  appendTelemetry("Voice capture started.");

  try {
    const response = await fetch("/listen");
    setStatus("Thinking...", "Transcribing and generating response");
    const data = await response.json();
    handleVoiceResult({ ...data, source: "touch" });
  } catch (err) {
    setBoxText(ui.response, String(err));
    setStatus("Error", "Network or server problem");
    ui.netStatus.innerText = "Error";
    ui.footerNet.innerText = "Error";
    appendTelemetry(`Fetch failed: ${err}`);
  } finally {
    updateLatency(t0);
  }
}

ui.voiceCore.addEventListener("click", listen);

updateClocks();
setInterval(updateClocks, 1000);
setInterval(pollEvents, 800);
pollEvents();

// Lightweight simulated diagnostics keep the footer lively in offline/demo mode.
setInterval(() => {
  ui.cpuVal.innerText = `${18 + Math.floor(Math.random() * 18)}%`;
  ui.tempVal.innerText = `${45 + Math.floor(Math.random() * 8)}C`;
}, 3000);

stickToBottom(ui.heard);
stickToBottom(ui.response);
stickToBottom(ui.telemetry);
