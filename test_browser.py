# test_browser.py
# Now we READ data from the page after navigating to it

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    print("Logging in...")
    page.goto("http://127.0.0.1:5000")
    page.get_by_placeholder("Username").fill("admin")
    page.get_by_placeholder("Password").fill("password123")
    page.get_by_role("button", name="Login").click()
    page.wait_for_timeout(1000)

    print("Searching for member 12345...")
    page.get_by_placeholder("Enter Member ID").fill("12345")
    page.get_by_role("button", name="Search Member").click()
    page.wait_for_timeout(1000)

    print("Reading data from page...")

    # Read the full page text
    page_text = page.inner_text("body")
    print("\n--- PAGE TEXT ---")
    print(page_text)
    print("--- END ---")

    # Read specific values
    all_cells = page.locator("td").all()
    for i, cell in enumerate(all_cells):
        text = cell.inner_text().strip()
        if "Savings Balance" in text:
            # The next cell has the actual value
            balance = all_cells[i + 1].inner_text().strip()
            print(f"\n✅ Savings Balance found: {balance}")

    page.wait_for_timeout(3000)
    browser.close()

# from playwright.sync_api import sync_playwright

# with sync_playwright() as p:
#     browser = p.chromium.launch(headless=False)
#     page = browser.new_page(viewport={"width": 1280, "height": 800})

#     print("Step 1: Going to bank...")
#     page.goto("http://127.0.0.1:5000")
#     page.screenshot(path="screenshot_01.png")

#     print("Step 2: Typing username...")
#     page.get_by_placeholder("Username").fill("admin")
#     page.screenshot(path="screenshot_02.png")

#     print("Step 3: Typing password...")
#     page.get_by_placeholder("Password").fill("password123")
#     page.screenshot(path="screenshot_03.png")

#     print("Step 4: Clicking Login...")
#     page.get_by_role("button", name="Login").click()
#     page.wait_for_timeout(1000)
#     page.screenshot(path="screenshot_04.png")

#     print("Step 5: Typing member ID...")
#     page.get_by_placeholder("Enter Member ID").fill("12345")
#     page.screenshot(path="screenshot_05.png")

#     print("Step 6: Clicking Search...")
#     page.get_by_role("button", name="Search Member").click()
#     page.wait_for_timeout(1000)
#     page.screenshot(path="screenshot_06.png")

#     print("Done! Check all screenshot files in your project folder")
#     page.wait_for_timeout(3000)
#     browser.close()