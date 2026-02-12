const socket = io();
const toggleButton = document.getElementById('voiceToggleButton');
const participantList = document.getElementById('voiceParticipantList');

let joined = false;

const renderParticipants = (participants) => {
  if (!participantList) return;
  if (!participants.length) {
    participantList.innerHTML = '<li class="empty">아직 참가자가 없습니다.</li>';
    return;
  }

  participantList.innerHTML = participants
    .map((user) => {
      const meBadge = user.id === window.KJB_CURRENT_USER_ID ? '<span class="badge">나</span>' : '';
      return `
        <li class="voice-user-item">
          <img src="${user.avatar}" alt="avatar">
          <a href="/profile?usr=${user.email_prefix}">${user.name}</a>
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

toggleButton?.addEventListener('click', () => {
  if (joined) {
    socket.emit('leave_voice_room');
    setJoined(false);
    return;
  }
  socket.emit('join_voice_room');
  setJoined(true);
});

socket.on('connect', () => {
  socket.emit('request_voice_room');
});

socket.on('voice_room_update', (participants) => {
  const users = Array.isArray(participants) ? participants : [];
  renderParticipants(users);
  const iAmInRoom = users.some((user) => user.id === window.KJB_CURRENT_USER_ID);
  setJoined(iAmInRoom);
});

window.addEventListener('beforeunload', () => {
  if (joined) {
    socket.emit('leave_voice_room');
  }
});
