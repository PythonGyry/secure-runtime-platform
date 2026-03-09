function escapeAttr(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const state = {
  token: null,
  bootstrap: null,
  apps: [],
  releases: [],
  licenses: [],
  keys: [],
  licensesAppFilter: "",
  keysStatusFilter: "",
  releasesTab: { app: "", channel: "" },
};

const loginView = document.getElementById("login-view");
const dashboardView = document.getElementById("dashboard-view");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const serverSummary = document.getElementById("server-summary");
const licensesTable = document.getElementById("licenses-table");
const keysTable = document.getElementById("keys-table");
const releasesTable = document.getElementById("releases-table");
const auditLog = document.getElementById("audit-log");

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const msg = Array.isArray(payload.detail)
      ? payload.detail.map((e) => e.msg || JSON.stringify(e)).join("; ")
      : typeof payload.detail === "string"
        ? payload.detail
        : "Request failed";
    throw new Error(msg);
  }
  return response.json();
}

function toggleView(isAuthenticated) {
  loginView.classList.toggle("hidden", isAuthenticated);
  dashboardView.classList.toggle("hidden", !isAuthenticated);
  if (isAuthenticated) {
    initMobileNav();
  }
}

function initMobileNav() {
  const nav = document.getElementById("mobile-nav");
  const tabs = nav?.querySelectorAll(".mobile-nav-tab");
  const panels = document.querySelectorAll(".mobile-panel");
  if (!tabs?.length || !panels.length) return;

  function showPanel(panelId) {
    panels.forEach((p) => {
      const match = p.dataset.mobilePanel === panelId;
      p.classList.toggle("mobile-panel-visible", match);
    });
    tabs.forEach((t) => {
      t.classList.toggle("active", t.dataset.panel === panelId);
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => showPanel(tab.dataset.panel));
  });

  showPanel("licenses");
}

function formatChannelAccess(ca) {
  if (!ca) return "";
  if (Array.isArray(ca)) return ca.join(", ");
  return Object.entries(ca)
    .map(([app, chs]) => `${app}: ${(chs || []).join(", ")}`)
    .join("; ");
}

function renderLicenses(items) {
  const appFilter = state.licensesAppFilter || "";
  let filtered = items;
  if (appFilter) {
    filtered = items.filter((item) => {
      const ca = item.channel_access;
      if (Array.isArray(ca)) return appFilter === "wishlist";
      if (ca && typeof ca === "object") return ca[appFilter];
      return false;
    });
  }
  const rows = filtered.map((item) => ({
    ...item,
    caStr: formatChannelAccess(item.channel_access),
  }));
  licensesTable.innerHTML = rows.map((item) => `
    <tr>
      <td>${item.license_id}</td>
      <td class="copyable-key" data-key="${escapeAttr(item.license_key)}" title="Клік для копіювання">${item.license_key}</td>
      <td>${item.display_name}</td>
      <td>${item.status}</td>
      <td>${item.caStr}</td>
      <td>${item.bound_hwid || ""}</td>
      <td>
        <div class="inline-actions">
          <button data-action="toggle-license" data-id="${item.license_id}" data-status="${item.status}">
            ${item.status === "active" ? "Disable" : "Enable"}
          </button>
          <button class="secondary" data-action="unbind-license" data-id="${item.license_id}">Unbind</button>
          <button class="secondary" data-action="regenerate-license" data-id="${item.license_id}">Regenerate</button>
          <button class="secondary" data-action="delete-license" data-id="${item.license_id}">Delete</button>
        </div>
      </td>
    </tr>
  `).join("");
  const cardsEl = document.getElementById("licenses-cards");
  if (cardsEl) {
    cardsEl.innerHTML = rows.map((item) => `
      <div class="card" data-id="${item.license_id}">
        <div class="card-row"><span class="card-label">ID</span><span class="card-value">${item.license_id}</span></div>
        <div class="card-row"><span class="card-label">Key</span><span class="card-value copyable-key" data-key="${escapeAttr(item.license_key)}" title="Клік для копіювання">${item.license_key}</span></div>
        <div class="card-row"><span class="card-label">Name</span><span class="card-value">${item.display_name}</span></div>
        <div class="card-row"><span class="card-label">Status</span><span class="card-value">${item.status}</span></div>
        <div class="card-row"><span class="card-label">Access</span><span class="card-value">${item.caStr}</span></div>
        <div class="card-row"><span class="card-label">HWID</span><span class="card-value">${item.bound_hwid || "—"}</span></div>
        <div class="card-actions inline-actions">
          <button data-action="toggle-license" data-id="${item.license_id}" data-status="${item.status}">${item.status === "active" ? "Disable" : "Enable"}</button>
          <button class="secondary" data-action="unbind-license" data-id="${item.license_id}">Unbind</button>
          <button class="secondary" data-action="regenerate-license" data-id="${item.license_id}">Regenerate</button>
          <button class="secondary" data-action="delete-license" data-id="${item.license_id}">Delete</button>
        </div>
      </div>
    `).join("");
  }
}

function renderKeys(items) {
  const statusFilter = state.keysStatusFilter || "";
  const filtered = statusFilter ? items.filter((k) => k.status === statusFilter) : items;
  keysTable.innerHTML = filtered.map((item) => `
    <tr>
      <td>${item.key_id}</td>
      <td>${item.status}</td>
      <td>${item.created_at}</td>
      <td>
        <div class="inline-actions">
          <button data-action="activate-key" data-id="${item.key_id}">Activate</button>
          <button class="secondary" data-action="retire-key" data-id="${item.key_id}">Retire</button>
        </div>
      </td>
    </tr>
  `).join("");
  const cardsEl = document.getElementById("keys-cards");
  if (cardsEl) {
    cardsEl.innerHTML = filtered.map((item) => `
      <div class="card">
        <div class="card-row"><span class="card-label">Key ID</span><span class="card-value">${item.key_id}</span></div>
        <div class="card-row"><span class="card-label">Status</span><span class="card-value">${item.status}</span></div>
        <div class="card-row"><span class="card-label">Created</span><span class="card-value">${item.created_at}</span></div>
        <div class="card-actions inline-actions">
          <button data-action="activate-key" data-id="${item.key_id}">Activate</button>
          <button class="secondary" data-action="retire-key" data-id="${item.key_id}">Retire</button>
        </div>
      </div>
    `).join("");
  }
}

function renderReleases(items) {
  releasesTable.innerHTML = items.map((item) => `
    <tr>
      <td>${item.app || "wishlist"}</td>
      <td>${item.channel}</td>
      <td>${item.version}</td>
      <td>${item.status}</td>
      <td>${item.package_file}</td>
      <td>
        <div class="inline-actions">
          <button data-action="publish-release" data-app="${item.app || "wishlist"}" data-channel="${item.channel}" data-version="${item.version}">Publish</button>
          <button class="secondary" data-action="deprecate-release" data-app="${item.app || "wishlist"}" data-channel="${item.channel}" data-version="${item.version}">Deprecate</button>
        </div>
      </td>
    </tr>
  `).join("");
  const cardsEl = document.getElementById("releases-cards");
  if (cardsEl) {
    cardsEl.innerHTML = items.map((item) => `
      <div class="card">
        <div class="card-row"><span class="card-label">App</span><span class="card-value">${item.app || "wishlist"}</span></div>
        <div class="card-row"><span class="card-label">Channel</span><span class="card-value">${item.channel}</span></div>
        <div class="card-row"><span class="card-label">Version</span><span class="card-value">${item.version}</span></div>
        <div class="card-row"><span class="card-label">Status</span><span class="card-value">${item.status}</span></div>
        <div class="card-row"><span class="card-label">Package</span><span class="card-value">${item.package_file}</span></div>
        <div class="card-actions inline-actions">
          <button data-action="publish-release" data-app="${item.app || "wishlist"}" data-channel="${item.channel}" data-version="${item.version}">Publish</button>
          <button class="secondary" data-action="deprecate-release" data-app="${item.app || "wishlist"}" data-channel="${item.channel}" data-version="${item.version}">Deprecate</button>
        </div>
      </div>
    `).join("");
  }
}

function renderAudit(items) {
  auditLog.textContent = items.map((item) => {
    return `[${item.created_at}] ${item.username} ${item.action} ${item.payload_json}`;
  }).join("\n");
}

async function refreshAll() {
  state.bootstrap = await api("/api/admin/bootstrap");
  serverSummary.textContent = `Default channel: ${state.bootstrap.server.default_channel}. Trusted keys: ${Object.keys(state.bootstrap.server.trusted_public_keys).length}.`;

  const [appsRes, licenses, keys, releases, audit] = await Promise.all([
    api("/api/admin/apps"),
    api("/api/admin/licenses"),
    api("/api/admin/keys"),
    api("/api/admin/releases"),
    api("/api/admin/audit"),
  ]);
  state.apps = Array.isArray(appsRes?.items) ? appsRes.items : [];
  state.licenses = licenses.items;
  state.keys = keys.items;
  state.releases = releases.items;
  const { app: tabApp, channel: tabChannel } = state.releasesTab;
  const filteredReleases = releases.items.filter((r) => {
    const app = r.app || "wishlist";
    if (tabApp && app !== tabApp) return false;
    if (tabChannel && r.channel !== tabChannel) return false;
    return true;
  });
  renderLicenses(licenses.items);
  renderKeys(keys.items);
  renderReleases(filteredReleases);
  renderAudit(audit.items);
  updateReleasesTabs();
  updateReleasesFilterDropdown();
  updateLicensesAppDropdown();
  updateKeysStatusDropdown();
  updateAppVersionDropdown();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  try {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const payload = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    state.token = payload.session_token;
    toggleView(true);
    await refreshAll();
  } catch (error) {
    loginError.textContent = error.message;
  }
});

document.getElementById("logout-button").addEventListener("click", async () => {
  try {
    await api("/api/admin/logout", { method: "POST" });
  } finally {
    state.token = null;
    toggleView(false);
  }
});

function getSelectedAppChannels() {
  const panel = document.getElementById("app-version-panel");
  if (!panel) return {};
  const selected = Array.from(panel.querySelectorAll("input:checked")).map((cb) => cb.value);
  const result = {};
  for (const v of selected) {
    const [app, channel] = v.split("|");
    if (app && channel) {
      if (!result[app]) result[app] = [];
      result[app].push(channel);
    }
  }
  return result;
}

function updateAppVersionDropdown() {
  const panel = document.getElementById("app-version-panel");
  const valueEl = document.getElementById("app-version-value");
  if (!panel || !valueEl) return;
  const releases = state.releases || [];
  const appsFromApi = state.apps || [];
  const appsFromReleases = [...new Set(releases.map((r) => r.app).filter(Boolean))];
  const allApps = [...new Set([...appsFromApi, ...appsFromReleases])].sort();
  const pairs = [];
  const seen = new Set();
  for (const r of releases) {
    const app = r.app || "wishlist";
    const ch = r.channel || "stable";
    const key = `${app}|${ch}`;
    if (!seen.has(key)) {
      seen.add(key);
      pairs.push({ app, channel: ch });
    }
  }
  if (!pairs.length && allApps.length) {
    for (const app of allApps) {
      pairs.push({ app, channel: "stable" });
    }
  }
  if (!pairs.length) {
    pairs.push({ app: allApps[0] || "wishlist", channel: "stable" });
  }
  const selected = getSelectedAppChannels();
  panel.innerHTML = pairs
    .map(({ app, channel }) => {
      const val = `${app}|${channel}`;
      const isChecked = selected[app]?.includes(channel);
      return `<label class="dropdown-option"><input type="checkbox" value="${val}" ${isChecked ? "checked" : ""} /> ${app} / ${channel}</label>`;
    })
    .join("");
  const sel = getSelectedAppChannels();
  const label = Object.entries(sel)
    .map(([a, chs]) => `${a}: ${chs.join(", ")}`)
    .join("; ");
  valueEl.textContent = label || "Обрати програму та версію";
  valueEl.classList.toggle("empty", !label);
  panel.querySelectorAll("input").forEach((cb) => {
    cb.addEventListener("change", () => {
      const s = getSelectedAppChannels();
      const l = Object.entries(s).map(([a, chs]) => `${a}: ${chs.join(", ")}`).join("; ");
      valueEl.textContent = l || "Обрати програму та версію";
      valueEl.classList.toggle("empty", !l);
    });
  });
}

function updateReleasesTabs() {
  const bar = document.getElementById("releases-tabs");
  if (!bar) return;
  const tabs = getReleasesTabOptions();
  const { app: curApp, channel: curCh } = state.releasesTab;
  bar.innerHTML = tabs.map((t) => {
    const active = t.app === curApp && t.channel === curCh ? " active" : "";
    return `<button type="button" class="tab${active}" data-app="${t.app}" data-channel="${t.channel}">${t.label}</button>`;
  }).join("");
  bar.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.releasesTab = { app: btn.dataset.app || "", channel: btn.dataset.channel || "" };
      bar.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const filtered = state.releases.filter((r) => {
        const app = r.app || "wishlist";
        if (state.releasesTab.app && app !== state.releasesTab.app) return false;
        if (state.releasesTab.channel && r.channel !== state.releasesTab.channel) return false;
        return true;
      });
      renderReleases(filtered);
      updateReleasesFilterDropdown();
    });
  });
}

function updateLicensesAppDropdown() {
  const panel = document.getElementById("licenses-app-panel");
  const valueEl = document.getElementById("licenses-app-value");
  if (!panel || !valueEl) return;
  const apps = state.apps || [];
  const options = [{ value: "", label: "All apps" }, ...apps.map((a) => ({ value: a, label: a }))];
  const cur = state.licensesAppFilter;
  panel.innerHTML = options.map((o) => {
    const checked = o.value === cur;
    return `<label class="dropdown-option"><input type="radio" name="licenses-app" value="${o.value}" ${checked ? "checked" : ""} /> ${o.label}</label>`;
  }).join("");
  valueEl.textContent = options.find((o) => o.value === cur)?.label || "All apps";
  panel.querySelectorAll("input").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.licensesAppFilter = radio.value;
      valueEl.textContent = options.find((o) => o.value === radio.value)?.label || "All apps";
      document.getElementById("licenses-app-dropdown")?.classList.remove("open");
      renderLicenses(state.licenses);
    });
  });
}

function initLicensesAppDropdown() {
  const dropdown = document.getElementById("licenses-app-dropdown");
  const trigger = document.getElementById("licenses-app-trigger");
  const panel = document.getElementById("licenses-app-panel");
  if (!dropdown || !trigger || !panel) return;
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });
  document.addEventListener("click", () => dropdown.classList.remove("open"));
  panel.addEventListener("click", (e) => e.stopPropagation());
}

function updateKeysStatusDropdown() {
  const panel = document.getElementById("keys-status-panel");
  const valueEl = document.getElementById("keys-status-value");
  if (!panel || !valueEl) return;
  const options = [
    { value: "", label: "All statuses" },
    { value: "active", label: "active" },
    { value: "trusted", label: "trusted" },
    { value: "retired", label: "retired" },
  ];
  const cur = state.keysStatusFilter || "";
  panel.innerHTML = options.map((o) => {
    const checked = o.value === cur;
    return `<label class="dropdown-option"><input type="radio" name="keys-status" value="${o.value}" ${checked ? "checked" : ""} /> ${o.label}</label>`;
  }).join("");
  valueEl.textContent = options.find((o) => o.value === cur)?.label || "All statuses";
  panel.querySelectorAll("input").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.keysStatusFilter = radio.value;
      valueEl.textContent = options.find((o) => o.value === radio.value)?.label || "All statuses";
      document.getElementById("keys-status-dropdown")?.classList.remove("open");
      renderKeys(state.keys);
    });
  });
}

function initKeysStatusDropdown() {
  const dropdown = document.getElementById("keys-status-dropdown");
  const trigger = document.getElementById("keys-status-trigger");
  const panel = document.getElementById("keys-status-panel");
  if (!dropdown || !trigger || !panel) return;
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });
  document.addEventListener("click", () => dropdown.classList.remove("open"));
  panel.addEventListener("click", (e) => e.stopPropagation());
}

function getReleasesTabOptions() {
  const appsFromApi = state.apps || [];
  const releases = state.releases || [];
  const appsFromReleases = [...new Set(releases.map((r) => r.app).filter(Boolean))];
  const apps = [...new Set([...appsFromApi, ...appsFromReleases])].sort();
  const channels = [...new Set(releases.map((r) => r.channel).filter(Boolean))];
  const tabs = [{ app: "", channel: "", label: "All" }];
  for (const app of apps) {
    const appChannels = [...new Set(releases.filter((r) => (r.app || "wishlist") === app).map((r) => r.channel))];
    if (appChannels.length) {
      for (const ch of appChannels) {
        tabs.push({ app, channel: ch, label: `${app} / ${ch}` });
      }
    } else {
      tabs.push({ app, channel: "", label: app });
    }
  }
  if (channels.length && !apps.length) {
    for (const ch of channels) {
      tabs.push({ app: "", channel: ch, label: ch });
    }
  }
  return tabs;
}

function updateReleasesFilterDropdown() {
  const panel = document.getElementById("releases-filter-panel");
  const valueEl = document.getElementById("releases-filter-value");
  if (!panel || !valueEl) return;
  const tabs = getReleasesTabOptions();
  const { app: curApp, channel: curCh } = state.releasesTab;
  panel.innerHTML = tabs.map((t) => {
    const active = t.app === curApp && t.channel === curCh;
    return `<label class="dropdown-option"><input type="radio" name="releases-filter" value="${t.app}|${t.channel}" data-app="${t.app}" data-channel="${t.channel}" ${active ? "checked" : ""} /> ${t.label}</label>`;
  }).join("");
  const curLabel = tabs.find((t) => t.app === curApp && t.channel === curCh)?.label || "All";
  valueEl.textContent = curLabel;
  panel.querySelectorAll("input").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.releasesTab = { app: radio.dataset.app || "", channel: radio.dataset.channel || "" };
      valueEl.textContent = tabs.find((t) => t.app === radio.dataset.app && t.channel === radio.dataset.channel)?.label || "All";
      document.getElementById("releases-filter-dropdown")?.classList.remove("open");
      const filtered = state.releases.filter((r) => {
        const app = r.app || "wishlist";
        if (state.releasesTab.app && app !== state.releasesTab.app) return false;
        if (state.releasesTab.channel && r.channel !== state.releasesTab.channel) return false;
        return true;
      });
      renderReleases(filtered);
      updateReleasesTabs();
    });
  });
}

function initReleasesFilterDropdown() {
  const dropdown = document.getElementById("releases-filter-dropdown");
  const trigger = document.getElementById("releases-filter-trigger");
  const panel = document.getElementById("releases-filter-panel");
  if (!dropdown || !trigger || !panel) return;
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });
  document.addEventListener("click", () => dropdown.classList.remove("open"));
  panel.addEventListener("click", (e) => e.stopPropagation());
}

function initAppVersionDropdown() {
  const dropdown = document.getElementById("app-version-dropdown");
  const trigger = document.getElementById("app-version-trigger");
  const panel = document.getElementById("app-version-panel");
  if (!dropdown || !trigger || !panel) return;
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });
  document.addEventListener("click", () => dropdown.classList.remove("open"));
  panel.addEventListener("click", (e) => e.stopPropagation());
}

document.getElementById("license-no-expiry").addEventListener("change", (e) => {
  const input = document.getElementById("license-expires-at");
  const wrapper = document.getElementById("license-expires-wrapper");
  input.disabled = e.target.checked;
  wrapper.classList.toggle("disabled", e.target.checked);
});

document.getElementById("license-expires-wrapper").addEventListener("click", () => {
  const input = document.getElementById("license-expires-at");
  if (!input.disabled && typeof input.showPicker === "function") {
    input.focus();
    input.showPicker();
  }
});

document.getElementById("license-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const noExpiry = document.getElementById("license-no-expiry").checked;
  let expiresAt = null;
  if (!noExpiry) {
    const val = document.getElementById("license-expires-at").value.trim();
    if (val) {
      expiresAt = val.length === 16 ? val + ":00" : val;
    }
  }
  const appChannelAccess = getSelectedAppChannels();
  const defaultApp = (state.apps || [])[0] || (state.releases || [])[0]?.app || "wishlist";
  const channelAccess = Object.keys(appChannelAccess).length ? appChannelAccess : { [defaultApp]: ["stable"] };
  const payload = {
    display_name: document.getElementById("license-display-name").value.trim(),
    channel_access: channelAccess,
    expires_at: expiresAt,
    notes: document.getElementById("license-notes").value.trim(),
  };
  await api("/api/admin/licenses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  event.target.reset();
  document.getElementById("license-no-expiry").checked = true;
  document.getElementById("license-expires-at").disabled = true;
  updateAppVersionDropdown();
  await refreshAll();
});

initAppVersionDropdown();
initLicensesAppDropdown();
initKeysStatusDropdown();
initReleasesFilterDropdown();

document.getElementById("refresh-licenses").addEventListener("click", refreshAll);
document.getElementById("generate-key").addEventListener("click", async () => {
  await api("/api/admin/keys", { method: "POST" });
  await refreshAll();
});
document.getElementById("sync-releases").addEventListener("click", async () => {
  await api("/api/admin/releases/sync", { method: "POST" });
  await refreshAll();
});

document.body.addEventListener("click", async (event) => {
  const copyable = event.target.closest(".copyable-key");
  if (copyable) {
    const key = copyable.dataset.key;
    if (key) {
      try {
        await navigator.clipboard.writeText(key);
        const orig = copyable.textContent;
        copyable.textContent = "Скопійовано!";
        copyable.style.color = "var(--success, #22c55e)";
        copyable.style.cursor = "default";
        setTimeout(() => {
          copyable.textContent = orig;
          copyable.style.color = "";
          copyable.style.cursor = "";
        }, 1200);
      } catch {
        /* clipboard API unavailable */
      }
    }
    return;
  }
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }
  const action = button.dataset.action;
  if (action === "toggle-license") {
    const nextStatus = button.dataset.status === "active" ? "disabled" : "active";
    await api(`/api/admin/licenses/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus }),
    });
  } else if (action === "unbind-license") {
    await api(`/api/admin/licenses/${button.dataset.id}/unbind`, { method: "POST" });
  } else if (action === "regenerate-license") {
    await api(`/api/admin/licenses/${button.dataset.id}/regenerate`, { method: "POST" });
  } else if (action === "delete-license") {
    await api(`/api/admin/licenses/${button.dataset.id}`, { method: "DELETE" });
  } else if (action === "activate-key") {
    await api(`/api/admin/keys/${button.dataset.id}/activate`, { method: "POST" });
  } else if (action === "retire-key") {
    await api(`/api/admin/keys/${button.dataset.id}/retire`, { method: "POST" });
  } else if (action === "publish-release") {
    const app = button.dataset.app || "wishlist";
    await api(`/api/admin/releases/${encodeURIComponent(app)}/${encodeURIComponent(button.dataset.channel)}/${encodeURIComponent(button.dataset.version)}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "published" }),
    });
  } else if (action === "deprecate-release") {
    const app = button.dataset.app || "wishlist";
    await api(`/api/admin/releases/${encodeURIComponent(app)}/${encodeURIComponent(button.dataset.channel)}/${encodeURIComponent(button.dataset.version)}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "deprecated" }),
    });
  }
  await refreshAll();
});

toggleView(false);
