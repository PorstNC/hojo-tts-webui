// Hojo TTS WebUI — frontend logic with i18n support (TTS + Settings/Key Management)
(function () {
  "use strict";

  // ===========================================================================
  // i18n Module
  // ===========================================================================
  const I18N_DEFAULT_LANG = "zh";
  const I18N_STORAGE_KEY = "hojo_tts_lang";
  let currentLang = I18N_DEFAULT_LANG;
  let i18nDict = {};
  let i18nReady = false;

  function getNested(obj, path) {
    return path.split(".").reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
  }

  function t(key, vars) {
    let val = getNested(i18nDict, key);
    if (val === undefined) {
      // Fallback: return the key itself (helps debugging)
      val = key;
    }
    if (vars && typeof val === "string") {
      Object.keys(vars).forEach(k => {
        val = val.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
      });
    }
    return val;
  }

  function applyI18n(root) {
    const scope = root || document;
    // Text content
    scope.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      const translated = t(key);
      if (translated !== key) el.textContent = translated;
    });
    // Placeholders
    scope.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      const key = el.getAttribute("data-i18n-placeholder");
      const translated = t(key);
      if (translated !== key) el.placeholder = translated;
    });
    // Values (buttons)
    scope.querySelectorAll("[data-i18n-value]").forEach(el => {
      const key = el.getAttribute("data-i18n-value");
      const translated = t(key);
      if (translated !== key) el.value = translated;
    });
    // Title attributes
    scope.querySelectorAll("[data-i18n-title]").forEach(el => {
      const key = el.getAttribute("data-i18n-title");
      const translated = t(key);
      if (translated !== key) el.title = translated;
    });
    // Update html lang
    document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  }

  async function loadLanguage(lang) {
    try {
      const res = await fetch("/locales/" + lang + ".json");
      if (!res.ok) throw new Error("HTTP " + res.status);
      i18nDict = await res.json();
      currentLang = lang;
      localStorage.setItem(I18N_STORAGE_KEY, lang);
      i18nReady = true;
      applyI18n();
      // Re-render dynamic content that depends on language
      if (typeof renderDynamicI18n === "function") renderDynamicI18n();
      return true;
    } catch (e) {
      console.error("Failed to load language:", lang, e);
      // Fallback to default
      if (lang !== I18N_DEFAULT_LANG) {
        return loadLanguage(I18N_DEFAULT_LANG);
      }
      return false;
    }
  }

  function initI18n() {
    const saved = localStorage.getItem(I18N_STORAGE_KEY);
    const langSelect = document.getElementById("langSelect");
    if (langSelect) {
      langSelect.value = saved || I18N_DEFAULT_LANG;
      langSelect.addEventListener("change", () => {
        loadLanguage(langSelect.value);
      });
    }
    return loadLanguage(saved || I18N_DEFAULT_LANG);
  }

  // ===========================================================================
  // Elements
  // ===========================================================================
  const textInput = document.getElementById("textInput");
  const voiceSelect = document.getElementById("voiceSelect");
  const synthesizeBtn = document.getElementById("synthesizeBtn");
  const clearBtn = document.getElementById("clearBtn");
  const charCount = document.getElementById("charCount");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const resultPanel = document.getElementById("resultPanel");
  const audioPlayer = document.getElementById("audioPlayer");
  const downloadLink = document.getElementById("downloadLink");
  const infoRow = document.getElementById("infoRow");
  const genTime = document.getElementById("genTime");
  const audioDuration = document.getElementById("audioDuration");
  const apiModelName = document.getElementById("apiModelName");
  const apiDefaultVoice = document.getElementById("apiDefaultVoice");
  const apiAuthStatus = document.getElementById("apiAuthStatus");
  const curlExample = document.getElementById("curlExample");
  const langSelect = document.getElementById("langSelect");

  // Settings tab elements
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const adminAuthPanel = document.getElementById("adminAuthPanel");
  const adminPasswordInput = document.getElementById("adminPasswordInput");
  const adminAuthBtn = document.getElementById("adminAuthBtn");
  const addKeyPanel = document.getElementById("addKeyPanel");
  const newKeyName = document.getElementById("newKeyName");
  const newKeyQuota = document.getElementById("newKeyQuota");
  const newKeyTokenQuota = document.getElementById("newKeyTokenQuota");
  const newKeyValue = document.getElementById("newKeyValue");
  const genKeyBtn = document.getElementById("genKeyBtn");
  const addKeyBtn = document.getElementById("addKeyBtn");
  const addKeyResult = document.getElementById("addKeyResult");
  const keysList = document.getElementById("keysList");
  const refreshKeysBtn = document.getElementById("refreshKeysBtn");
  const billingModePanel = document.getElementById("billingModePanel");
  const billingModeRadios = document.querySelectorAll('input[name="billingMode"]');
  const billingModeStatus = document.getElementById("billingModeStatus");

  let currentAudioUrl = null;
  let adminPassword = "";
  let adminPasswordSet = false;
  let billingModeLoading = false;
  let currentBillingMode = "per_call";
  let lastStatus = null;
  let lastVoices = null;

  // ===========================================================================
  // Dynamic i18n re-render (called after language switch)
  // ===========================================================================
  function renderDynamicI18n() {
    // Re-render status text
    if (lastStatus) {
      if (lastStatus.loaded) {
        setStatus("ready", t("status.ready") + " · " + lastStatus.platform + " · " + lastStatus.voices_count + " " + t("status.voices_count"));
      } else if (lastStatus.load_error) {
        setStatus("error", t("status.load_error") + ": " + lastStatus.load_error);
      } else {
        setStatus("loading", t("status.loading"));
      }
      // Re-render API auth status
      if (apiAuthStatus) {
        if (lastStatus.auth_required) {
          apiAuthStatus.textContent = t("api.auth_enabled") + " (" + lastStatus.keys_count + t("api.keys_count") + ")";
        } else {
          apiAuthStatus.textContent = t("api.auth_disabled");
        }
      }
      // Re-render curl example
      renderCurlExample(lastStatus);
    }
    // Re-render voices
    if (lastVoices && lastVoices.voices) {
      renderVoices(lastVoices);
    }
    // Re-render billing mode status
    if (billingModeStatus && currentBillingMode) {
      const modeLabels = {
        none: t("settings.billing_none"),
        per_call: t("settings.billing_per_call"),
        per_token: t("settings.billing_per_token"),
      };
      billingModeStatus.textContent = t("settings.billing_current") + ": " + (modeLabels[currentBillingMode] || currentBillingMode);
    }
    // Re-render keys list if loaded
    if (keysList && keysList.dataset.loadedKeys) {
      try {
        const keys = JSON.parse(keysList.dataset.loadedKeys);
        renderKeys(keys);
      } catch (_) {}
    }
  }

  // ===========================================================================
  // Tab switching
  // ===========================================================================
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      tabBtns.forEach(b => b.classList.toggle("active", b === btn));
      tabContents.forEach(c => c.classList.toggle("active", c.id === "tab-" + tab));
      if (tab === "settings") {
        loadKeys();
        loadBillingMode();
      }
    });
  });

  // ===========================================================================
  // Admin auth
  // ===========================================================================
  adminAuthBtn.addEventListener("click", () => {
    adminPassword = adminPasswordInput.value.trim();
    if (!adminPassword) {
      alert(t("settings.admin_please_input"));
      return;
    }
    loadKeys();
    loadBillingMode();
  });
  adminPasswordInput.addEventListener("keydown", e => {
    if (e.key === "Enter") adminAuthBtn.click();
  });

  function adminHeaders() {
    const h = { "Content-Type": "application/json" };
    if (adminPasswordSet && adminPassword) {
      h["X-Admin-Password"] = adminPassword;
    }
    return h;
  }

  // ===========================================================================
  // Character counter
  // ===========================================================================
  function updateCharCount() {
    const len = textInput.value.length;
    charCount.textContent = len + " / 20000";
    charCount.style.color = len > 20000 ? "var(--error)" : "";
  }
  textInput.addEventListener("input", updateCharCount);
  updateCharCount();

  // ===========================================================================
  // Status
  // ===========================================================================
  function setStatus(state, text) {
    statusDot.className = "status-dot " + state;
    statusText.textContent = text;
  }

  // ===========================================================================
  // Render voices (extracted for i18n re-render)
  // ===========================================================================
  function renderVoices(voices) {
    voiceSelect.innerHTML = "";
    if (voices.voices && voices.voices.length) {
      const zh = voices.voices.filter(v => v.id.startsWith("hojo_zh"));
      const en = voices.voices.filter(v => v.id.startsWith("hojo_en"));
      if (zh.length) {
        const zg = document.createElement("optgroup");
        zg.label = t("tts.voice_group_zh");
        zh.forEach(v => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = v.label + " (" + v.id + ")";
          zg.appendChild(opt);
        });
        voiceSelect.appendChild(zg);
      }
      if (en.length) {
        const eg = document.createElement("optgroup");
        eg.label = t("tts.voice_group_en");
        en.forEach(v => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = v.label + " (" + v.id + ")";
          eg.appendChild(opt);
        });
        voiceSelect.appendChild(eg);
      }
      const defaultVoice = voices.default_voice || (lastStatus && lastStatus.default_voice) || "hojo_zh_f_02";
      voiceSelect.value = defaultVoice;
      synthesizeBtn.disabled = false;
    } else {
      voiceSelect.innerHTML = '<option value="">' + t("tts.voice_none") + "</option>";
    }
  }

  // ===========================================================================
  // Render curl example (extracted for i18n re-render)
  // ===========================================================================
  function renderCurlExample(status) {
    if (!curlExample) return;
    const base = window.location.origin;
    const model = status.model_name || "hojo-tts-light-40m";
    const voice = status.default_voice || "hojo_zh_f_02";
    const authLine = status.auth_required
      ? '  -H "Authorization: Bearer YOUR_API_KEY" \\\n'
      : "";
    curlExample.textContent =
      "curl -X POST " + base + "/v1/audio/speech \\\n" +
      authLine +
      '  -H "Content-Type: application/json" \\\n' +
      "  -d '{\n" +
      '    "model": "' + model + '",\n' +
      '    "input": "' + t("api.curl_test_text") + '",\n' +
      '    "voice": "' + voice + '",\n' +
      '    "response_format": "wav"\n' +
      "  }' \\\n" +
      "  --output output.wav";
  }

  // ===========================================================================
  // Init: load status + voices
  // ===========================================================================
  async function init() {
    setStatus("loading", t("status.checking"));
    try {
      const [statusRes, voicesRes] = await Promise.all([
        fetch("/api/status"),
        fetch("/api/voices"),
      ]);
      const status = await statusRes.json();
      const voices = await voicesRes.json();
      lastStatus = status;
      lastVoices = voices;

      adminPasswordSet = status.admin_password_set || false;

      if (status.loaded) {
        setStatus("ready", t("status.ready") + " · " + status.platform + " · " + status.voices_count + " " + t("status.voices_count"));
      } else if (status.load_error) {
        setStatus("error", t("status.load_error") + ": " + status.load_error);
      } else {
        setStatus("loading", t("status.loading"));
      }

      // Populate API info
      if (apiModelName) apiModelName.textContent = status.model_name || "hojo-tts-light-40m";
      if (apiDefaultVoice) apiDefaultVoice.textContent = status.default_voice || "hojo_zh_f_02";
      if (apiAuthStatus) {
        if (status.auth_required) {
          apiAuthStatus.textContent = t("api.auth_enabled") + " (" + status.keys_count + t("api.keys_count") + ")";
          apiAuthStatus.style.color = "var(--success)";
        } else {
          apiAuthStatus.textContent = t("api.auth_disabled");
          apiAuthStatus.style.color = "var(--text-dim)";
        }
      }
      renderCurlExample(status);

      // Populate voice select
      renderVoices(voices);
    } catch (err) {
      setStatus("error", t("status.connect_failed") + ": " + err.message);
    }
  }

  // ===========================================================================
  // Synthesize (TTS tab)
  // ===========================================================================
  async function synthesize() {
    const text = textInput.value.trim();
    const voice = voiceSelect.value;
    if (!text) { alert(t("tts.alert_no_text")); return; }
    if (!voice) { alert(t("tts.alert_no_voice")); return; }

    synthesizeBtn.disabled = true;
    synthesizeBtn.querySelector(".btn-text").textContent = t("tts.synthesizing");
    synthesizeBtn.querySelector(".btn-spinner").hidden = false;
    resultPanel.hidden = true;
    infoRow.hidden = true;

    const t0 = performance.now();
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice }),
      });
      if (!res.ok) {
        let errMsg = t("tts.alert_failed");
        try { const err = await res.json(); errMsg = err.error || errMsg; } catch (_) {}
        throw new Error(errMsg);
      }
      const blob = await res.blob();
      const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
      if (currentAudioUrl) URL.revokeObjectURL(currentAudioUrl);
      currentAudioUrl = URL.createObjectURL(blob);
      audioPlayer.src = currentAudioUrl;
      downloadLink.href = currentAudioUrl;
      downloadLink.download = "hojo_tts_" + voice + "_" + Date.now() + ".wav";
      resultPanel.hidden = false;
      infoRow.hidden = false;
      genTime.textContent = t("tts.gen_time") + ": " + elapsed + "s";
      audioPlayer.addEventListener("loadedmetadata", function onMeta() {
        audioDuration.textContent = t("tts.audio_duration") + ": " + audioPlayer.duration.toFixed(1) + "s";
        audioPlayer.removeEventListener("loadedmetadata", onMeta);
      });
      audioPlayer.play().catch(() => {});
    } catch (err) {
      alert(t("tts.alert_failed") + ": " + err.message);
    } finally {
      synthesizeBtn.disabled = false;
      synthesizeBtn.querySelector(".btn-text").textContent = t("tts.synthesize");
      synthesizeBtn.querySelector(".btn-spinner").hidden = true;
    }
  }

  synthesizeBtn.addEventListener("click", synthesize);
  clearBtn.addEventListener("click", () => {
    textInput.value = "";
    updateCharCount();
    resultPanel.hidden = true;
  });
  textInput.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") synthesize();
  });

  // ===========================================================================
  // Key Management (Settings tab)
  // ===========================================================================
  async function loadKeys() {
    if (adminPasswordSet && !adminPassword) {
      adminAuthPanel.hidden = false;
      addKeyPanel.style.display = "none";
      keysList.innerHTML = '<p class="hint-text">' + t("settings.admin_please_verify") + "</p>";
      return;
    }
    adminAuthPanel.hidden = true;
    addKeyPanel.style.display = "";

    keysList.innerHTML = '<p class="hint-text">' + t("settings.keys_loading") + "</p>";
    try {
      const res = await fetch("/api/admin/keys", {
        method: "GET",
        headers: adminHeaders(),
      });
      if (res.status === 403) {
        keysList.innerHTML = '<p class="hint-text" style="color:var(--error)">' + t("settings.admin_wrong") + "</p>";
        adminPassword = "";
        adminAuthPanel.hidden = false;
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        keysList.innerHTML = '<p class="hint-text" style="color:var(--error)">' + t("settings.keys_load_failed") + ": " + (err.error || res.statusText) + "</p>";
        return;
      }
      const data = await res.json();
      // Store for i18n re-render
      keysList.dataset.loadedKeys = JSON.stringify(data.keys || []);
      renderKeys(data.keys || []);
    } catch (err) {
      keysList.innerHTML = '<p class="hint-text" style="color:var(--error)">' + t("settings.keys_load_failed") + ": " + err.message + "</p>";
    }
  }

  async function loadBillingMode() {
    if (adminPasswordSet && !adminPassword) {
      billingModePanel.style.display = "none";
      return;
    }
    billingModePanel.style.display = "";
    billingModeLoading = true;
    try {
      const res = await fetch("/api/admin/billing-mode", { headers: adminHeaders() });
      if (res.ok) {
        const data = await res.json();
        currentBillingMode = data.billing_mode;
        addKeyPanel.dataset.billingMode = data.billing_mode;
        billingModeRadios.forEach(r => {
          r.checked = (r.value === data.billing_mode);
        });
        const modeLabels = {
          none: t("settings.billing_none"),
          per_call: t("settings.billing_per_call"),
          per_token: t("settings.billing_per_token"),
        };
        billingModeStatus.textContent = t("settings.billing_current") + ": " + (modeLabels[data.billing_mode] || data.billing_mode);
        billingModeStatus.style.color = "var(--success)";
        loadKeys();
      }
    } catch (e) {
      billingModeStatus.textContent = t("settings.billing_load_failed") + ": " + e.message;
      billingModeStatus.style.color = "var(--error)";
    } finally {
      billingModeLoading = false;
    }
  }

  billingModeRadios.forEach(radio => {
    radio.addEventListener("change", async () => {
      if (billingModeLoading) return;
      const mode = radio.value;
      billingModeStatus.textContent = t("settings.billing_switching");
      billingModeStatus.style.color = "var(--text-dim)";
      try {
        const res = await fetch("/api/admin/billing-mode", {
          method: "POST",
          headers: adminHeaders(),
          body: JSON.stringify({ billing_mode: mode }),
        });
        if (res.ok) {
          currentBillingMode = mode;
          addKeyPanel.dataset.billingMode = mode;
          const modeLabels = {
            none: t("settings.billing_none"),
            per_call: t("settings.billing_per_call"),
            per_token: t("settings.billing_per_token"),
          };
          billingModeStatus.textContent = t("settings.billing_switched") + ": " + modeLabels[mode];
          billingModeStatus.style.color = "var(--success)";
          showToast(t("settings.billing_toast"));
          loadKeys();
        } else {
          const err = await res.json().catch(() => ({}));
          billingModeStatus.textContent = t("settings.billing_switch_failed") + ": " + (err.error || res.statusText);
          billingModeStatus.style.color = "var(--error)";
          loadBillingMode();
        }
      } catch (e) {
        billingModeStatus.textContent = t("settings.billing_switch_failed") + ": " + e.message;
        billingModeStatus.style.color = "var(--error)";
        loadBillingMode();
      }
    });
  });

  function renderKeys(keys) {
    if (!keys.length) {
      keysList.innerHTML = '<p class="hint-text">' + t("settings.keys_none") + "</p>";
      return;
    }
    keysList.innerHTML = "";
    keys.forEach(k => {
      const card = document.createElement("div");
      card.className = "key-card";

      // Build stats HTML based on billing mode
      let statsHtml = "";
      if (currentBillingMode === "per_call") {
        const remainingColor = k.quota !== -1 && k.remaining === 0 ? "var(--error)" : "var(--text)";
        statsHtml =
          '<div class="key-stats">' +
          "<span>" + t("settings.key_quota_stat") + ': <strong style="color:' + remainingColor + '">' + escapeHtml(String(k.quota_display)) + "</strong></span>" +
          "<span>" + t("settings.key_used_stat") + ": <strong>" + k.used + "</strong></span>" +
          "<span>" + t("settings.key_remaining_stat") + ': <strong style="color:' + remainingColor + '">' + escapeHtml(String(k.remaining)) + "</strong></span>" +
          "<span>" + t("settings.key_created_stat") + ": <strong>" + escapeHtml(k.created_at) + "</strong></span>" +
          "</div>";
      } else if (currentBillingMode === "per_token") {
        const tokenRemainingColor = k.token_quota !== -1 && k.token_remaining === 0 ? "var(--error)" : "var(--text)";
        statsHtml =
          '<div class="key-stats">' +
          "<span>" + t("settings.key_token_quota_stat") + ': <strong style="color:' + tokenRemainingColor + '">' + escapeHtml(String(k.token_quota_display)) + "</strong></span>" +
          "<span>" + t("settings.key_token_used_stat") + ": <strong>" + k.tokens_used + "</strong></span>" +
          "<span>" + t("settings.key_token_remaining_stat") + ': <strong style="color:' + tokenRemainingColor + '">' + escapeHtml(String(k.token_remaining)) + "</strong></span>" +
          "<span>" + t("settings.key_created_stat") + ": <strong>" + escapeHtml(k.created_at) + "</strong></span>" +
          "</div>";
      } else {
        statsHtml =
          '<div class="key-stats">' +
          "<span>" + t("settings.key_created_stat") + ": <strong>" + escapeHtml(k.created_at) + "</strong></span>" +
          '<span style="color:var(--text-dim)">' + t("settings.key_billing_disabled") + "</span>" +
          "</div>";
      }

      // Build action buttons based on billing mode
      let quotaButtons = "";
      if (currentBillingMode === "per_call") {
        quotaButtons =
          '<button class="btn btn-secondary" data-action="quota" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_quota") + "</button>" +
          '<button class="btn btn-secondary" data-action="reset" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_reset") + "</button>";
      } else if (currentBillingMode === "per_token") {
        quotaButtons =
          '<button class="btn btn-secondary" data-action="token_quota" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_token_quota") + "</button>" +
          '<button class="btn btn-secondary" data-action="reset_tokens" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_reset_tokens") + "</button>";
      }

      card.innerHTML =
        '<div class="key-card-header">' +
        '<span class="key-name">' + escapeHtml(k.name) + "</span>" +
        '<span class="key-string" title="' + t("settings.action_copy") + '">' + escapeHtml(k.key_masked) + "</span>" +
        "</div>" +
        statsHtml +
        '<div class="key-actions">' +
        '<button class="btn btn-secondary" data-action="copy" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_copy") + "</button>" +
        quotaButtons +
        '<button class="btn btn-secondary" data-action="rename" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_rename") + "</button>" +
        '<button class="btn btn-secondary" style="color:var(--error);border-color:var(--error)" data-action="delete" data-key="' + escapeHtml(k.key) + '">' + t("settings.action_delete") + "</button>" +
        "</div>";
      keysList.appendChild(card);
    });

    keysList.querySelectorAll("[data-action]").forEach(btn => {
      btn.addEventListener("click", () => handleKeyAction(btn.dataset.action, btn.dataset.key));
    });
  }

  async function handleKeyAction(action, key) {
    if (action === "copy") {
      try {
        await navigator.clipboard.writeText(key);
        showToast(t("settings.toast_copied"));
      } catch (_) {
        prompt(t("settings.toast_copied") + ":", key);
      }
      return;
    }
    if (action === "delete") {
      if (!confirm(t("settings.confirm_delete", { key: key.substring(0, 10) }))) return;
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "DELETE",
          headers: adminHeaders(),
        });
        if (res.ok) { showToast(t("settings.toast_deleted")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_delete_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_delete_failed") + ": " + e.message); }
      return;
    }
    if (action === "reset") {
      if (!confirm(t("settings.confirm_reset"))) return;
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "PUT",
          headers: adminHeaders(),
          body: JSON.stringify({ reset_used: true }),
        });
        if (res.ok) { showToast(t("settings.toast_reset")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_reset_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_reset_failed") + ": " + e.message); }
      return;
    }
    if (action === "reset_tokens") {
      if (!confirm(t("settings.confirm_reset_tokens"))) return;
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "PUT",
          headers: adminHeaders(),
          body: JSON.stringify({ reset_tokens: true }),
        });
        if (res.ok) { showToast(t("settings.toast_token_reset")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_reset_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_reset_failed") + ": " + e.message); }
      return;
    }
    if (action === "quota") {
      const input = prompt(t("settings.prompt_new_quota"), "-1");
      if (input === null) return;
      const quota = parseInt(input, 10);
      if (isNaN(quota) || quota < -1) { alert(t("settings.prompt_invalid_number")); return; }
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "PUT",
          headers: adminHeaders(),
          body: JSON.stringify({ quota }),
        });
        if (res.ok) { showToast(t("settings.toast_quota_updated")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_update_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_update_failed") + ": " + e.message); }
      return;
    }
    if (action === "token_quota") {
      const input = prompt(t("settings.prompt_new_token_quota"), "-1");
      if (input === null) return;
      const token_quota = parseInt(input, 10);
      if (isNaN(token_quota) || token_quota < -1) { alert(t("settings.prompt_invalid_number")); return; }
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "PUT",
          headers: adminHeaders(),
          body: JSON.stringify({ token_quota }),
        });
        if (res.ok) { showToast(t("settings.toast_token_updated")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_update_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_update_failed") + ": " + e.message); }
      return;
    }
    if (action === "rename") {
      const name = prompt(t("settings.prompt_new_name"), "");
      if (name === null || !name.trim()) return;
      try {
        const res = await fetch("/api/admin/keys/" + encodeURIComponent(key), {
          method: "PUT",
          headers: adminHeaders(),
          body: JSON.stringify({ name: name.trim() }),
        });
        if (res.ok) { showToast(t("settings.toast_renamed")); loadKeys(); }
        else { const err = await res.json().catch(()=>({})); alert(t("settings.alert_rename_failed") + ": " + (err.error || res.statusText)); }
      } catch (e) { alert(t("settings.alert_rename_failed") + ": " + e.message); }
      return;
    }
  }

  // Generate random key
  genKeyBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/admin/generate-key", {
        method: "POST",
        headers: adminHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        newKeyValue.value = data.key;
      }
    } catch (e) {
      newKeyValue.value = "sk-" + Array.from(crypto.getRandomValues(new Uint8Array(24))).map(b => b.toString(16).padStart(2, "0")).join("");
    }
  });

  // Add key
  addKeyBtn.addEventListener("click", async () => {
    const name = newKeyName.value.trim() || t("settings.key_unnamed");
    const quota = parseInt(newKeyQuota.value, 10);
    const token_quota = parseInt(newKeyTokenQuota.value, 10);
    const key = newKeyValue.value.trim();

    // Validate only the active billing mode's quota field
    if (currentBillingMode === "per_call" && (isNaN(quota) || quota < -1)) {
      alert(t("settings.key_quota_invalid")); return;
    }
    if (currentBillingMode === "per_token" && (isNaN(token_quota) || token_quota < -1)) {
      alert(t("settings.key_token_invalid")); return;
    }

    addKeyBtn.disabled = true;
    addKeyBtn.textContent = t("settings.key_adding");
    try {
      const body = {
        name,
        quota: currentBillingMode === "per_call" ? quota : -1,
        token_quota: currentBillingMode === "per_token" ? token_quota : -1,
      };
      if (key) body.key = key;
      const res = await fetch("/api/admin/keys", {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok || res.status === 201) {
        addKeyResult.hidden = false;
        addKeyResult.className = "key-result success";
        let quotaInfo = "";
        if (currentBillingMode === "per_call") {
          quotaInfo = t("settings.key_quota_stat") + ": " + (data.quota === -1 ? t("settings.key_quota_unlimited") : data.quota + " " + t("settings.key_quota_calls")) + "<br>";
        } else if (currentBillingMode === "per_token") {
          quotaInfo = t("settings.key_token_quota_stat") + ": " + (data.token_quota === -1 ? t("settings.key_token_unlimited") : data.token_quota + t("settings.key_token_unit")) + "<br>";
        }
        addKeyResult.innerHTML =
          "<strong>" + t("settings.key_add_success") + "</strong><br>" +
          t("settings.key_name_field") + ": " + escapeHtml(data.name) + "<br>" +
          quotaInfo +
          t("settings.key_full_key") + ': <code>' + escapeHtml(data.key) + "</code>";
        newKeyName.value = "";
        newKeyValue.value = "";
        newKeyQuota.value = "-1";
        newKeyTokenQuota.value = "-1";
        loadKeys();
      } else {
        addKeyResult.hidden = false;
        addKeyResult.className = "key-result error";
        addKeyResult.innerHTML = "<strong>" + t("settings.key_add_failed") + ":</strong> " + escapeHtml(data.error || res.statusText);
      }
    } catch (e) {
      addKeyResult.hidden = false;
      addKeyResult.className = "key-result error";
      addKeyResult.innerHTML = "<strong>" + t("settings.key_add_failed") + ":</strong> " + escapeHtml(e.message);
    } finally {
      addKeyBtn.disabled = false;
      addKeyBtn.textContent = t("settings.key_add");
    }
  });

  // Token quota preset buttons
  document.querySelectorAll(".token-preset").forEach(btn => {
    btn.addEventListener("click", () => {
      newKeyTokenQuota.value = btn.dataset.value;
    });
  });

  refreshKeysBtn.addEventListener("click", loadKeys);

  // ===========================================================================
  // Utilities
  // ===========================================================================
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  let toastTimer = null;
  function showToast(msg) {
    let toast = document.getElementById("toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "toast";
      toast.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--success);color:#fff;padding:10px 20px;border-radius:8px;font-size:0.85rem;z-index:9999;opacity:0;transition:opacity 0.3s;";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.style.opacity = "0"; }, 2000);
  }

  // ===========================================================================
  // Bootstrap: init i18n first, then init app
  // ===========================================================================
  initI18n().then(() => {
    init();
  });
})();
