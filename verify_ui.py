import os
from playwright.sync_api import sync_playwright

def verify_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Mock pywebview
        page.add_init_script("""
            window.pywebview = {
                api: {
                    get_config: async () => ({
                        hotkey: 'right alt',
                        start_with_windows: false,
                        stt: { api_key: 'test-stt-key' },
                        llm: { api_key: 'test-llm-key' },
                        glossary: []
                    }),
                    get_version: async () => '1.0.0'
                }
            };
        """)

        # Get absolute path to index.html
        file_path = f"file://{os.path.abspath('src/my_typeless/web/index.html')}"
        page.goto(file_path)

        # Manually trigger pywebviewready event since we mocked pywebview
        page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")

        # Wait for initialization (hotkeyBtn is visible on the first page)
        page.wait_for_selector('#hotkeyBtn')

        # Go to STT page
        page.click('a[data-page="stt"]')
        page.wait_for_selector('#page-stt.active')
        page.wait_for_selector('#sttKey', state='visible')

        # Find the STT toggle button
        stt_toggle = page.locator('#page-stt button[onclick*="togglePasswordVisibility"]')

        # Verify initial state
        assert stt_toggle.get_attribute('aria-label') == 'Show password', "Initial aria-label should be 'Show password'"
        assert stt_toggle.get_attribute('title') == 'Show password', "Initial title should be 'Show password'"

        # Click to show
        stt_toggle.click()

        # Verify state after click
        assert stt_toggle.get_attribute('aria-label') == 'Hide password', "After click aria-label should be 'Hide password'"
        assert stt_toggle.get_attribute('title') == 'Hide password', "After click title should be 'Hide password'"

        # Take screenshot of shown state
        page.screenshot(path="stt_password_shown.png")

        # Click to hide again
        stt_toggle.click()

        # Verify state after second click
        assert stt_toggle.get_attribute('aria-label') == 'Show password', "After second click aria-label should be 'Show password'"
        assert stt_toggle.get_attribute('title') == 'Show password', "After second click title should be 'Show password'"


        # Go to LLM page
        page.click('a[data-page="llm"]')
        page.wait_for_selector('#page-llm.active')
        page.wait_for_selector('#llmKey', state='visible')

        # Find the LLM toggle button
        llm_toggle = page.locator('#page-llm button[onclick*="togglePasswordVisibility"]')

        # Verify initial state
        assert llm_toggle.get_attribute('aria-label') == 'Show password', "LLM Initial aria-label should be 'Show password'"
        assert llm_toggle.get_attribute('title') == 'Show password', "LLM Initial title should be 'Show password'"

        # Click to show
        llm_toggle.click()

        # Verify state after click
        assert llm_toggle.get_attribute('aria-label') == 'Hide password', "LLM After click aria-label should be 'Hide password'"
        assert llm_toggle.get_attribute('title') == 'Hide password', "LLM After click title should be 'Hide password'"

        # Take screenshot of shown state
        page.screenshot(path="llm_password_shown.png")

        print("UI Verification Passed!")
        browser.close()

if __name__ == "__main__":
    verify_ui()
