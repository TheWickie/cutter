// Frontend logic for Cutter Voice Pilot.
//
// This script manages the call lifecycle: retrieving a short‑lived token from
// the backend, creating a WebRTC PeerConnection, exchanging SDP with the
// OpenAI realtime API, and updating the UI.  It keeps the interface
// lightweight and fails gracefully with error messages.

let pc = null;           // current RTCPeerConnection
let remoteAudio = null;  // element playing the assistant's audio
let callActive = false;  // flag indicating whether a call is in progress
let clientSecret = null; // current client_secret token
let modelName = null;    // realtime model name

// Determine backend base URL. Use local server during development and
// the Render deployment in production.
const API_BASE =
  window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "https://cutter.onrender.com";

/**
 * Update the status indicator in the UI.
 * @param {string} state One of "connected", "connecting", or "disconnected".
 */
function updateStatus(state) {
  const statusEl = document.getElementById("status");
  statusEl.classList.remove("status-disconnected", "status-connecting", "status-connected");
  switch (state) {
    case "connected":
      statusEl.textContent = "Connected — speak naturally.";
      statusEl.classList.add("status-connected");
      break;
    case "connecting":
      statusEl.textContent = "Connecting…";
      statusEl.classList.add("status-connecting");
      break;
    default:
      statusEl.textContent = "Disconnected";
      statusEl.classList.add("status-disconnected");
      break;
  }
}

/**
 * Start the voice call.  Fetches a session token from the backend and
 * negotiates a WebRTC connection with OpenAI's realtime API.
 */
async function startCall() {
  updateStatus("connecting");
  const button = document.getElementById("callButton");
  button.disabled = true;
  try {
    // Request a new client_secret and model name from our backend.
    const response = await fetch(`${API_BASE}/session`, { method: "POST" });
    if (!response.ok) {
      throw new Error(`Server error: ${response.statusText}`);
    }
    const data = await response.json();
    clientSecret = data.client_secret;
    modelName = data.model;

    // Create a new RTCPeerConnection and set up handlers.
    pc = new RTCPeerConnection();
    remoteAudio = new Audio();
    remoteAudio.autoplay = true;
    remoteAudio.playsInline = true;
    pc.ontrack = (ev) => {
      // Assign the remote stream to our audio element when tracks arrive.
      if (remoteAudio.srcObject !== ev.streams[0]) {
        remoteAudio.srcObject = ev.streams[0];
      }
    };

    // Obtain microphone input from the user.
    const localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    localStream.getTracks().forEach((track) => {
      pc.addTrack(track, localStream);
    });

    // Create an SDP offer and set it as the local description.
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // Send the SDP offer to OpenAI's realtime endpoint.  Note that we use
    // the client_secret returned by our backend as the bearer token.  The
    // body of this request is the SDP itself (not JSON).
    const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=${encodeURIComponent(modelName)}`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${clientSecret}`,
          "Content-Type": "application/sdp"
        },
        body: offer.sdp
      }
    );
    if (!sdpResponse.ok) {
      throw new Error(`Realtime negotiation failed: ${await sdpResponse.text()}`);
    }

    // The response body contains the answer SDP.  Apply it to complete the handshake.
    const answerSdp = await sdpResponse.text();
    await pc.setRemoteDescription(new RTCSessionDescription({
      type: "answer",
      sdp: answerSdp
    }));

    // Update UI to reflect an active call.
    callActive = true;
    updateStatus("connected");
    button.textContent = "Hang up";
  } catch (err) {
    console.error(err);
    alert("Error starting call: " + err.message);
    // Ensure we clean up if something goes wrong.
    endCall();
  } finally {
    button.disabled = false;
  }
}

/**
 * End the current call and clean up resources.
 */
function endCall() {
  if (pc) {
    // Stop all outgoing tracks and close the peer connection.
    pc.getSenders().forEach((sender) => {
      if (sender.track) {
        sender.track.stop();
      }
    });
    pc.close();
    pc = null;
  }
  if (remoteAudio) {
    remoteAudio.srcObject = null;
    remoteAudio = null;
  }
  callActive = false;
  clientSecret = null;
  modelName = null;
  updateStatus("disconnected");
  const button = document.getElementById("callButton");
  button.textContent = "Call the helper";
}

// Set up event listeners once the DOM is ready.
document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("callButton");
  button.addEventListener("click", () => {
    if (!callActive) {
      startCall();
    } else {
      endCall();
    }
  });
});

// NOTE: The OpenAI realtime API may also send a text transcript over a
// datachannel.  If/when that feature is available, you can use
// pc.ondatachannel to receive text messages and append them to the
// transcript div.  For now this functionality is stubbed out.