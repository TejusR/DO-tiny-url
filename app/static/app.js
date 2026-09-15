const form = document.querySelector("#link-form");
const urlInput = document.querySelector("#url");
const aliasInput = document.querySelector("#custom-alias");
const submitButton = document.querySelector("#submit-button");
const statusRegion = document.querySelector("#status");
const successPanel = document.querySelector("#success-panel");
const shortUrl = document.querySelector("#short-url");
const openLink = document.querySelector("#open-link");
const copyButton = document.querySelector("#copy-button");
const analyticsForm = document.querySelector("#analytics-form");
const analyticsAliasInput = document.querySelector("#analytics-alias");
const analyticsButton = document.querySelector("#analytics-button");
const analyticsStatus = document.querySelector("#analytics-status");
const analyticsPanel = document.querySelector("#analytics-panel");
const analyticsShortUrl = document.querySelector("#analytics-short-url");
const clickCount = document.querySelector("#click-count");
const createdAt = document.querySelector("#created-at");
const lastAccessedAt = document.querySelector("#last-accessed-at");
const originalUrl = document.querySelector("#original-url");

function setLoading(button, isLoading) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
  button.setAttribute("aria-busy", String(isLoading));
}

function showStatus(region, message, isSuccess = false) {
  region.textContent = message;
  region.classList.toggle("success", isSuccess);
}

function apiErrorMessage(detail, fallback) {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item?.msg === "string" ? item.msg.replace(/^Value error, /, "") : ""))
      .filter(Boolean);
    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  return fallback;
}

function formatDate(value) {
  if (!value) {
    return "Never";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!form.reportValidity()) {
    showStatus(statusRegion, "Please complete the highlighted fields.");
    return;
  }

  const payload = { url: urlInput.value.trim() };
  const customAlias = aliasInput.value.trim();
  if (customAlias) {
    payload.custom_alias = customAlias;
  }

  successPanel.hidden = true;
  showStatus(statusRegion, "Creating your short link…", true);
  setLoading(submitButton, true);

  try {
    const response = await fetch("/api/v1/links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        apiErrorMessage(
          data.detail,
          "We couldn't shorten that link. Please check the details and try again.",
        ),
      );
    }

    shortUrl.textContent = data.short_url;
    shortUrl.href = data.short_url;
    openLink.href = data.short_url;
    successPanel.hidden = false;
    analyticsAliasInput.value = data.alias;
    showStatus(statusRegion, "Your short link is ready.", true);
    shortUrl.focus();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Something went wrong. Please try again.";
    showStatus(statusRegion, message);
  } finally {
    setLoading(submitButton, false);
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(shortUrl.href);
    copyButton.textContent = "Copied";
    showStatus(statusRegion, "Short link copied to your clipboard.", true);
    window.setTimeout(() => {
      copyButton.textContent = "Copy";
    }, 1800);
  } catch {
    showStatus(statusRegion, "Copy isn't available here. Select the short link and copy it manually.");
    shortUrl.focus();
  }
});

analyticsForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!analyticsForm.reportValidity()) {
    showStatus(analyticsStatus, "Enter a valid link alias.");
    return;
  }

  const alias = analyticsAliasInput.value.trim();
  analyticsPanel.hidden = true;
  showStatus(analyticsStatus, "Loading analytics…", true);
  setLoading(analyticsButton, true);

  try {
    const response = await fetch(`/api/v1/links/${encodeURIComponent(alias)}`);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(apiErrorMessage(data.detail, "We couldn't load analytics for that link."));
    }

    analyticsShortUrl.textContent = data.short_url;
    analyticsShortUrl.href = data.short_url;
    clickCount.textContent = String(data.click_count);
    createdAt.textContent = formatDate(data.created_at);
    lastAccessedAt.textContent = formatDate(data.last_accessed_at);
    originalUrl.textContent = data.original_url;
    analyticsPanel.hidden = false;
    showStatus(analyticsStatus, "Analytics loaded.", true);
    analyticsPanel.focus();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Something went wrong. Please try again.";
    showStatus(analyticsStatus, message);
  } finally {
    setLoading(analyticsButton, false);
  }
});
