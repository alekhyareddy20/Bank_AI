# guardrails.py
# Safety rules that run before every action
# Blocks dangerous URLs, risky actions, and hides sensitive data

ALLOWED_DOMAINS = ["127.0.0.1:5000", "localhost:5000"]

BLOCKED_ACTIONS = ["delete", "drop", "truncate"]

RISKY_PAGE_KEYWORDS = ["cannot be undone", "irreversible", "permanent"]

SENSITIVE_FIELDS = ["password", "ssn", "pin", "credit"]


def check_url(url):
    """Block any URL not in the allowed list"""
    if not url:
        return True
    allowed = any(domain in url for domain in ALLOWED_DOMAINS)
    if not allowed:
        raise Exception(f"🚫 BLOCKED: URL not allowed: {url}")
    return True


def check_action(action_type):
    """Block dangerous action types"""
    if action_type.lower() in BLOCKED_ACTIONS:
        raise Exception(f"🚫 BLOCKED: Action not allowed: {action_type}")
    return True


def check_risky_page(page_text):
    """
    Returns True if the page looks dangerous.
    Caller should pause and ask human before continuing.
    """
    for keyword in RISKY_PAGE_KEYWORDS:
        if keyword.lower() in page_text.lower():
            return True, keyword
    return False, None


def redact_sensitive(field_name, value):
    """
    Hide sensitive values in logs.
    'password' -> '****word'
    """
    if not value:
        return value
    for pattern in SENSITIVE_FIELDS:
        if pattern.lower() in field_name.lower():
            if len(value) <= 4:
                return "****"
            return "****" + value[-4:]
    return value


def safe_log_step(element, value):
    """Print a step but hide sensitive values"""
    safe_value = redact_sensitive(element, value)
    print(f"   element: {element} | value: {safe_value}")


# ── TEST IT ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing guardrails...\n")

    # Test 1: allowed URL
    try:
        check_url("http://127.0.0.1:5000/search")
        print("✅ Allowed URL passed")
    except Exception as e:
        print(e)

    # Test 2: blocked URL
    try:
        check_url("http://google.com")
        print("❌ Should have been blocked!")
    except Exception as e:
        print(f"✅ Blocked URL caught: {e}")

    # Test 3: risky page
    risky, keyword = check_risky_page("WARNING: This action cannot be undone")
    print(f"✅ Risky page detected: {risky} | keyword: {keyword}")

    # Test 4: sensitive data redaction
    print(f"✅ Password redacted: {redact_sensitive('password', 'password123')}")
    print(f"✅ Normal field shown: {redact_sensitive('member_id', '12345')}")