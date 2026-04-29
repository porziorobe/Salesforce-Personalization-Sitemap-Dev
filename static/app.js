(function () {
  var pageUrlInput = document.getElementById('page-url');
  var customerNameInput = document.getElementById('customer-name');
  var detectBtn = document.getElementById('detect-btn');
  var detectedFields = document.getElementById('detected-fields');
  var targetSelectorInput = document.getElementById('target-selector');
  var targetHtmlInput = document.getElementById('target-html');
  var manualToggle = document.getElementById('manual-toggle');
  var generateBtn = document.getElementById('generate-btn');
  var outputArea = document.getElementById('output');
  var copyBtn = document.getElementById('copy-btn');
  var errorBanner = document.getElementById('error-banner');
  var extractingIndicator = document.getElementById('extracting-indicator');

  var feedbackPanel = document.getElementById('feedback-panel');
  var feedbackNote = document.getElementById('feedback-note');
  var regenerateBtn = document.getElementById('regenerate-btn');
  var issueCheckboxes = document.querySelectorAll('input[name="fb-issue"]');

  var historyList = document.getElementById('history-list');
  var clearHistoryBtn = document.getElementById('clear-history-btn');
  var HISTORY_KEY = 'sitemap_history';
  var HISTORY_MAX = 50;

  var extractedStyles = null;
  var stylesReady = false;

  function setBtnLoading(btn, loading) {
    btn.disabled = loading;
    btn.classList.toggle('is-loading', loading);
    btn.querySelector('.btn-loading').hidden = !loading;
  }

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.hidden = false;
  }

  function clearError() {
    errorBanner.textContent = '';
    errorBanner.hidden = true;
  }

  function setEditable(editable) {
    targetSelectorInput.readOnly = !editable;
    targetHtmlInput.readOnly = !editable;
  }

  function updateGenerateEnabled() {
    var manualHasContent = targetSelectorInput.value.trim() && targetHtmlInput.value.trim();
    generateBtn.disabled = !(stylesReady || manualHasContent);
  }

  function showFeedbackPanel() {
    feedbackPanel.hidden = false;
    updateRegenerateEnabled();
  }

  function hideFeedbackPanel() {
    feedbackPanel.hidden = true;
    feedbackNote.value = '';
    issueCheckboxes.forEach(function (cb) { cb.checked = false; });
    regenerateBtn.disabled = true;
  }

  function getCheckedIssues() {
    var issues = [];
    issueCheckboxes.forEach(function (cb) {
      if (cb.checked) issues.push(cb.value);
    });
    return issues;
  }

  function updateRegenerateEnabled() {
    regenerateBtn.disabled = getCheckedIssues().length === 0 && !feedbackNote.value.trim();
  }

  async function extractStyles(pageUrl, targetSelector) {
    extractingIndicator.hidden = false;
    stylesReady = false;
    updateGenerateEnabled();
    try {
      var response = await fetch('/extract-styles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageUrl: pageUrl, targetSelector: targetSelector }),
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        throw new Error(data.error || 'Style extraction failed.');
      }
      extractedStyles = data.extractedStyles || null;
      stylesReady = true;
      updateGenerateEnabled();
    } finally {
      extractingIndicator.hidden = true;
    }
  }

  async function detectHero() {
    clearError();
    outputArea.value = '';
    copyBtn.disabled = true;
    hideFeedbackPanel();
    extractedStyles = null;
    stylesReady = false;
    updateGenerateEnabled();

    var pageUrl = pageUrlInput.value.trim();
    if (!pageUrl) {
      showError('Please enter a Customer Website URL.');
      return;
    }

    setBtnLoading(detectBtn, true);
    try {
      var response = await fetch('/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageUrl: pageUrl }),
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        showError('Could not access this site automatically. Enter the CSS selector and element HTML below.');
        detectedFields.hidden = false;
        manualToggle.checked = true;
        setEditable(true);
        updateGenerateEnabled();
        return;
      }

      targetSelectorInput.value = data.selector || '';
      targetHtmlInput.value = data.outerHtml || '';
      detectedFields.hidden = false;
      manualToggle.checked = false;
      setEditable(false);

      try {
        await extractStyles(pageUrl, targetSelectorInput.value.trim());
      } catch (extractErr) {
        showError(extractErr.message || 'Style extraction failed.');
      }
    } catch (err) {
      showError('Could not access this site automatically. Enter the CSS selector and element HTML below.');
      detectedFields.hidden = false;
      manualToggle.checked = true;
      setEditable(true);
      updateGenerateEnabled();
    } finally {
      setBtnLoading(detectBtn, false);
    }
  }

  async function generateSitemap() {
    clearError();
    outputArea.value = '';
    copyBtn.disabled = true;

    var pageUrl = pageUrlInput.value.trim();
    var targetSelector = targetSelectorInput.value.trim();
    var targetHtml = targetHtmlInput.value;

    if (!pageUrl || !targetSelector || !targetHtml.trim()) {
      showError('Detection output is incomplete. Detect hero or fill fields manually.');
      return;
    }

    setBtnLoading(generateBtn, true);
    try {
      var response = await fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pageUrl: pageUrl,
          targetSelector: targetSelector,
          targetHtml: targetHtml,
          extractedStyles: extractedStyles,
          customerName: customerNameInput.value.trim(),
        }),
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        if (response.status === 502 || response.status === 503 || response.status === 504) {
          showError(
            'The AI service timed out \u2014 this can happen with large or complex '
            + 'hero elements. Try again, or select a simpler parent element with '
            + 'fewer nested containers if the problem persists.'
          );
        } else {
          showError(data.error || 'Generation failed (' + response.status + ').');
        }
        return;
      }
      if (!data.sitemap) {
        showError('Sitemap generation returned empty output.');
        return;
      }
      outputArea.value = data.sitemap;
      copyBtn.disabled = false;
      showFeedbackPanel();
      addHistoryEntry(pageUrl, data.sitemap);
    } catch (err) {
      showError(
        err.name === 'TypeError'
          ? 'The AI service timed out \u2014 this can happen with large or complex '
            + 'hero elements. Try again, or select a simpler parent element with '
            + 'fewer nested containers if the problem persists.'
          : 'Network error during sitemap generation. Try again.'
      );
    } finally {
      setBtnLoading(generateBtn, false);
    }
  }

  async function regenerateWithFeedback() {
    clearError();
    var issues = getCheckedIssues();
    var note = feedbackNote.value.trim();
    if (issues.length === 0 && !note) {
      showError('Select an issue or provide feedback text.');
      return;
    }

    setBtnLoading(regenerateBtn, true);
    try {
      var response = await fetch('/regenerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pageUrl: pageUrlInput.value.trim(),
          targetSelector: targetSelectorInput.value.trim(),
          targetHtml: targetHtmlInput.value,
          extractedStyles: extractedStyles,
          previousOutput: outputArea.value,
          issues: issues,
          feedbackNote: feedbackNote.value.trim(),
          customerName: customerNameInput.value.trim(),
        }),
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        if (response.status === 502 || response.status === 503 || response.status === 504) {
          showError(
            'The AI service timed out \u2014 this can happen with large or complex '
            + 'hero elements. Try again, or select a simpler parent element with '
            + 'fewer nested containers if the problem persists.'
          );
        } else {
          showError(data.error || 'Regeneration failed (' + response.status + ').');
        }
        return;
      }
      if (!data.sitemap) {
        showError('Regeneration returned empty output.');
        return;
      }
      outputArea.value = data.sitemap;
      copyBtn.disabled = false;
      hideFeedbackPanel();
      showFeedbackPanel();
      addHistoryEntry(pageUrlInput.value.trim(), data.sitemap);
    } catch (err) {
      showError(
        err.name === 'TypeError'
          ? 'The AI service timed out \u2014 this can happen with large or complex '
            + 'hero elements. Try again, or select a simpler parent element with '
            + 'fewer nested containers if the problem persists.'
          : 'Network error during regeneration. Try again.'
      );
    } finally {
      setBtnLoading(regenerateBtn, false);
    }
  }

  pageUrlInput.addEventListener('blur', function () {
    if (pageUrlInput.value.trim() && !customerNameInput.value.trim()) {
      customerNameInput.value = deriveBrand(pageUrlInput.value.trim());
    }
  });

  detectBtn.addEventListener('click', detectHero);
  generateBtn.addEventListener('click', generateSitemap);
  regenerateBtn.addEventListener('click', regenerateWithFeedback);

  issueCheckboxes.forEach(function (cb) {
    cb.addEventListener('change', updateRegenerateEnabled);
  });
  feedbackNote.addEventListener('input', updateRegenerateEnabled);

  manualToggle.addEventListener('change', function () {
    setEditable(this.checked);
  });
  targetSelectorInput.addEventListener('input', updateGenerateEnabled);
  targetHtmlInput.addEventListener('input', updateGenerateEnabled);

  copyBtn.addEventListener('click', async function () {
    if (!outputArea.value) return;
    try {
      await navigator.clipboard.writeText(outputArea.value);
      var original = copyBtn.textContent;
      copyBtn.textContent = 'Copied!';
      copyBtn.disabled = true;
      setTimeout(function () {
        copyBtn.textContent = original;
        copyBtn.disabled = false;
      }, 1500);
    } catch (e) {
      showError('Could not copy to clipboard.');
    }
  });

  function deriveBrand(url) {
    try {
      var host = new URL(url).hostname.replace(/^www\./, '');
      var name = host.split('.')[0];
      return name.charAt(0).toUpperCase() + name.slice(1);
    } catch (_) {
      return 'Unknown';
    }
  }

  function getHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; }
    catch (_) { return []; }
  }

  function saveHistory(entries) {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_MAX)));
  }

  function addHistoryEntry(url, sitemap) {
    var entries = getHistory();
    entries.unshift({
      id: String(Date.now()),
      brand: deriveBrand(url),
      url: url,
      timestamp: Date.now(),
      sitemap: sitemap,
    });
    saveHistory(entries);
    renderHistory();
  }

  function deleteHistoryEntry(id) {
    saveHistory(getHistory().filter(function (e) { return e.id !== id; }));
    renderHistory();
  }

  function timeAgo(ts) {
    var diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'Yesterday';
    return new Date(ts).toLocaleDateString();
  }

  function renderHistory() {
    var entries = getHistory();
    clearHistoryBtn.hidden = entries.length === 0;

    if (entries.length === 0) {
      historyList.innerHTML = '<p class="history-empty">No sitemaps generated yet.</p>';
      return;
    }

    historyList.innerHTML = entries.map(function (entry) {
      return '<div class="history-card" data-id="' + entry.id + '">'
        + '<div class="history-card-info">'
        + '<span class="history-brand">' + entry.brand + '</span>'
        + '<span class="history-url" title="' + entry.url + '">' + entry.url + '</span>'
        + '</div>'
        + '<span class="history-time">' + timeAgo(entry.timestamp) + '</span>'
        + '<div class="history-actions">'
        + '<button type="button" class="history-btn history-btn--load">Load</button>'
        + '<button type="button" class="history-btn history-btn--delete">Delete</button>'
        + '</div>'
        + '</div>';
    }).join('');
  }

  historyList.addEventListener('click', function (e) {
    var btn = e.target.closest('.history-btn');
    if (!btn) return;
    var card = btn.closest('.history-card');
    var id = card.dataset.id;
    var entries = getHistory();
    var entry = entries.find(function (e) { return e.id === id; });
    if (!entry) return;

    if (btn.classList.contains('history-btn--load')) {
      outputArea.value = entry.sitemap;
      copyBtn.disabled = false;
      showFeedbackPanel();
      outputArea.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else if (btn.classList.contains('history-btn--delete')) {
      deleteHistoryEntry(id);
    }
  });

  clearHistoryBtn.addEventListener('click', function () {
    if (!confirm('Clear all generation history?')) return;
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
  });

  renderHistory();
})();
