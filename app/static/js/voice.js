const socket = io({
  transports: ['websocket', 'polling'],
  reconnection: true,
});
const toggleButton = document.getElementById('voiceToggleButton');
const participantList = document.getElementById('voiceParticipantList');

const peerConnections = new Map();
const remoteAudioElements = new Map();
const pendingIceCandidates = new Map();
const activeSpeakerIds = new Set();

let joined = false;
let localStream = null;
let audioContext = null;
let speakingInterval = null;
let lastSpeakingState = false;
let latestParticipants = [];

const defaultIceServers = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
];

const configuredIceServers = Array.isArray(window.KJB_VOICE_ICE_SERVERS)
  ? window.KJB_VOICE_ICE_SERVERS.filter((server) => server && typeof server === 'object' && server.urls)
  : [];

const rtcConfig = {
  iceServers: configuredIceServers.length ? configuredIceServers : defaultIceServers,
};

const getCurrentUserId = () => Number(window.KJB_CURRENT_USER_ID);

const serializeSessionDescription = (description) => {
  if (!description) return null;
  return {
    type: description.type,
    sdp: description.sdp,
  };
};

const serializeIceCandidate = (candidate) => {
  if (!candidate) return null;
  return {
    candidate: candidate.candidate,
    sdpMid: candidate.sdpMid,
    sdpMLineIndex: candidate.sdpMLineIndex,
    usernameFragment: candidate.usernameFragment,
  };
};

const renderParticipants = (participants) => {
  if (!participantList) return;
  if (!participants.length) {
    participantList.innerHTML = '<li class="empty">아직 참가자가 없습니다.</li>';
    return;
  }

  participantList.innerHTML = participants
    .map((user) => {
      const meBadge = user.id === getCurrentUserId() ? '<span class="badge">나</span>' : '';
      const speakingClass = activeSpeakerIds.has(user.id) ? 'on' : '';
      return `
        <li class="voice-user-item" data-user-id="${user.id}">
          <img src="${user.avatar}" alt="avatar">
          <a href="/profile?usr=${user.email_prefix}">${user.name}</a>
          <span class="voice-speaking-indicator ${speakingClass}" aria-label="speaking"></span>
          ${meBadge}
        </li>
      `;
    })
    .join('');
};

const setJoined = (value) => {
  joined = value;
  if (!toggleButton) return;
  toggleButton.dataset.joined = joined ? 'true' : 'false';
  toggleButton.textContent = joined ? '나가기' : '참가하기';
  toggleButton.classList.toggle('danger', joined);
  toggleButton.classList.toggle('success', !joined);
};

const createRemoteAudioElement = (userId) => {
  const audio = document.createElement('audio');
  audio.autoplay = true;
  audio.playsInline = true;
  audio.dataset.userId = String(userId);
  audio.style.display = 'none';
  document.body.appendChild(audio);
  remoteAudioElements.set(userId, audio);
  return audio;
};

const closePeerConnection = (userId) => {
  const connection = peerConnections.get(userId);
  if (connection) {
    connection.onicecandidate = null;
    connection.ontrack = null;
    connection.onconnectionstatechange = null;
    connection.close();
  }
  peerConnections.delete(userId);
  pendingIceCandidates.delete(userId);

  const audio = remoteAudioElements.get(userId);
  if (audio) {
    audio.srcObject = null;
    audio.remove();
  }
  remoteAudioElements.delete(userId);
};

const queueIceCandidate = (userId, candidate) => {
  const pending = pendingIceCandidates.get(userId) || [];
  pending.push(candidate);
  pendingIceCandidates.set(userId, pending);
};

const flushPendingIceCandidates = async (userId, connection) => {
  const pending = pendingIceCandidates.get(userId);
  if (!pending?.length) return;

  for (const candidate of pending) {
    await connection.addIceCandidate(new RTCIceCandidate(candidate));
  }
  pendingIceCandidates.delete(userId);
};

const cleanupVoiceResources = () => {
  Array.from(peerConnections.keys()).forEach(closePeerConnection);
  if (speakingInterval) {
    clearInterval(speakingInterval);
    speakingInterval = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }
  activeSpeakerIds.clear();
  lastSpeakingState = false;
};

const createPeerConnection = (remoteUserId) => {
  const connection = new RTCPeerConnection(rtcConfig);
  peerConnections.set(remoteUserId, connection);

  if (localStream) {
    localStream.getAudioTracks().forEach((track) => {
      connection.addTrack(track, localStream);
    });
  }

  connection.onicecandidate = (event) => {
    if (!event.candidate) return;
    const candidate = serializeIceCandidate(event.candidate);
    if (!candidate?.candidate) return;
    socket.emit('voice_signal', {
      target_id: remoteUserId,
      signal: { type: 'candidate', candidate },
    });
  };

  connection.ontrack = (event) => {
    const [stream] = event.streams;
    const audio = remoteAudioElements.get(remoteUserId) || createRemoteAudioElement(remoteUserId);
    if (audio.srcObject !== stream) {
      audio.srcObject = stream;
      audio.play().catch((error) => {
        console.warn('원격 음성 자동 재생 실패', error);
      });
    }
  };

  connection.onconnectionstatechange = () => {
    const state = connection.connectionState;
    if (state === 'failed' || state === 'closed' || state === 'disconnected') {
      closePeerConnection(remoteUserId);
    }
  };

  return connection;
};

const getPeerConnection = (remoteUserId) => peerConnections.get(remoteUserId) || createPeerConnection(remoteUserId);

const maybeStartSpeakingMonitor = () => {
  if (!localStream || speakingInterval) return;
  const [track] = localStream.getAudioTracks();
  if (!track) return;

  audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(new MediaStream([track]));
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);

  const buffer = new Uint8Array(analyser.fftSize);
  speakingInterval = setInterval(() => {
    analyser.getByteTimeDomainData(buffer);
    let sumSquares = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const normalized = (buffer[i] - 128) / 128;
      sumSquares += normalized * normalized;
    }
    const rms = Math.sqrt(sumSquares / buffer.length);
    const isSpeaking = rms > 0.04;

    if (isSpeaking !== lastSpeakingState) {
      lastSpeakingState = isSpeaking;
      socket.emit('voice_activity', { is_speaking: isSpeaking });
    }
  }, 120);
};

const ensureVoiceJoined = async () => {
  if (joined) return true;

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    });
    socket.emit('join_voice_room');
    setJoined(true);
    maybeStartSpeakingMonitor();
    return true;
  } catch (error) {
    console.error('음성 장치 접근 실패', error);
    return false;
  }
};

const leaveVoice = () => {
  if (!joined) return;
  socket.emit('voice_activity', { is_speaking: false });
  socket.emit('leave_voice_room');
  cleanupVoiceResources();
  setJoined(false);
};

const reconcilePeers = async (participants) => {
  if (!joined || !localStream) return;

  const myId = getCurrentUserId();
  const remoteUsers = participants.filter((user) => user.id !== myId);
  const currentRemoteIds = new Set(remoteUsers.map((user) => user.id));

  Array.from(peerConnections.keys()).forEach((userId) => {
    if (!currentRemoteIds.has(userId)) {
      closePeerConnection(userId);
    }
  });

  for (const user of remoteUsers) {
    const shouldCreateOffer = myId < user.id;
    const connection = getPeerConnection(user.id);
    if (!shouldCreateOffer || connection.signalingState !== 'stable') continue;
    try {
      const offer = await connection.createOffer({ offerToReceiveAudio: true });
      await connection.setLocalDescription(offer);
      const localDescription = serializeSessionDescription(connection.localDescription);
      if (!localDescription?.sdp) continue;
      socket.emit('voice_signal', {
        target_id: user.id,
        signal: { type: 'offer', sdp: localDescription },
      });
    } catch (error) {
      console.error('오퍼 생성 실패', error);
    }
  }
};

toggleButton?.addEventListener('click', async () => {
  if (joined) {
    leaveVoice();
    return;
  }
  await ensureVoiceJoined();
});

socket.on('connect', () => {
  socket.emit('request_voice_room');
});

socket.on('voice_room_update', async (participants) => {
  const users = Array.isArray(participants) ? participants : [];
  latestParticipants = users;
  renderParticipants(users);
  const iAmInRoom = users.some((user) => user.id === getCurrentUserId());
  if (!iAmInRoom && joined) {
    cleanupVoiceResources();
    setJoined(false);
  }
  setJoined(iAmInRoom && !!localStream);
  await reconcilePeers(users);
});

socket.on('voice_activity_update', (payload) => {
  activeSpeakerIds.clear();
  const ids = Array.isArray(payload?.speaking_user_ids) ? payload.speaking_user_ids : [];
  ids.forEach((id) => activeSpeakerIds.add(Number(id)));
  renderParticipants(latestParticipants);
});

socket.on('voice_signal', async ({ from_id: fromId, signal }) => {
  if (!joined || !fromId || !signal) return;
  const connection = getPeerConnection(Number(fromId));

  try {
    if (signal.type === 'offer') {
      if (!signal.sdp?.sdp) return;
      await connection.setRemoteDescription(new RTCSessionDescription(signal.sdp));
      await flushPendingIceCandidates(Number(fromId), connection);
      const answer = await connection.createAnswer();
      await connection.setLocalDescription(answer);
      const localDescription = serializeSessionDescription(connection.localDescription);
      if (!localDescription?.sdp) return;
      socket.emit('voice_signal', {
        target_id: Number(fromId),
        signal: { type: 'answer', sdp: localDescription },
      });
      return;
    }

    if (signal.type === 'answer') {
      if (!signal.sdp?.sdp) return;
      await connection.setRemoteDescription(new RTCSessionDescription(signal.sdp));
      await flushPendingIceCandidates(Number(fromId), connection);
      return;
    }

    if (signal.type === 'candidate' && signal.candidate) {
      if (connection.remoteDescription) {
        await connection.addIceCandidate(new RTCIceCandidate(signal.candidate));
      } else {
        queueIceCandidate(Number(fromId), signal.candidate);
      }
    }
  } catch (error) {
    console.error('시그널 처리 실패', error);
  }
});

window.addEventListener('beforeunload', () => {
  if (joined) {
    socket.emit('voice_activity', { is_speaking: false });
    socket.emit('leave_voice_room');
  }
  cleanupVoiceResources();
});
