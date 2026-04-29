import os
import re
import json
import time
import logging
from urllib.parse import urljoin, urlparse

import requests
import cssutils
from bs4 import BeautifulSoup, Comment
from flask import Flask, request, jsonify, render_template

from dotenv import load_dotenv

load_dotenv()

from auth import ConnectedAppAuth
from llm_provider import ConnectAPILLM

cssutils.log.setLevel(logging.CRITICAL)

authenticator = ConnectedAppAuth(creds_file="creds.json")
llm = ConnectAPILLM(
    authenticator=authenticator,
    provider="OpenAI",
    model="sfdc_ai__DefaultOpenAIGPT4OmniMini",
    temperature=0.5,
)

app = Flask(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

HERO_KEYWORDS = re.compile(r"(hero|banner|jumbotron|masthead|splash|jumbo)", re.I)

DEFAULT_STYLES = {
    "banner": {"backgroundColor": "#333333", "fontFamily": "Arial, Helvetica, sans-serif"},
    "header": {"fontSize": "32px", "fontWeight": "600", "color": "#DDDDDD"},
    "subheader": {"fontSize": "20px", "fontWeight": "400", "color": "#DDDDDD"},
    "cta": {
        "backgroundColor": "#097fb3",
        "borderRadius": "20px",
        "padding": "10px 20px",
        "color": "#DDDDDD",
    },
}

LLM_PROMPT = """You are an expert Salesforce Personalization (Interaction Studio) developer.
Your job is to generate a ready-to-use sitemap JavaScript file.

You will receive four inputs:
1. PAGE_URL  - The customer's webpage URL
2. TARGET_HTML - The cleaned HTML of the hero element to personalize
3. TARGET_SELECTOR - The CSS selector for that element
4. EXTRACTED_STYLES - Fallback CSS values extracted from the customer's page

=== TASK ===
Output a single JavaScript file. It has two parts:

PART 1 — FIXED BOILERPLATE (output verbatim, substituting only CUSTOMER_NAME
and TARGET_SELECTOR as noted):

//SimpleSitemap
SalesforceInteractions.setLoggingLevel(100);
SalesforceInteractions.updateConsents({{
    purpose: SalesforceInteractions.ConsentPurpose.Tracking,
    provider: "Example Consent Manager",
    status: SalesforceInteractions.ConsentStatus.OptIn
}});

document.addEventListener(
    SalesforceInteractions.CustomEvents.OnSetAnonymousId, () => {{
        SalesforceInteractions.sendEvent({{
            user: {{ attributes: {{ eventType: 'identity' }} }}
        }})
    }}
);

document.querySelector('html').style.fontSize = '14px';
SalesforceInteractions.Personalization.Config.initialize({{
    additionalTransformers: [{{
        name: "CUSTOMER_NAME_Homepage_Hero_Banner",
        transformerType: "Handlebars",
        lastModifiedDate: new Date().getTime() - (1000 * 60 * 5),
        substitutionDefinitions: {{
            BackgroundImageUrl: {{ defaultValue: '[attributes].[BackgroundImageUrl]' }},
            Header: {{ defaultValue: '[attributes].[Header]' }},
            Subheader: {{ defaultValue: '[attributes].[Subheader]' }},
            CallToActionUrl: {{ defaultValue: '[attributes].[CallToActionUrl]' }},
            CallToActionText: {{ defaultValue: '[attributes].[CallToActionText]' }}
        }},
        transformerTypeDetails: {{
            html: `GENERATED_TRANSFORMER_HTML`
        }}
    }}]
}});

/* ===================== SITEMAP ===================== */
console.log("PSP: Hello world from Data Cloud");
SalesforceInteractions.setLoggingLevel(100);
SalesforceInteractions.updateConsents({{
    purpose: SalesforceInteractions.ConsentPurpose.Tracking,
    provider: "Example Consent Manager",
    status: SalesforceInteractions.ConsentStatus.OptIn
}});

document.addEventListener(
    SalesforceInteractions.CustomEvents.OnSetAnonymousId, () => {{
        SalesforceInteractions.sendEvent({{
            user: {{ attributes: {{ eventType: 'identity', isAnonymous: 1 }} }}
        }})
    }}
);

function getMetaTag(tagName){{
    var metaTags = document.getElementsByTagName("META");
    var metaTagContent = "";
    for (var i = 0; i < metaTags.length; i++) {{
        if(metaTags[i].name == tagName){{
            metaTagContent = metaTags[i].getAttribute('content');
        }}
    }}
    return metaTagContent;
}}

SalesforceInteractions.init().then(() => {{
    const config = {{
        global: {{ onActionEvent: (event) => {{ return event; }} }},
        pageTypes: [{{
            name: "Homepage",
            isMatch: () => window.location.pathname === '/',
            interaction: {{ name: "Homepage", eventType: "browse", pageType: "Homepage" }},
            onActionEvent: (event) => {{
                if (event.interaction.name == "Homepage") {{
                    SalesforceInteractions.Personalization
                        .fetch(["CUSTOMER_NAME_Homepage_Hero_Banner"])
                        .then(r => renderBannerHeader(r.personalizations[0].attributes))
                }}
                return event;
            }},
            contentZones: [{{ name: "Homepage | Hero", selector: "TARGET_SELECTOR" }}]
        }}],
        pageTypeDefault: {{ name: "Default" }}
    }};
    SalesforceInteractions.initSitemap(config);
}});

^^^ END OF FIXED BOILERPLATE ^^^

The ONLY things you change in the boilerplate above are:
- Replace every CUSTOMER_NAME with the customer name derived from PAGE_URL
  (e.g. https://www.ahead.com → Ahead)
- Replace TARGET_SELECTOR with the actual CSS selector from the input
- Replace GENERATED_TRANSFORMER_HTML with the HTML you generate in Part 2

Do NOT add, remove, reorder, or modify any other line in the boilerplate.

=== PART 2 — GENERATE THE TRANSFORMER HTML ===

Adapt TARGET_HTML into a personalization transformer. Your job is to preserve the
customer's DOM structure, nesting, and CSS class names while replacing content
with the 5 Handlebars subVar variables listed below.

The output should look like a trimmed version of TARGET_HTML with subVars slotted
into the semantically correct positions — NOT a generic template.

Rules:

1. PRESERVE THE CUSTOMER'S STRUCTURE.
   Keep the tag hierarchy, nesting, wrapper divs, and CSS class names from
   TARGET_HTML. The transformer replaces the original element on the live page,
   so the customer's existing stylesheets will style these class names.
   Do NOT flatten the hierarchy. Do NOT invent generic class names.

2. SLOT THE 5 MANDATORY subVar VARIABLES (four curly braces each):
   - {{{{subVar 'BackgroundImageUrl'}}}} — place as an inline style
     background: url('{{{{subVar 'BackgroundImageUrl'}}}}') no-repeat center center / cover;
     on the element where the hero's background image belongs (follow the
     customer's existing pattern from TARGET_HTML — it may not be the
     outermost wrapper).
   - {{{{subVar 'Header'}}}} — text content of the main heading element
   - {{{{subVar 'Subheader'}}}} — text content of the subtitle/description element
   - {{{{subVar 'CallToActionUrl'}}}} — href of a CTA link
   - {{{{subVar 'CallToActionText'}}}} — text of that CTA link
   If TARGET_HTML lacks a CTA link, add one inside the content area styled
   to match using EXTRACTED_STYLES.cta values as inline styles.
   All five variables MUST appear — they are the personalization fields.

3. STRIP REMAINING NOISE.
   Remove any leftover video, audio, modal, script, or interactive elements
   the pre-processor may have missed. Remove empty wrapper divs that serve
   no structural purpose. Keep overlay divs, layout containers, and
   decorative elements (like <hr> separators).

4. INLINE STYLES — use sparingly.
   Keep inline styles that already exist in TARGET_HTML. Add inline styles
   only where essential (background image, overlay opacity). Do NOT add a
   <style> block. The customer's class names will inherit styles from the
   live page's stylesheets.
   If you must add fallback styles (e.g. for an added CTA), use
   EXTRACTED_STYLES values as inline style attributes.

Output only valid HTML. No <style> block, no JavaScript, no markdown fences.

=== INPUTS ===
- PAGE_URL: {page_url}
- TARGET_SELECTOR: {target_selector}
- TARGET_HTML:
{target_html}
- EXTRACTED_STYLES:
{extracted_styles}

=== OUTPUT ===
Output ONLY the complete JavaScript file (Part 1 boilerplate with Part 2
transformer HTML inserted). No markdown fences, no commentary."""


ISSUE_INSTRUCTIONS = {
    "background_image": (
        "BACKGROUND IMAGE: Ensure {{subVar 'BackgroundImageUrl'}} is placed as an "
        "inline style background: url(...) on the appropriate element, following "
        "the customer's pattern from TARGET_HTML."
    ),
    "text_content": (
        "HEADER / SUBHEADER: Ensure the heading uses {{subVar 'Header'}} and the "
        "subtitle uses {{subVar 'Subheader'}}. Preserve the customer's class names "
        "on these elements. If styling is missing, use EXTRACTED_STYLES header and "
        "subheader values as inline style attributes."
    ),
    "cta_missing": (
        "CTA BUTTON: Ensure a visible CTA link is present: "
        "<a href=\"{{subVar 'CallToActionUrl'}}\">{{subVar 'CallToActionText'}}</a>. "
        "If adding a new CTA, style it using EXTRACTED_STYLES cta values as inline styles."
    ),
    "layout_wrong": (
        "LAYOUT: The transformer HTML structure should more closely mirror the tag "
        "hierarchy and nesting in TARGET_HTML. Preserve the customer's wrapper divs, "
        "containers, and layout structure."
    ),
}

CORRECTION_PROMPT = """You are revising a Salesforce Personalization sitemap that you previously generated.
The user has flagged specific issues with the transformer HTML inside transformerTypeDetails.

RULES:
- Fix ONLY the transformer HTML (the content inside transformerTypeDetails.html backticks).
- Do NOT change any other part of the JavaScript — the boilerplate must remain identical.
- All five subVar Handlebars variables remain MANDATORY in the transformer HTML.
- Preserve the customer's DOM structure and class names from TARGET_HTML.
- Do NOT add a <style> block. Use inline styles only where TARGET_HTML already has
  them or where essential (e.g. background image).
- Output the COMPLETE revised JavaScript file. No markdown fences, no commentary.

=== ISSUES TO FIX ===
{issue_list}

{user_note}

=== ORIGINAL INPUTS ===
- PAGE_URL: {page_url}
- TARGET_SELECTOR: {target_selector}
- TARGET_HTML:
{target_html}
- EXTRACTED_STYLES:
{extracted_styles}

=== YOUR PREVIOUS OUTPUT ===
{previous_output}

=== OUTPUT ===
Output the COMPLETE revised JavaScript file with the transformer HTML fixed.
No markdown fences, no commentary."""


def fetch_page(url):
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"}, timeout=25, allow_redirects=True)
    resp.raise_for_status()
    return resp.text, resp.url


def best_selector(tag):
    if tag.get("id"):
        return f"#{tag['id']}"
    classes = [c for c in tag.get("class", []) if re.match(r"^[-_a-zA-Z0-9]+$", c)]
    if classes:
        return f"{tag.name}.{'.'.join(classes[:3])}"
    return tag.name


def detect_hero(soup):
    candidates = soup.body.find_all(["section", "div"], limit=80) if soup.body else []

    for el in candidates:
        style = el.get("style", "")
        if re.search(r"background(-image)?\s*:", style, re.I):
            return el

    for el in candidates:
        cls = " ".join(el.get("class", []))
        if HERO_KEYWORDS.search(cls):
            return el

    for el in candidates:
        if el.find(["h1", "h2"]) and el.find("a"):
            return el

    first_section = soup.find("section")
    if first_section:
        return first_section

    return None


def parse_inline_style(style_str):
    out = {}
    if not style_str:
        return out
    for decl in style_str.split(";"):
        decl = decl.strip()
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        out[prop.strip().lower()] = val.strip()
    return out


def collect_hero_classes(hero):
    class_set = set()
    for c in hero.get("class", []):
        class_set.add(c)
    for child in hero.find_all(True, recursive=False):
        for c in child.get("class", []):
            class_set.add(c)
    return class_set


def selector_matches(selector_text, hero_classes):
    sel = selector_text.lower()
    for cls in hero_classes:
        if f".{cls.lower()}" in sel:
            return True
    return False


def infer_bucket(selector_text, declarations):
    s = selector_text.lower()
    if " a" in s or s.endswith("a") or ".cta" in s or ".btn" in s:
        return "cta"
    if "h1" in s or "title" in s or "header" in s:
        return "header"
    if "h2" in s or "subheader" in s or "subtitle" in s or " p" in s:
        return "subheader"
    return "banner"


NOISE_TAGS = {
    "script", "noscript", "iframe", "link", "meta",
    "video", "audio", "source", "track",
    "button", "picture",
}


def sanitize_html(raw_html):
    """Strip interactive/media noise from TARGET_HTML while preserving structural DOM."""
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in list(soup.find_all(NOISE_TAGS)):
        tag.decompose()

    for comment in list(soup.find_all(string=lambda t: isinstance(t, Comment))):
        comment.extract()

    for tag in list(soup.find_all(True)):
        if not tag.parent:
            continue
        classes = " ".join(tag.get("class", []))
        if "modal" in classes.lower() or tag.get("aria-hidden") == "true":
            tag.decompose()
            continue
        for attr in list(tag.attrs):
            if attr.startswith("data-"):
                del tag[attr]

    return str(soup).strip()


def _usable(val):
    """Reject CSS variable references, currentColor, and empty values."""
    if not val:
        return False
    v = val.strip().lower()
    return not v.startswith("var(") and v != "currentcolor"


def pick_style_values(base, declarations, bucket):
    if bucket == "banner":
        if "background-color" in declarations and _usable(declarations["background-color"]):
            base["banner"]["backgroundColor"] = declarations["background-color"]
        elif "background" in declarations and _usable(declarations["background"]):
            base["banner"]["backgroundColor"] = declarations["background"]
        if "font-family" in declarations and _usable(declarations["font-family"]):
            base["banner"]["fontFamily"] = declarations["font-family"]
    elif bucket == "header":
        if "color" in declarations and _usable(declarations["color"]):
            base["header"]["color"] = declarations["color"]
        if "font-size" in declarations and _usable(declarations["font-size"]):
            base["header"]["fontSize"] = declarations["font-size"]
        if "font-weight" in declarations and _usable(declarations["font-weight"]):
            base["header"]["fontWeight"] = declarations["font-weight"]
    elif bucket == "subheader":
        if "color" in declarations and _usable(declarations["color"]):
            base["subheader"]["color"] = declarations["color"]
        if "font-size" in declarations and _usable(declarations["font-size"]):
            base["subheader"]["fontSize"] = declarations["font-size"]
        if "font-weight" in declarations and _usable(declarations["font-weight"]):
            base["subheader"]["fontWeight"] = declarations["font-weight"]
    elif bucket == "cta":
        if "background-color" in declarations and _usable(declarations["background-color"]):
            base["cta"]["backgroundColor"] = declarations["background-color"]
        elif "background" in declarations and _usable(declarations["background"]):
            base["cta"]["backgroundColor"] = declarations["background"]
        if "border-radius" in declarations and _usable(declarations["border-radius"]):
            base["cta"]["borderRadius"] = declarations["border-radius"]
        if "padding" in declarations and _usable(declarations["padding"]):
            base["cta"]["padding"] = declarations["padding"]
        if "color" in declarations and _usable(declarations["color"]):
            base["cta"]["color"] = declarations["color"]


def extract_matching_rules(css_text, hero_classes):
    try:
        sheet = cssutils.parseString(css_text, validate=False)
    except Exception:
        return []
    out = []
    for rule in sheet:
        if rule.type != rule.STYLE_RULE:
            continue
        sel = rule.selectorText
        if not selector_matches(sel, hero_classes):
            continue
        declarations = {}
        for prop in rule.style:
            declarations[prop.name.lower()] = prop.value
        out.append((sel, declarations))
    return out


def derive_customer_name(page_url):
    hostname = urlparse(page_url).hostname or ""
    hostname = re.sub(r"^www\.", "", hostname, flags=re.I)
    root = hostname.split(".")[0] or "Customer"
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", root).strip()
    if not normalized:
        return "Customer"
    return "".join(w.capitalize() for w in normalized.split())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/detect", methods=["POST"])
def detect():
    data = request.get_json(silent=True) or {}
    page_url = (data.get("pageUrl") or "").strip()
    if not page_url:
        return jsonify(error="pageUrl is required."), 400

    try:
        html, final_url = fetch_page(page_url)
    except Exception as e:
        return jsonify(error=f"Failed to fetch page: {e}"), 502

    soup = BeautifulSoup(html, "html.parser")
    hero = detect_hero(soup)

    if not hero:
        return jsonify(error="Could not detect a hero element on this page."), 404

    return jsonify(
        pageUrl=final_url,
        selector=best_selector(hero),
        outerHtml=str(hero),
    )


@app.route("/extract-styles", methods=["POST"])
def extract_styles():
    data = request.get_json(silent=True) or {}
    page_url = (data.get("pageUrl") or "").strip()
    target_selector = (data.get("targetSelector") or "").strip()

    if not page_url:
        return jsonify(error="pageUrl is required."), 400
    if not target_selector:
        return jsonify(error="targetSelector is required."), 400

    try:
        html, final_url = fetch_page(page_url)
    except Exception as e:
        return jsonify(error=f"Failed to fetch page: {e}"), 502

    soup = BeautifulSoup(html, "html.parser")

    if target_selector.startswith("#"):
        hero = soup.find(id=target_selector[1:])
    elif target_selector.startswith("."):
        parts = target_selector[1:].split(".")
        hero = soup.find(class_=lambda c: c and all(p in c.split() for p in parts))
    else:
        hero = soup.select_one(target_selector)

    if not hero:
        hero = detect_hero(soup)

    extracted = json.loads(json.dumps(DEFAULT_STYLES))

    if hero:
        hero_classes = collect_hero_classes(hero)

        inline = parse_inline_style(hero.get("style", ""))
        pick_style_values(extracted, inline, "banner")
        for child in hero.find_all(True, recursive=False):
            child_inline = parse_inline_style(child.get("style", ""))
            tag_name = child.name or ""
            bucket = infer_bucket(tag_name, child_inline)
            pick_style_values(extracted, child_inline, bucket)

        for style_tag in soup.find_all("style"):
            css_text = style_tag.string or ""
            for sel, declarations in extract_matching_rules(css_text, hero_classes):
                pick_style_values(extracted, declarations, infer_bucket(sel, declarations))

        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if not href:
                continue
            try:
                abs_url = urljoin(final_url, href)
                resp = requests.get(abs_url, headers={"User-Agent": BROWSER_UA}, timeout=15)
                if resp.status_code == 200:
                    for sel, declarations in extract_matching_rules(resp.text, hero_classes):
                        pick_style_values(extracted, declarations, infer_bucket(sel, declarations))
            except Exception:
                continue

    return jsonify(extractedStyles=extracted)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    page_url = (data.get("pageUrl") or "").strip()
    target_html = data.get("targetHtml") or ""
    target_selector = (data.get("targetSelector") or "").strip()
    extracted_styles = data.get("extractedStyles") or DEFAULT_STYLES

    if not page_url:
        return jsonify(error="pageUrl is required."), 400
    if not target_html.strip():
        return jsonify(error="targetHtml is required."), 400
    if not target_selector:
        return jsonify(error="targetSelector is required."), 400

    try:
        clean_html = sanitize_html(target_html)
    except Exception:
        clean_html = target_html

    prompt = LLM_PROMPT.format(
        page_url=page_url,
        target_html=clean_html,
        target_selector=target_selector,
        extracted_styles=json.dumps(extracted_styles, indent=2),
    )

    last_err = None
    result = None
    for attempt in range(3):
        try:
            result = llm.invoke(prompt)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    if result is None:
        return jsonify(error=_llm_error_message(last_err)), 502

    text = result if isinstance(result, str) else str(result)
    text = strip_markdown_fences(text)

    return jsonify(sitemap=text)


def _llm_error_message(err):
    msg = str(err) if err else ""
    if "503" in msg or "timeout" in msg.lower():
        return (
            "The AI service timed out \u2014 this can happen with large or complex "
            "hero elements. Try again, or select a simpler parent element with "
            "fewer nested containers if the problem persists."
        )
    return f"LLM generation failed: {msg}"


def strip_markdown_fences(text):
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else len(text)
        text = text[first_nl + 1:]
        last_fence = text.rfind("```")
        if last_fence != -1:
            text = text[:last_fence]
        text = text.strip()
    return text


@app.route("/regenerate", methods=["POST"])
def regenerate():
    data = request.get_json(silent=True) or {}
    page_url = (data.get("pageUrl") or "").strip()
    target_html = data.get("targetHtml") or ""
    target_selector = (data.get("targetSelector") or "").strip()
    extracted_styles = data.get("extractedStyles") or DEFAULT_STYLES
    previous_output = data.get("previousOutput") or ""
    issues = data.get("issues") or []
    feedback_note = (data.get("feedbackNote") or "").strip()

    if not previous_output.strip():
        return jsonify(error="previousOutput is required."), 400

    issue_lines = []
    for key in issues:
        instruction = ISSUE_INSTRUCTIONS.get(key)
        if instruction:
            issue_lines.append(f"- {instruction}")

    if not issue_lines and not feedback_note:
        return jsonify(error="Select an issue or provide feedback text."), 400

    user_note_section = ""
    if feedback_note:
        user_note_section = f"=== ADDITIONAL USER FEEDBACK ===\n{feedback_note}"

    try:
        clean_html = sanitize_html(target_html)
    except Exception:
        clean_html = target_html

    prompt = CORRECTION_PROMPT.format(
        issue_list="\n".join(issue_lines),
        user_note=user_note_section,
        page_url=page_url,
        target_selector=target_selector,
        target_html=clean_html,
        extracted_styles=json.dumps(extracted_styles, indent=2),
        previous_output=previous_output,
    )

    last_err = None
    result = None
    for attempt in range(3):
        try:
            result = llm.invoke(prompt)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    if result is None:
        return jsonify(error=_llm_error_message(last_err)), 502

    text = result if isinstance(result, str) else str(result)
    text = strip_markdown_fences(text)

    return jsonify(sitemap=text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
