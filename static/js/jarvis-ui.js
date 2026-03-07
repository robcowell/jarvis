let requestCount = 0;

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
  tempVal: document.getElementById("tempVal"),
  textInput: document.getElementById("textInput"),
  sendBtn: document.getElementById("sendBtn")
};

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
  ui.telemetry.innerText = `[${stamp}] ${text}\n${ui.telemetry.innerText}`;
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

async function listen() {
  const t0 = performance.now();

  setStatus("Listening...", "Recording request");
  ui.heard.innerText = "Listening for speech...";
  ui.response.innerText = "";
  ui.lastAction.innerText = "Voice request";
  ui.inputMode.innerText = "Voice";
  appendTelemetry("Voice capture started.");

  try {
    const response = await fetch("/listen");
    setStatus("Thinking...", "Transcribing and generating response");
    const data = await response.json();

    if (data.ok) {
      requestCount += 1;
      ui.requestCount.innerText = String(requestCount);
      ui.heard.innerText = data.text || "(No transcript)";
      ui.response.innerText = data.response || "(No response)";
      setStatus("Speaking...", "Response ready");
      appendTelemetry("Voice response generated.");

      setTimeout(() => {
        setStatus("Idle", "Touch the core to speak");
      }, 900);
    } else {
      ui.response.innerText = data.error || "Unknown error";
      ui.heard.innerText = "Input unavailable.";
      setStatus("Error", data.error || "Voice request failed");
      ui.micStatus.innerText = "Check input";
      ui.footerMic.innerText = "Issue";
      appendTelemetry(`Error: ${data.error || "Unknown error"}`);
    }
  } catch (err) {
    ui.response.innerText = String(err);
    setStatus("Error", "Network or server problem");
    ui.netStatus.innerText = "Error";
    ui.footerNet.innerText = "Error";
    appendTelemetry(`Fetch failed: ${err}`);
  } finally {
    updateLatency(t0);
  }
}

async function askText() {
  const text = ui.textInput.value.trim();
  if (!text) {
    return;
  }

  const t0 = performance.now();
  setStatus("Thinking...", "Processing typed request");
  ui.heard.innerText = text;
  ui.response.innerText = "";
  ui.lastAction.innerText = "Text request";
  ui.inputMode.innerText = "Text";
  appendTelemetry("Typed request submitted.");

  try {
    const formData = new FormData();
    formData.append("text", text);

    const response = await fetch("/ask", {
      method: "POST",
      body: formData
    });
    const data = await response.json();

    if (data.ok) {
      requestCount += 1;
      ui.requestCount.innerText = String(requestCount);
      ui.response.innerText = data.response || "(No response)";
      ui.textInput.value = "";
      setStatus("Idle", "Touch the core to speak");
      appendTelemetry("Typed response generated.");
    } else {
      ui.response.innerText = data.error || "Unknown error";
      setStatus("Error", data.error || "Typed request failed");
      appendTelemetry(`Error: ${data.error || "Unknown error"}`);
    }
  } catch (err) {
    ui.response.innerText = String(err);
    setStatus("Error", "Network or server problem");
    appendTelemetry(`Fetch failed: ${err}`);
  } finally {
    updateLatency(t0);
  }
}

ui.voiceCore.addEventListener("click", listen);
ui.sendBtn.addEventListener("click", askText);
ui.textInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    askText();
  }
});

updateClocks();
setInterval(updateClocks, 1000);

// Lightweight simulated diagnostics keep the footer lively in offline/demo mode.
setInterval(() => {
  ui.cpuVal.innerText = `${18 + Math.floor(Math.random() * 18)}%`;
  ui.tempVal.innerText = `${45 + Math.floor(Math.random() * 8)}C`;
}, 3000);
