const store = {
  token: localStorage.getItem("kjb_token"),
  userId: localStorage.getItem("kjb_user"),
};

const socket = io({
  query: store.userId ? { user_id: store.userId } : {},
});

socket.on("presence", (data) => {
  const list = document.getElementById("online-users");
  if (!list) return;
  const existing = list.querySelector(`[data-user='${data.user_id}']`);
  if (data.is_online) {
    if (!existing) {
      const li = document.createElement("li");
      li.dataset.user = data.user_id;
      li.textContent = `User ${data.user_id}`;
      list.appendChild(li);
    }
  } else if (existing) {
    existing.remove();
  }
});

socket.on("chat", (payload) => {
  const log = document.getElementById("chat-log");
  if (!log) return;
  const line = document.createElement("div");
  line.textContent = `${payload.sender_id}: ${payload.content}`;
  log.appendChild(line);
});

const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(loginForm);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
      }),
    });
    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem("kjb_token", data.access_token);
      localStorage.setItem("kjb_user", data.user_id);
      window.location.href = "/channel";
    }
  });
}

const registerForm = document.getElementById("register-form");
if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(registerForm);
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        nickname: form.get("nickname"),
      }),
    });
    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem("kjb_token", data.access_token);
      localStorage.setItem("kjb_user", data.user_id);
      window.location.href = "/channel";
    }
  });
}

const chatForm = document.getElementById("chat-form");
if (chatForm) {
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = chatForm.querySelector("input[name='content']");
    if (!input.value) return;
    socket.emit("chat", {
      channel_id: 1,
      sender_id: store.userId || 0,
      content: input.value,
    });
    input.value = "";
  });
}

const postForm = document.getElementById("post-form");
if (postForm) {
  postForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(postForm);
    await fetch("/api/boards/posts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: store.token ? `Bearer ${store.token}` : "",
      },
      body: JSON.stringify({
        title: form.get("title"),
        body: form.get("body"),
      }),
    });
    form.set("title", "");
    form.set("body", "");
  });
}
