// TrọUni Interactive Controller (Nhà Tốt UI + Live Chat)
document.addEventListener("DOMContentLoaded", () => {
  // 1. Navbar elevation on scroll
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    window.addEventListener("scroll", () => {
      navbar.classList.toggle("scrolled", window.scrollY > 8);
    });
  }

  // 2. Auto-dismiss flash toasts
  document.querySelectorAll(".toast[data-auto-dismiss]").forEach((toast) => {
    setTimeout(() => {
      toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(() => toast.remove(), 320);
    }, 4000);
  });

  // 3. List / Grid view toggle on Home page
  const feedEl = document.getElementById("nt-listings-feed");
  const viewBtns = document.querySelectorAll("[data-view-mode]");
  if (feedEl && viewBtns.length) {
    const savedMode = localStorage.getItem("trouni_view_mode") || "list";
    const applyMode = (mode) => {
      feedEl.classList.toggle("grid-mode", mode === "grid");
      viewBtns.forEach((b) => b.classList.toggle("active", b.dataset.viewMode === mode));
    };
    applyMode(savedMode);
    viewBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.viewMode;
        localStorage.setItem("trouni_view_mode", mode);
        applyMode(mode);
      });
    });
  }

  // 4. Auth Tab Switcher & Demo Credential Autofill
  const tabBtns = document.querySelectorAll("[data-auth-tab]");
  const panels = document.querySelectorAll("[data-auth-panel]");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.authTab;
      tabBtns.forEach((b) => b.classList.toggle("active", b === btn));
      panels.forEach((p) => {
        p.style.display = p.dataset.authPanel === target ? "block" : "none";
      });
    });
  });

  document.querySelectorAll("[data-demo-email]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const loginTab = document.querySelector('[data-auth-tab="login"]');
      if (loginTab) loginTab.click();
      const emailInput = document.querySelector("#login-email");
      const passInput = document.querySelector("#login-password");
      if (emailInput && passInput) {
        emailInput.value = btn.dataset.demoEmail;
        passInput.value = btn.dataset.demoPass;
        showToast(`Đã điền tài khoản demo: ${btn.dataset.demoLabel}`, "info");
      }
    });
  });

  // 5. AJAX Favorite Toggle (supports both icon button and Nhà Tốt pill button)
  document.querySelectorAll("[data-fav-toggle]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.dataset.favToggle;
      try {
        const res = await fetch(`/api/favorites/${id}/toggle`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) {
          showToast(data.message || "Vui lòng đăng nhập để lưu phòng.", "error");
          if (res.status === 401) {
            setTimeout(() => (window.location.href = "/auth?tab=login"), 900);
          }
          return;
        }
        btn.classList.toggle("active", data.favorited);
        if (btn.dataset.favStyle === "pill") {
          const ico = btn.querySelector(".heart-ico");
          const txt = btn.querySelector(".save-txt");
          if (ico) ico.innerHTML = data.favorited ? "&#10084;" : "&#9825;";
          if (txt) txt.textContent = data.favorited ? "Đã lưu" : "Lưu";
        } else {
          btn.innerHTML = data.favorited ? "&#10084;" : "&#9825;";
        }
        showToast(data.message, "success");

        if (!data.favorited && btn.closest("[data-favorites-page]")) {
          const card = btn.closest(".card");
          if (card) {
            card.style.opacity = "0";
            card.style.transform = "scale(0.95)";
            setTimeout(() => card.remove(), 280);
          }
        }
      } catch {
        showToast("Không thể kết nối máy chủ.", "error");
      }
    });
  });

  // 6. Admin Mode: Instant Approve / Reject / Delete
  document.querySelectorAll("[data-admin-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const listingId = btn.dataset.listingId;
      const action = btn.dataset.adminAction;
      const card = document.querySelector(`[data-mod-card="${listingId}"]`);
      if (!card) return;

      let note = "";
      if (action === "rejected") {
        note = window.prompt(
          "Nhập lý do từ chối bài đăng (tùy chọn):",
          "Vui lòng bổ sung ảnh rõ hơn và địa chỉ chi tiết."
        );
        if (note === null) return;
      }

      card.classList.add("is-updating");
      try {
        if (action === "delete") {
          if (!window.confirm("Bạn chắc chắn muốn xóa vĩnh viễn bài đăng này?")) {
            card.classList.remove("is-updating");
            return;
          }
          const res = await fetch(`/api/admin/listings/${listingId}/delete`, { method: "POST" });
          const data = await res.json();
          if (res.ok && data.ok) {
            card.classList.add("is-removing");
            setTimeout(() => card.remove(), 300);
            showToast(data.message, "info");
          }
          return;
        }

        const formData = new FormData();
        formData.append("action", action);
        formData.append("admin_note", note);

        const res = await fetch(`/api/admin/listings/${listingId}/review`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        card.classList.remove("is-updating");

        if (!res.ok || !data.ok) {
          showToast(data.message || "Có lỗi xảy ra.", "error");
          return;
        }

        const badge = card.querySelector("[data-status-badge]");
        const noteEl = card.querySelector("[data-admin-note]");
        if (badge) {
          badge.className = `status-badge status-${data.status}`;
          badge.textContent =
            data.status === "approved"
              ? "Đã duyệt"
              : data.status === "rejected"
              ? "Bị từ chối"
              : "Chờ duyệt";
        }
        if (noteEl) {
          noteEl.textContent = `Ghi chú Admin: ${data.admin_note}`;
        }

        if (data.counts) {
          ["all", "pending", "approved", "rejected"].forEach((key) => {
            const el = document.querySelector(`[data-kpi="${key}"]`);
            if (el) el.textContent = data.counts[key];
          });
        }
        showToast(data.message, data.status === "approved" ? "success" : "info");
      } catch {
        card.classList.remove("is-updating");
        showToast("Lỗi kết nối khi duyệt bài.", "error");
      }
    });
  });

  // 7. Live Unread Chat Badge Polling (when logged in)
  if (document.body.dataset.loggedIn === "1") {
    const refreshUnreadBadge = async () => {
      try {
        const res = await fetch("/api/chat/unread");
        if (!res.ok) return;
        const data = await res.json();
        updateNavUnread(data.unread_count || 0);
      } catch {
        // Ignore transient network errors
      }
    };
    setInterval(refreshUnreadBadge, 6000);
  }

  // 8. Chat Inbox Page Controller
  initChatInbox();
});

function updateNavUnread(count) {
  const badge = document.querySelector("[data-nav-unread]");
  if (!badge) return;
  badge.textContent = count;
  badge.classList.toggle("hidden", count <= 0);
}

function applyPricePreset(val) {
  const form = document.getElementById("nt-filter-form");
  if (!form) return;
  const minEl = document.getElementById("f-min-price");
  const maxEl = document.getElementById("f-max-price");
  if (!val) {
    minEl.value = "";
    maxEl.value = "";
  } else {
    const [minV, maxV] = val.split("-");
    minEl.value = minV && minV !== "0" ? minV : "";
    maxEl.value = maxV || "";
  }
  form.submit();
}

function applyAreaPreset(val) {
  const form = document.getElementById("nt-filter-form");
  if (!form) return;
  const minEl = document.getElementById("f-min-area");
  const maxEl = document.getElementById("f-max-area");
  if (!val) {
    minEl.value = "";
    maxEl.value = "";
  } else {
    const [minV, maxV] = val.split("-");
    minEl.value = minV && minV !== "0" ? minV : "";
    maxEl.value = maxV || "";
  }
  form.submit();
}

function applySort(sortVal) {
  const url = new URL(window.location.href);
  url.searchParams.set("sort", sortVal);
  window.location.href = url.toString();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function initChatInbox() {
  const appEl = document.getElementById("chat-app");
  if (!appEl) return;

  let activeConvId = appEl.dataset.activeConv ? Number(appEl.dataset.activeConv) : null;
  const currentUserId = Number(appEl.dataset.userId);
  let lastRenderedSignature = "";

  const convListEl = document.getElementById("chat-conv-list");
  const convCountEl = document.getElementById("chat-conv-count");
  const emptyThreadEl = document.getElementById("chat-thread-empty");
  const activeThreadEl = document.getElementById("chat-thread-active");
  const messagesEl = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  const partnerAvatarEl = document.getElementById("chat-partner-avatar");
  const partnerNameEl = document.getElementById("chat-partner-name");
  const partnerSubEl = document.getElementById("chat-partner-sub");
  const callBtnEl = document.getElementById("chat-call-btn");
  const listingBarEl = document.getElementById("chat-listing-bar");
  const listingImgEl = document.getElementById("chat-listing-img");
  const listingTitleEl = document.getElementById("chat-listing-title");
  const listingPriceEl = document.getElementById("chat-listing-price");
  const listingDistrictEl = document.getElementById("chat-listing-district");

  async function loadConversations() {
    try {
      const res = await fetch("/api/chat/conversations");
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok) return;

      updateNavUnread(data.unread_total || 0);
      if (convCountEl) convCountEl.textContent = data.conversations.length;

      if (!data.conversations.length) {
        convListEl.innerHTML = `
          <div class="chat-empty-list">
            <p>Chưa có cuộc trò chuyện nào.</p>
            <a class="btn btn-primary btn-sm" href="/">Tìm phòng để chat ngay</a>
          </div>`;
        return;
      }

      convListEl.innerHTML = data.conversations
        .map((c) => {
          const activeCls = c.id === activeConvId ? "active" : "";
          const timeText = (c.last_message_at || c.updated_at || "").slice(-5);
          const unreadHtml =
            c.unread_count > 0 ? `<span class="chat-unread-dot">${c.unread_count}</span>` : "";
          return `
            <button type="button" class="chat-conv-item ${activeCls}" data-conv-id="${c.id}">
              <img class="chat-conv-thumb" src="${escapeHtml(c.listing_image)}" alt="" />
              <div class="chat-conv-body">
                <div class="chat-conv-top">
                  <strong class="chat-conv-name">${escapeHtml(c.partner_name)}</strong>
                  <span class="chat-conv-time">${escapeHtml(timeText)}</span>
                </div>
                <div class="chat-conv-listing">${escapeHtml(c.listing_title)}</div>
                <div class="chat-conv-bottom">
                  <span class="chat-conv-preview">${escapeHtml(c.last_message || "Bắt đầu cuộc trò chuyện...")}</span>
                  ${unreadHtml}
                </div>
              </div>
            </button>`;
        })
        .join("");

      convListEl.querySelectorAll("[data-conv-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const cid = Number(btn.dataset.convId);
          selectConversation(cid);
        });
      });
    } catch {
      // Ignore polling error
    }
  }

  async function loadMessages(convId, forceScroll = false) {
    if (!convId) return;
    try {
      const res = await fetch(`/api/chat/conversations/${convId}/messages`);
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok) return;

      const conv = data.conversation;
      emptyThreadEl.style.display = "none";
      activeThreadEl.style.display = "flex";

      partnerAvatarEl.textContent = (conv.partner_name || "?").charAt(0).toUpperCase();
      partnerNameEl.textContent = conv.partner_name;
      partnerSubEl.textContent =
        conv.partner_role === "landlord" ? "Chủ trọ · Đang hoạt động" : "Người tìm trọ · Đang hoạt động";
      callBtnEl.href = `tel:${conv.partner_phone || conv.listing_phone}`;
      callBtnEl.textContent = `Gọi ${conv.partner_phone || conv.listing_phone}`;

      listingBarEl.href = `/listing/${conv.listing_id}`;
      listingImgEl.src = conv.listing_image;
      listingTitleEl.textContent = conv.listing_title;
      listingPriceEl.textContent = conv.listing_price_text;
      listingDistrictEl.textContent = `· Q. ${conv.listing_district} · ${Math.round(conv.listing_area)} m²`;

      updateNavUnread(data.unread_total || 0);

      const sig = `${convId}:${data.messages.length}:${
        data.messages.length ? data.messages[data.messages.length - 1].id : 0
      }`;
      if (sig !== lastRenderedSignature) {
        lastRenderedSignature = sig;
        if (!data.messages.length) {
          messagesEl.innerHTML = `
            <div style="text-align:center; color:#6b7280; font-size:0.86rem; margin:auto;">
              Hãy gửi tin nhắn đầu tiên cho <strong>${escapeHtml(conv.partner_name)}</strong> để hỏi về phòng trọ này!
            </div>`;
        } else {
          messagesEl.innerHTML = data.messages
            .map((m) => {
              const mine = m.sender_id === currentUserId ? "me" : "other";
              return `
                <div class="msg-row ${mine}">
                  <div class="msg-bubble">${escapeHtml(m.content)}</div>
                  <div class="msg-time">${escapeHtml(m.created_at)}</div>
                </div>`;
            })
            .join("");
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } else if (forceScroll) {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    } catch {
      // Ignore polling error
    }
  }

  function selectConversation(convId) {
    activeConvId = convId;
    lastRenderedSignature = "";
    const url = new URL(window.location.href);
    url.searchParams.set("conv_id", convId);
    window.history.replaceState({}, "", url.toString());
    loadMessages(convId, true);
    loadConversations();
  }

  async function sendMessage(text) {
    if (!activeConvId || !text.trim()) return;
    const formData = new FormData();
    formData.append("content", text.trim());
    try {
      const res = await fetch(`/api/chat/conversations/${activeConvId}/messages`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showToast(data.message || "Không gửi được tin nhắn.", "error");
        return;
      }
      chatInput.value = "";
      await loadMessages(activeConvId, true);
      await loadConversations();
    } catch {
      showToast("Lỗi kết nối khi gửi tin nhắn.", "error");
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(chatInput.value);
  });

  document.querySelectorAll("[data-quick-msg]").forEach((btn) => {
    btn.addEventListener("click", () => {
      sendMessage(btn.dataset.quickMsg);
    });
  });

  convListEl.querySelectorAll("[data-conv-id]").forEach((btn) => {
    btn.addEventListener("click", () => selectConversation(Number(btn.dataset.convId)));
  });

  if (activeConvId) {
    loadMessages(activeConvId, true);
  }
  loadConversations();

  // Poll every 2.5 seconds for new messages
  setInterval(() => {
    if (activeConvId) loadMessages(activeConvId, false);
    loadConversations();
  }, 2500);
}

function showToast(message, category = "success") {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  const toast = document.createElement("div");
  toast.className = `toast ${category}`;
  toast.textContent = message;
  stack.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}
