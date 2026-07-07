const API_SESSION_URL = "/api/sessions/";
const TARGET_SAMPLE_RATE = 16000;
const FRAME_MS = 100;
const SAMPLES_PER_FRAME = TARGET_SAMPLE_RATE * FRAME_MS / 1000;

const state = {
  audioContext: null,
  mediaStream: null,
  sourceNode: null,
  processorNode: null,
  silenceNode: null,
  socket: null,
  sessionId: null,
  seq: 0,
  frameCount: 0,
  startedAt: 0,
  recordingStartedAt: 0,
  resampleCarry: new Float32Array(0),
  pcmCarry: [],
  ttsUrls: [],
};

const els = {
  statusBadge: document.querySelector("#statusBadge"),
  toneSelect: document.querySelector("#toneSelect"),
  recordButton: document.querySelector("#recordButton"),
  stopButton: document.querySelector("#stopButton"),
  cancelButton: document.querySelector("#cancelButton"),
  clearButton: document.querySelector("#clearButton"),
  sessionId: document.querySelector("#sessionId"),
  frameCount: document.querySelector("#frameCount"),
  latency: document.querySelector("#latency"),
  englishOutput: document.querySelector("#englishOutput"),
  hindiOutput: document.querySelector("#hindiOutput"),
  audioList: document.querySelector("#audioList"),
  eventLog: document.querySelector("#eventLog"),
};

const serverEventHandlers = {
  "asr.final": handleAsrFinal,
  "pipeline.stage": handlePipelineStage,
  "segment.skipped": handleSegmentSkipped,
  "translation.final": handleTranslationFinal,
  "tts.audio": handleTtsAudio,
  "metrics.latency": handleLatencyMetrics,
  "interruption.detected": handleInterruptionDetected,
  "session.ready": handleSessionReady,
  "session.cancelled": handleSessionCancelled,
  "error": handleServerError,
};

els.recordButton.addEventListener("click", startRecording);
els.stopButton.addEventListener("click", stopRecording);
els.cancelButton.addEventListener("click", cancelProcessing);
els.clearButton.addEventListener("click", clearOutputs);

async function startRecording() {
  closeCurrentSocket();
  clearOutputs();
  setStatus("Starting", "");
  setControls({ recording: false, busy: true });

  try {
    const session = await createSession();
    state.sessionId = session.sessionId;
    els.sessionId.textContent = session.sessionId;
    await openSocket(session.streamUrl);
    await startMicrophone();
    state.startedAt = performance.now();
    state.recordingStartedAt = Date.now();
    setStatus("Recording", "recording");
    setControls({ recording: true, busy: false, cancelable: true });
    logEvent("Microphone is recording. Speak English, then stop to translate.");
  } catch (error) {
    await cleanupRecording();
    setStatus("Error", "");
    setControls({ recording: false, busy: false, cancelable: false });
    logEvent(error.message || String(error));
  }
}

async function stopRecording() {
  setControls({ recording: false, busy: true, cancelable: true });
  setStatus("Processing", "");
  stopMicrophoneNodes();
  flushPcmCarry();
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify({ type: "audio.end", seq: nextSeq() }));
  }
  logEvent("Audio sent. Waiting for ASR, translation, and TTS.");
}

async function cancelProcessing() {
  stopMicrophoneNodes();
  stopAllPlayback();
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify({ type: "session.cancel", seq: nextSeq() }));
  }
  closeCurrentSocket();
  state.pcmCarry = [];
  state.resampleCarry = new Float32Array(0);
  setStatus("Cancelled", "");
  setControls({ recording: false, busy: false, cancelable: false });
  logEvent("Cancelled current processing.");
}

async function createSession() {
  const response = await fetch(API_SESSION_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone: els.toneSelect.value }),
  });
  if (!response.ok) {
    throw new Error(`Session creation failed: ${response.status}`);
  }
  return response.json();
}

function openSocket(streamUrl) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(normalizeStreamUrl(streamUrl));
    state.socket = socket;
    socket.addEventListener("open", () => {
      setStatus("Loading model", "");
      logEvent("Loading translation model.");
    }, { once: true });
    socket.addEventListener("error", () => reject(new Error("WebSocket connection failed")), { once: true });
    socket.addEventListener("message", function waitForReady(event) {
      const message = JSON.parse(event.data);
      if (message.type === "session.ready") {
        socket.removeEventListener("message", waitForReady);
        socket.addEventListener("message", handleSocketMessage);
        logEvent("Translation model is ready.");
        resolve();
        return;
      }
      if (message.type === "error") {
        socket.removeEventListener("message", waitForReady);
        handleSocketMessage(event);
        reject(new Error(message.message || message.code || "Model loading failed"));
        return;
      }
      handleSocketMessage(event);
    });
    socket.addEventListener("close", () => {
      if (els.statusBadge.textContent !== "Ready" && els.statusBadge.textContent !== "Error") {
        logEvent("WebSocket closed.");
      }
      setControls({ recording: false, busy: false, cancelable: false });
    });
  });
}

function normalizeStreamUrl(streamUrl) {
  const url = new URL(streamUrl, window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  url.host = window.location.host;
  return url.toString();
}

async function startMicrophone() {
  state.mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  state.audioContext = new AudioContext();
  state.sourceNode = state.audioContext.createMediaStreamSource(state.mediaStream);
  state.processorNode = state.audioContext.createScriptProcessor(4096, 1, 1);
  state.silenceNode = state.audioContext.createGain();
  state.silenceNode.gain.value = 0;
  state.processorNode.onaudioprocess = handleAudioProcess;
  state.sourceNode.connect(state.processorNode);
  state.processorNode.connect(state.silenceNode);
  state.silenceNode.connect(state.audioContext.destination);
}

function handleAudioProcess(event) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    return;
  }
  const input = event.inputBuffer.getChannelData(0);
  const downsampled = downsampleTo16k(input, state.audioContext.sampleRate);
  for (const sample of downsampled) {
    state.pcmCarry.push(sample);
    if (state.pcmCarry.length >= SAMPLES_PER_FRAME) {
      const frame = state.pcmCarry.splice(0, SAMPLES_PER_FRAME);
      sendPcmFrame(floatToPcm16(new Float32Array(frame)));
    }
  }
}

function downsampleTo16k(input, inputSampleRate) {
  if (inputSampleRate === TARGET_SAMPLE_RATE) {
    return input;
  }
  const combined = new Float32Array(state.resampleCarry.length + input.length);
  combined.set(state.resampleCarry);
  combined.set(input, state.resampleCarry.length);

  const ratio = inputSampleRate / TARGET_SAMPLE_RATE;
  const outputLength = Math.floor(combined.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), combined.length);
    let sum = 0;
    for (let j = start; j < end; j += 1) {
      sum += combined[j];
    }
    output[i] = sum / Math.max(1, end - start);
  }

  const consumed = Math.floor(outputLength * ratio);
  state.resampleCarry = combined.slice(consumed);
  return output;
}

function floatToPcm16(floatSamples) {
  const buffer = new ArrayBuffer(floatSamples.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < floatSamples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatSamples[i]));
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Uint8Array(buffer);
}

function sendPcmFrame(pcmBytes) {
  const timestampMs = Date.now() - state.recordingStartedAt;
  state.socket.send(JSON.stringify({
    type: "audio.frame",
    seq: nextSeq(),
    timestampMs,
    format: "pcm16",
    sampleRate: TARGET_SAMPLE_RATE,
    channels: 1,
    data: bytesToBase64(pcmBytes),
  }));
  state.frameCount += 1;
  els.frameCount.textContent = String(state.frameCount);
}

function flushPcmCarry() {
  if (state.pcmCarry.length > 0 && state.socket && state.socket.readyState === WebSocket.OPEN) {
    sendPcmFrame(floatToPcm16(new Float32Array(state.pcmCarry)));
    state.pcmCarry = [];
  }
}

function handleSocketMessage(event) {
  const message = JSON.parse(event.data);
  const handler = serverEventHandlers[message.type] || handleUnknownServerEvent;
  handler(message);
}

function handleAsrFinal(message) {
  setText(els.englishOutput, message.text || "");
  logEvent(`ASR: ${message.text || "(empty)"}`);
}

function handlePipelineStage(message) {
  setStatus(stageLabel(message.stage), "");
  logEvent(`Stage: ${stageLabel(message.stage)}`);
}

function handleSegmentSkipped(message) {
  setStatus("Ready", "ready");
  setControls({ recording: false, busy: false, cancelable: false });
  logEvent(`Skipped: ${skipReasonLabel(message.reason)}`);
}

function handleTranslationFinal(message) {
  setText(els.hindiOutput, message.translatedText || "");
  logEvent(`Hindi: ${message.translatedText || "(empty)"}`);
}

function handleTtsAudio(message) {
  appendAudio(message);
  setStatus("Ready", "ready");
  setControls({ recording: false, busy: false, cancelable: false });
}

function handleLatencyMetrics(message) {
  els.latency.textContent = formatLatency(message);
  logEvent(`Metrics: ${els.latency.textContent}`);
}

function handleInterruptionDetected() {
  logEvent("Interruption detected. Active TTS should stop.");
  stopAllPlayback();
}

function handleSessionReady() {
  logEvent("Session is ready.");
}

function handleSessionCancelled() {
  setStatus("Cancelled", "");
  setControls({ recording: false, busy: false, cancelable: false });
  logEvent("Backend cancelled current session.");
}

function handleServerError(message) {
  setStatus("Error", "");
  setControls({ recording: false, busy: false, cancelable: false });
  logEvent(`${message.code}: ${message.message}`);
}

function handleUnknownServerEvent(message) {
  logEvent(`Unhandled event: ${message.type || "(missing type)"}`);
}

function appendAudio(message) {
  const bytes = base64ToBytes(message.data);
  const mimeType = message.format === "wav" ? "audio/wav" : "audio/mpeg";
  const url = URL.createObjectURL(new Blob([bytes], { type: mimeType }));
  state.ttsUrls.push(url);

  if (els.audioList.classList.contains("muted")) {
    els.audioList.classList.remove("muted");
    els.audioList.textContent = "";
  }

  const audio = document.createElement("audio");
  audio.controls = true;
  audio.autoplay = true;
  audio.src = url;
  audio.addEventListener("play", () => sendPlaybackEvent("playback.started", message.ttsSegmentId));
  audio.addEventListener("ended", () => sendPlaybackEvent("playback.stopped", message.ttsSegmentId));
  audio.addEventListener("pause", () => sendPlaybackEvent("playback.stopped", message.ttsSegmentId));
  els.audioList.append(audio);
  logEvent("Hindi audio received.");
}

function sendPlaybackEvent(type, ttsSegmentId) {
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify({ type, ttsSegmentId }));
  }
}

function stopMicrophoneNodes() {
  if (state.processorNode) {
    state.processorNode.disconnect();
    state.processorNode.onaudioprocess = null;
  }
  if (state.silenceNode) {
    state.silenceNode.disconnect();
  }
  if (state.sourceNode) {
    state.sourceNode.disconnect();
  }
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach((track) => track.stop());
  }
  if (state.audioContext) {
    state.audioContext.close();
  }
  state.processorNode = null;
  state.silenceNode = null;
  state.sourceNode = null;
  state.mediaStream = null;
  state.audioContext = null;
}

async function cleanupRecording() {
  stopMicrophoneNodes();
  closeCurrentSocket();
}

function closeCurrentSocket() {
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.close();
  }
  state.socket = null;
}

function clearOutputs() {
  stopAllPlayback();
  state.ttsUrls.forEach((url) => URL.revokeObjectURL(url));
  state.ttsUrls = [];
  state.seq = 0;
  state.frameCount = 0;
  state.resampleCarry = new Float32Array(0);
  state.pcmCarry = [];
  els.frameCount.textContent = "0";
  els.latency.textContent = "-";
  els.englishOutput.textContent = "Transcript will appear here after recording stops.";
  els.englishOutput.classList.add("muted");
  els.hindiOutput.textContent = "Hindi text will appear here.";
  els.hindiOutput.classList.add("muted");
  els.audioList.textContent = "Converted audio will appear here.";
  els.audioList.classList.add("muted");
  els.eventLog.textContent = "";
}

function stopAllPlayback() {
  document.querySelectorAll("audio").forEach((audio) => {
    audio.pause();
    audio.currentTime = 0;
  });
}

function setText(element, value) {
  element.textContent = value || "(empty)";
  element.classList.remove("muted");
}

function setStatus(text, className) {
  els.statusBadge.textContent = text;
  els.statusBadge.className = `badge ${className || ""}`.trim();
}

function setControls({ recording, busy, cancelable = false }) {
  els.recordButton.disabled = busy || recording;
  els.stopButton.disabled = busy || !recording;
  els.cancelButton.disabled = !cancelable;
  els.toneSelect.disabled = busy || recording;
}

function stageLabel(stage) {
  const labels = {
    asr_started: "ASR",
    translation_model_loading: "Loading model",
    translation_started: "Translating",
    tts_started: "Speaking",
  };
  return labels[stage] || stage || "Processing";
}

function skipReasonLabel(reason) {
  const labels = {
    empty_transcript: "No clear speech detected",
    low_confidence_transcript: "Speech was too unclear",
    transcript_not_ready: "Transcript was not ready",
  };
  return labels[reason] || reason || "Skipped";
}

function nextSeq() {
  state.seq += 1;
  return state.seq;
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function formatLatency(message) {
  const parts = [];
  for (const [key, value] of Object.entries(message)) {
    if (key.endsWith("Ms") && typeof value === "number") {
      parts.push(`${key}: ${Math.round(value)}ms`);
    }
  }
  return parts.length ? parts.join(", ") : "-";
}

function logEvent(text) {
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString()} - ${text}`;
  els.eventLog.prepend(item);
}
