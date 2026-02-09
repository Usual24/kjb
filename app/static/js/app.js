const store = {
  token: localStorage.getItem("kjb_token"),
  userId: localStorage.getItem("kjb_user"),
};

const socket = io({
  query: store.userId ? { user_id: store.userId } : {},
});

const updateOnlineEmpty = () => {
  const list = document.getElementById("online-users");
  const empty = document.getElementById("online-empty");
  if (!list || !empty) return;
  empty.style.display = list.children.length ? "none" : "block";
};

const setStatus = (element, message, type = "") => {
  if (!element) return;
  element.textContent = message;
  element.classList.remove("error", "success");
  if (type) {
    element.classList.add(type);
  }
};

const setLoading = (button, isLoading) => {
  if (!button) return;
  button.disabled = isLoading;
  button.dataset.originalText = button.dataset.originalText || button.textContent;
  button.textContent = isLoading ? "처리 중..." : button.dataset.originalText;
};

socket.on("presence", (data) => {
  const list = document.getElementById("online-users");
  const empty = document.getElementById("online-empty");
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
  if (empty) {
    empty.style.display = list.children.length ? "none" : "block";
  }
});

document.addEventListener("DOMContentLoaded", updateOnlineEmpty);

socket.on("chat", (payload) => {
  const log = document.getElementById("chat-log");
  if (!log) return;
  const empty = log.querySelector(".empty-state");
  if (empty) empty.remove();
  const line = document.createElement("div");
  line.textContent = `${payload.sender_id}: ${payload.content}`;
  log.appendChild(line);
});

const loginForm = document.getElementById("login-form");
if (loginForm) {
  const status = loginForm.querySelector("[data-role='login-status']");
  const submitButton = loginForm.querySelector("button[type='submit']");
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(status, "");
    const form = new FormData(loginForm);
    setLoading(submitButton, true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      const data = await response.json();
      if (response.ok && data.access_token) {
        localStorage.setItem("kjb_token", data.access_token);
        localStorage.setItem("kjb_user", data.user_id);
        setStatus(status, "로그인 성공! 채널로 이동합니다.", "success");
        window.location.href = "/channel";
      } else {
        setStatus(
          status,
          data.detail || "로그인에 실패했습니다. 이메일과 비밀번호를 확인하세요.",
          "error"
        );
      }
    } catch (error) {
      setStatus(status, "네트워크 오류가 발생했습니다. 다시 시도하세요.", "error");
    } finally {
      setLoading(submitButton, false);
    }
  });
}

const registerForm = document.getElementById("register-form");
if (registerForm) {
  const status = registerForm.querySelector("[data-role='register-status']");
  const submitButton = registerForm.querySelector("button[type='submit']");
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus(status, "");
    const form = new FormData(registerForm);
    setLoading(submitButton, true);
    try {
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
      if (response.ok && data.access_token) {
        localStorage.setItem("kjb_token", data.access_token);
        localStorage.setItem("kjb_user", data.user_id);
        setStatus(status, "가입 완료! 채널로 이동합니다.", "success");
        window.location.href = "/channel";
      } else {
        setStatus(
          status,
          data.detail || "회원가입에 실패했습니다. 입력 정보를 확인하세요.",
          "error"
        );
      }
    } catch (error) {
      setStatus(status, "네트워크 오류가 발생했습니다. 다시 시도하세요.", "error");
    } finally {
      setLoading(submitButton, false);
    }
  });
}

const chatForm = document.getElementById("chat-form");
if (chatForm) {
  const status = chatForm.querySelector("[data-role='chat-status']");
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = chatForm.querySelector("input[name='content']");
    if (!input.value.trim()) {
      setStatus(status, "메시지를 입력하세요.", "error");
      return;
    }
    if (!store.userId) {
      setStatus(status, "로그인 후 메시지를 보낼 수 있습니다.", "error");
      return;
    }
    setStatus(status, "");
    socket.emit("chat", {
      channel_id: 1,
      sender_id: store.userId || 0,
      content: input.value.trim(),
    });
    input.value = "";
  });
}

const postForm = document.getElementById("post-form");
if (postForm) {
  const status = postForm.querySelector("[data-role='board-status']");
  const submitButton = postForm.querySelector("button[type='submit']");
  postForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(postForm);
    if (!form.get("title") || !form.get("body")) {
      setStatus(status, "제목과 내용을 모두 입력하세요.", "error");
      return;
    }
    if (!store.token) {
      setStatus(status, "로그인 후 게시글을 작성할 수 있습니다.", "error");
      return;
    }
    setLoading(submitButton, true);
    setStatus(status, "");
    try {
      const response = await fetch("/api/boards/posts", {
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
      if (!response.ok) {
        setStatus(status, "게시글 작성에 실패했습니다.", "error");
        return;
      }
      setStatus(status, "게시글이 등록되었습니다.", "success");
      postForm.reset();
    } catch (error) {
      setStatus(status, "네트워크 오류가 발생했습니다. 다시 시도하세요.", "error");
    } finally {
      setLoading(submitButton, false);
    }
  });
}
