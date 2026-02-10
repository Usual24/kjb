const socket = io();
const chatMain = document.querySelector('.chat-main');
const channel = chatMain.dataset.channel;
const canSend = chatMain.dataset.canSend === 'true';
const messageList = document.getElementById('chatMessages');
const input = document.getElementById('chatInput');
const sendButton = document.getElementById('sendButton');
const contextMenu = document.getElementById('contextMenu');
const replyBanner = document.getElementById('replyBanner');
const onlineLists = document.querySelectorAll('[data-online-list]');
let replyToId = null;
let contextMessageId = null;
let contextUserId = null;

socket.emit('join', { channel });

function renderMessage(message) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message';
  wrapper.dataset.messageId = message.id;
  wrapper.dataset.userId = message.user_id;

  wrapper.innerHTML = `
    <a href="/profile?usr=${message.user_prefix}" class="avatar-link">
      <img src="${message.avatar}" alt="avatar">
    </a>
    <div class="message-body">
      <div class="message-meta">
        <a href="/profile?usr=${message.user_prefix}" ${message.name_color ? `style="color:${message.name_color};"` : ''}>${message.user_name}</a>
        ${message.accessory_image ? `<img src="${message.accessory_image}" class="name-accessory" alt="accessory">` : ''}
        <span>${message.created_at}</span>
        ${message.updated_at && message.updated_at !== message.created_at ? '<span class="edited">수정됨</span>' : ''}
      </div>
      ${message.reply_to ? `<div class="reply-preview">↳ ${message.reply_to}</div>` : ''}
      <div class="message-content">${message.rendered_content || message.content}</div>
    </div>
  `;
  return wrapper;
}

function appendMessage(message) {
  const element = renderMessage(message);
  messageList.appendChild(element);
  messageList.scrollTop = messageList.scrollHeight;
}

function updateOnlineList(users) {
  onlineLists.forEach((list) => {
    list.innerHTML = '';
    users.forEach(user => {
      const li = document.createElement('li');
      li.className = 'online-item';
      li.innerHTML = `
        <a href="/profile?usr=${user.email_prefix}">
          <img src="${user.avatar}" alt="avatar">
        </a>
        <a href="/profile?usr=${user.email_prefix}">${user.name}</a>
        ${user.accessory_image ? `<img src="${user.accessory_image}" class="name-accessory" alt="accessory">` : ''}
      `;
      const nameLink = li.querySelectorAll('a')[1];
      if (nameLink && user.name_color) {
        nameLink.style.color = user.name_color;
      }
      list.appendChild(li);
    });
  });
}

socket.on('online_update', (users) => {
  updateOnlineList(users);
});

socket.on('new_message', (message) => {
  appendMessage(message);
});

socket.on('message_updated', (message) => {
  const element = messageList.querySelector(`[data-message-id="${message.id}"]`);
  if (!element) return;
  element.querySelector('.message-content').textContent = message.content;
  if (message.rendered_content) {
    element.querySelector('.message-content').innerHTML = message.rendered_content;
  }
  const meta = element.querySelector('.message-meta');
  if (!meta.querySelector('.edited')) {
    const edited = document.createElement('span');
    edited.className = 'edited';
    edited.textContent = '수정됨';
    meta.appendChild(edited);
  }
});

socket.on('message_deleted', (payload) => {
  const element = messageList.querySelector(`[data-message-id="${payload.message_id}"]`);
  if (!element) return;
  element.querySelector('.message-content').textContent = '[삭제됨]';
});

sendButton.addEventListener('click', () => {
  if (!canSend) return;
  const content = input.value.trim();
  if (!content) return;
  socket.emit('send_message', { channel, content, reply_to: replyToId });
  input.value = '';
  replyToId = null;
  replyBanner.classList.add('hidden');
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendButton.click();
  }
});

messageList.addEventListener('contextmenu', (event) => {
  const messageElement = event.target.closest('.message');
  if (!messageElement) return;
  event.preventDefault();
  contextMessageId = messageElement.dataset.messageId;
  contextUserId = parseInt(messageElement.dataset.userId, 10);
  const isOwner = contextUserId === window.KJB_CURRENT_USER_ID;
  contextMenu.querySelector('[data-action="edit"]').style.display = isOwner ? 'block' : 'none';
  contextMenu.querySelector('[data-action="delete"]').style.display = (isOwner || window.KJB_IS_ADMIN) ? 'block' : 'none';
  contextMenu.style.top = `${event.clientY}px`;
  contextMenu.style.left = `${event.clientX}px`;
  contextMenu.classList.remove('hidden');
});

window.addEventListener('click', () => {
  contextMenu.classList.add('hidden');
});

contextMenu.addEventListener('click', (event) => {
  const action = event.target.dataset.action;
  if (!action) return;
  if (action === 'reply') {
    replyToId = contextMessageId;
    const messageElement = messageList.querySelector(`[data-message-id="${contextMessageId}"]`);
    const content = messageElement ? messageElement.querySelector('.message-content').textContent : '';
    replyBanner.textContent = `답장: ${content}`;
    replyBanner.classList.remove('hidden');
  }
  if (action === 'edit') {
    const newContent = prompt('수정할 내용을 입력하세요');
    if (newContent) {
      socket.emit('edit_message', { message_id: contextMessageId, content: newContent });
    }
  }
  if (action === 'delete') {
    if (confirm('메시지를 삭제할까요?')) {
      socket.emit('delete_message', { message_id: contextMessageId });
    }
  }
  contextMenu.classList.add('hidden');
});
