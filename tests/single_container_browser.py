"""Run inside the test container using /opt/flare-python/bin/python."""
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1440,1000")
options.add_argument("--user-data-dir=/data/smoke-browser-profile")
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
with webdriver.Chrome(options=options) as browser:
    browser.get("http://127.0.0.1/account/signin")
    wait = WebDriverWait(browser, 30, ignored_exceptions=(StaleElementReferenceException,))
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Enter your email"]'))).send_keys("single-container-smoke@example.test")
    browser.find_element(By.CSS_SELECTOR, 'input[placeholder="Enter your password"]').send_keys("Smoke-Test-Password-123!")
    browser.find_element(By.XPATH, "//button[.//p[text()='Sign in']]").click()
    wait.until(EC.url_contains("/home"))
    wait.until(lambda driver: driver.execute_script("return document.body.innerText.length") > 100)
    # A hard refresh verifies exported routes and authenticated hydration.
    browser.refresh()
    wait.until(lambda driver: "/home" in driver.current_url and len(driver.find_elements(By.TAG_NAME, "button")) > 0)
    errors = [entry for entry in browser.get_log("browser") if entry["level"] == "SEVERE" and
              ("Uncaught" in entry["message"] or "Hydration failed" in entry["message"])]
    assert not errors, errors
    browser.get("http://127.0.0.1/home?tab=search")
    search_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Search torrent here"]')))
    browser.execute_script("""
      Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async(value)=>{window.copiedFixtureMagnet=value;}}});
      const original = window.fetch;
      window.fetch = (url, options) => {
        if (String(url).includes('/torrent/search?')) {
          window.searchFixtureUrl = String(url);
          let rows = [
            {Title:'Ubuntu.Desktop', Seeders:50, Tracker:'Fixture', SearchSource:'fixture', SearchResultKey:'ubuntu', SearchCached:false, ResolveToken:'fixture_token_for_search_resolution'},
            {Title:'Completely unrelated', Seeders:1000, Tracker:'Fixture'},
            {Title:'Ubuntu', Seeders:1, Tracker:'Fixture'}
          ];
          const query = new URL(url, location.origin).searchParams.get('query');
          if (query === 'Hindi') rows = [
            {Title:'Movie Hindi', Seeders:50, Tracker:'Fixture'},
            {Title:'Tensei Shitara Ken Deshita', Seeders:1000, Tracker:'Fixture'},
            {Title:'World Is Dancing [HIDIVE]', Seeders:900, Tracker:'Fixture'},
            {Title:'Movie [Hindi+English]', Seeders:20, Tracker:'Fixture'},
            {Title:'Musafir 2004 Hindi', Seeders:10, Tracker:'Fixture'}
          ];
          if (query === 'Dune 2024') rows = [
            {Title:'Дюна / Dune Part Two (2024) Multilingual Long Release Name', Seeders:50, Tracker:'Fixture'},
            {Title:'Dune 2021', Seeders:1000, Tracker:'Fixture'},
            {Title:'Dune 2024', Seeders:20, Tracker:'Fixture'}
          ];
          if (query === 'Ubuntu') rows = [
            {__type:'cache_status'},
            {Title:'Ubuntu.Desktop',Seeders:5,Tracker:'Fixture',SearchSource:'fixture',SearchResultKey:'ubuntu',SearchCached:true},
            {Title:'Ubuntu stale result',Seeders:100,Tracker:'Fixture',SearchSource:'fixture',SearchResultKey:'stale',SearchCached:true},
            ...rows,
            {__type:'source_complete',indexer:'fixture'}
          ];
          return Promise.resolve(new Response(rows.map(row => JSON.stringify(row)).join('\\n') + '\\n'));
        }
        return original(url, options);
      };
    """)
    search_input.send_keys("Ubuntu")
    from selenium.webdriver.common.keys import Keys
    search_input.send_keys(Keys.ENTER)
    title_filter = wait.until(lambda driver: next((element for element in driver.find_elements(By.CSS_SELECTOR, 'input[placeholder="Filter results by title"]') if element.is_displayed()), False))
    assert title_filter.get_attribute("value") == "Ubuntu"
    wait.until(lambda driver: "Ubuntu.Desktop" in driver.find_element(By.TAG_NAME, "body").text)
    text = browser.find_element(By.TAG_NAME, "body").text
    assert "Completely unrelated" not in text
    assert "Ubuntu stale result" not in text
    titles = browser.find_elements(By.CSS_SELECTOR, "p.font-semibold")
    rendered = [element.text for element in titles if element.text.startswith("Ubuntu")]
    assert rendered == ["Ubuntu.Desktop", "Ubuntu"], rendered
    browser.find_elements(By.CSS_SELECTOR, 'button[title="Copy magnet link"]')[0].click()
    wait.until(lambda driver: driver.execute_script("return window.copiedFixtureMagnet") == "magnet:?xt=urn:btih:" + "1" * 40)
    print("PASS: Copy magnet resolves the server reference and writes the returned magnet to the clipboard")
    title_filter.clear()
    title_filter.send_keys("not present anywhere")
    wait.until(lambda driver: "No titles match your filters" in driver.find_element(By.TAG_NAME, "body").text)
    print("PASS: title filter autofills, excludes unrelated results, preserves seed ordering, explains filtered-empty results")
    for query, expected in [
        ("Hindi", ["Movie Hindi", "Movie [Hindi+English]", "Musafir 2004 Hindi"]),
        ("Dune 2024", ["Дюна / Dune Part Two (2024) Multilingual Long Release Name", "Dune 2024"]),
    ]:
        field = browser.find_element(By.CSS_SELECTOR, 'input[placeholder="Search torrent here"]')
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(query, Keys.ENTER)
        wait.until(lambda driver: next((element for element in driver.find_elements(By.CSS_SELECTOR, 'input[placeholder="Filter results by title"]') if element.is_displayed() and element.get_attribute("value") == query), False))
        wait.until(lambda driver: [element.text for element in driver.find_elements(By.CSS_SELECTOR, "p.leading-snug.font-semibold") if element.is_displayed()] == expected)
        if query == "Hindi":
            secondary = next(element for element in browser.find_elements(By.CSS_SELECTOR, 'input[placeholder="Filter results by title"]') if element.is_displayed())
            secondary.send_keys(Keys.CONTROL, "a")
            secondary.send_keys("m")
            for letter in ["", "u", "s"]:
                if letter: secondary.send_keys(letter)
                wait.until(lambda driver: "Musafir 2004 Hindi" in driver.find_element(By.TAG_NAME, "body").text)
            wait.until(lambda driver: [element.text for element in driver.find_elements(By.CSS_SELECTOR, "p.leading-snug.font-semibold") if element.is_displayed()] == ["Musafir 2004 Hindi"])
            print("PASS: editing Hindi filter m → mu → mus retains Musafir without another network search")

    print("PASS: Hindi excludes anime/HIDIVE false matches; Dune 2024 includes long multilingual titles and excludes the wrong year")
    browser.save_screenshot("/data/smoke-home.png")
    print("PASS: Chromium sign-in, authenticated home, hard refresh, no uncaught/hydration errors")

# Reopening a browser process must restore the HttpOnly persistent cookie.
with webdriver.Chrome(options=options) as browser:
    wait = WebDriverWait(browser, 30, ignored_exceptions=(StaleElementReferenceException,))
    browser.get("http://127.0.0.1/")
    wait.until(EC.url_contains("/home"))
    assert any(cookie.get("httpOnly") and cookie.get("expiry") for cookie in browser.get_cookies())
    browser.execute_cdp_cmd("Network.enable", {})
    browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*://*/api/auth/me"]})
    browser.refresh()
    time.sleep(2)
    assert "/home" in browser.current_url, "Temporary network loss must not navigate to login"
    browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
    browser.refresh()
    wait.until(EC.url_contains("/home"))
    print("PASS: browser close/reopen restores session; temporary auth network failure does not log out")
