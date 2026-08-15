# # test_browser.py
# # This script opens a real Chrome browser, goes to the bank, and takes a screenshot
# # Run it with: python test_browser.py

# from playwright.sync_api import sync_playwright

# with sync_playwright() as p:
#     # Launch a real Chrome browser (headless=False means you can SEE it)
#     browser = p.chromium.launch(headless=False)
#     page = browser.new_page(viewport={"width": 1280, "height": 800})

#     print("Opening browser...")
#     page.goto("http://127.0.0.1:5000")

#     print("Taking screenshot...")
#     page.screenshot(path="screenshot_01.png")

#     print("Done! Check screenshot_01.png in your project folder")
    
#     # Wait 3 seconds so you can see the browser before it closes
#     page.wait_for_timeout(3000)
#     browser.close()

# test_browser.py
# Now we click and type — logging into the bank automatically

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    print("Step 1: Going to bank...")
    page.goto("http://127.0.0.1:5000")
    page.screenshot(path="screenshot_01.png")

    print("Step 2: Typing username...")
    page.get_by_placeholder("Username").fill("admin")
    page.screenshot(path="screenshot_02.png")

    print("Step 3: Typing password...")
    page.get_by_placeholder("Password").fill("password123")
    page.screenshot(path="screenshot_03.png")

    print("Step 4: Clicking Login...")
    page.get_by_role("button", name="Login").click()
    page.wait_for_timeout(1000)
    page.screenshot(path="screenshot_04.png")

    print("Step 5: Typing member ID...")
    page.get_by_placeholder("Enter Member ID").fill("12345")
    page.screenshot(path="screenshot_05.png")

    print("Step 6: Clicking Search...")
    page.get_by_role("button", name="Search Member").click()
    page.wait_for_timeout(1000)
    page.screenshot(path="screenshot_06.png")

    print("Done! Check all screenshot files in your project folder")
    page.wait_for_timeout(3000)
    browser.close()