const form = document.querySelector("#link-form");
const urlInput = document.querySelector("#url");
const aliasInput = document.querySelector("#custom-alias");
const submitButton = document.querySelector("#submit-button");
const statusRegion = document.querySelector("#status");
const successPanel = document.querySelector("#success-panel");
const shortUrl = document.querySelector("#short-url");
const openLink = document.querySelector("#open-link");
const copyButton = document.querySelector("#copy-button");

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitButton.classList.toggle("loading", isLoading);
  submitButton.setAttribute("aria-busy", String(isLoading));
}

function showStatus(message, isSuccess = false) {
  statusRegion.textContent = message;
  statusRegion.classList.toggle("success", isSuccess);
}

function validationMessage(detail) {
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

  return "We couldn't shorten that link. Please check the details and try again.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!form.reportValidity()) {
    showStatus("Please complete the highlighted fields.");
    return;
  }

  const payload = { url: urlInput.value.trim() };
  const customAlias = aliasInput.value.trim();
  if (customAlias) {
    payload.custom_alias = customAlias;
  }

  successPanel.hidden = true;
  showStatus("Creating your short link…", true);
  setLoading(true);

  try {
    const response = await fetch("/api/v1/links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(validationMessage(data.detail));
    }

    shortUrl.textContent = data.short_url;
    shortUrl.href = data.short_url;
    openLink.href = data.short_url;
    successPanel.hidden = false;
    showStatus("Your short link is ready.", true);
    shortUrl.focus();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Something went wrong. Please try again.";
    showStatus(message);
  } finally {
    setLoading(false);
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(shortUrl.href);
    copyButton.textContent = "Copied";
    showStatus("Short link copied to your clipboard.", true);
    window.setTimeout(() => {
      copyButton.textContent = "Copy";
    }, 1800);
  } catch {
    showStatus("Copy isn't available here. Select the short link and copy it manually.");
    shortUrl.focus();
  }
});
