"""Poster/list layout and account preference at desktop and touch phone widths."""
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options=webdriver.ChromeOptions()
for arg in ('--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1000','--user-data-dir=/data/smoke-browser-profile'): options.add_argument(arg)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
script=r"""
  const original=window.fetch;
  window.posterLookups=0;
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async(value)=>{window.copiedPosterMagnet=value;}}});
  window.fetch=(url,options)=>{
    if(String(url).includes('/torrent/search-poster') && options?.method==='POST') window.posterLookups++;
    if(String(url).includes('/torrent/search?')){
      const rows=[
        {Title:'Dune.2024.1080p.WEB-DL',SearchResultKey:'dune-1080',Category:[{ID:2000}],Seeders:80,Size:2147483648,InfoHash:'1'.repeat(40),Tracker:'Fixture',Details:'https://example.test/dune',parsed:{title:'Dune',year:2024,resolution:'1080p',quality:'WEB-DL'}},
        {Title:'Dune.2024.2160p.BluRay',SearchResultKey:'dune-4k',Category:[{ID:2000}],Seeders:20,Size:4294967296,InfoHash:'2'.repeat(40),Tracker:'Fixture',Details:'https://example.test/dune',parsed:{title:'Dune',year:2024,resolution:'2160p',quality:'BluRay'}},
        {Title:'Dune Software 2024',SearchResultKey:'software',Category:[{ID:4000}],Seeders:5,InfoHash:'3'.repeat(40),Tracker:'Fixture',parsed:{title:'Dune Software',year:2024}},
        {Title:'Dune 2024 '+ 'LongRelease'.repeat(20),SearchResultKey:'long',Category:[{ID:2000}],Seeders:1,InfoHash:'4'.repeat(40),Tracker:'Fixture',parsed:{title:'Dune',year:2024}}
      ];
      return Promise.resolve(new Response(rows.map(row=>JSON.stringify(row)).join('\n')+'\n'));
    }
    return original(url,options);
  };
"""

def toggle(browser,mode):
    label='Thumbnail view' if mode=='grid' else 'List view'
    button=WebDriverWait(browser,20,ignored_exceptions=(StaleElementReferenceException,)).until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'[aria-label="Search result view"] button[aria-label="{label}"]')))
    WebDriverWait(browser,20,ignored_exceptions=(StaleElementReferenceException,)).until(lambda d:d.execute_script("const b=arguments[0],r=b.getBoundingClientRect();return b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));",button))
    button.click()
    WebDriverWait(browser,20,ignored_exceptions=(StaleElementReferenceException,)).until(lambda d:d.find_element(By.CSS_SELECTOR,f'[aria-label="Search result view"] button[aria-label="{label}"]').get_attribute('aria-pressed')=='true' and d.find_element(By.CSS_SELECTOR,f'[aria-label="Search result view"] button[aria-label="{label}"]').is_enabled())

with webdriver.Chrome(options=options) as browser:
    wait=WebDriverWait(browser,30,ignored_exceptions=(StaleElementReferenceException,))
    browser.get('http://127.0.0.1/home?tab=search')
    field=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Search torrent here"]')))
    assert browser.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="List view"]').get_attribute('aria-pressed')=='true'
    browser.execute_script(script)
    field.send_keys('Dune',Keys.ENTER)
    wait.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'button[title="Copy magnet link"]'))==4)
    assert browser.execute_script('return window.posterLookups')==0,'List view must not request movie posters'
    toggle(browser,'grid')
    wait.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'[data-search-poster-card] img'))>=2)
    wait.until(lambda d:d.execute_script('return [...document.querySelectorAll("[data-search-poster-card] img")].every(image=>image.complete&&image.naturalWidth>0)'))
    assert browser.execute_script('return window.posterLookups')==1,'Different releases must share one metadata lookup'
    assert 'Showing recent results while refreshing' not in browser.find_element(By.TAG_NAME,'body').text
    first=browser.find_elements(By.CSS_SELECTOR,'[data-search-poster-card]')[0]
    first.find_element(By.CSS_SELECTOR,'button[aria-label="Search result actions"]').click()
    wait.until(EC.element_to_be_clickable((By.XPATH,'//*[@role="menuitem" and normalize-space(.)="Copy magnet"]'))).click()
    wait.until(lambda d:d.execute_script('return window.copiedPosterMagnet') is not None)
    assert browser.execute_script('return window.copiedPosterMagnet').startswith('magnet:?xt=urn:btih:')
    wait.until(lambda d:not any(element.is_displayed() for element in d.find_elements(By.CSS_SELECTOR,'[role="status"]')))
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR,'[role="menu"]')))
    time.sleep(.25)
    browser.save_screenshot('/data/search-posters-desktop.png')
    for width, height in ((320,568),(375,667),(390,844),(414,896),(768,1024)):
        browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':True})
        browser.execute_cdp_cmd('Emulation.setTouchEmulationEnabled',{'enabled':True})
        time.sleep(.25)
        assert browser.execute_script('return document.documentElement.scrollWidth <= innerWidth+1'),width
        cards=browser.find_elements(By.CSS_SELECTOR,'[data-search-poster-card]')
        for card in cards[:2]:
            assert browser.execute_script('return arguments[0].scrollWidth <= arguments[0].clientWidth+1',card),width
            button=card.find_element(By.CSS_SELECTOR,'button[aria-label="Search result actions"]')
            assert button.is_displayed() and button.rect['height'] >= (44 if width < 768 else 28),width
        control=browser.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"]')
        assert browser.execute_script('const t=arguments[0],s=t.parentElement.querySelector("input").parentElement,a=t.getBoundingClientRect(),b=s.getBoundingClientRect(),c=t.querySelector("button").getBoundingClientRect();return Math.abs(a.top-b.top)<1&&a.height===b.height&&c.height===b.height&&c.width===c.height&&t.previousElementSibling.getAttribute("role")==="separator"',control),('aligned secondary controls',width)

        assert browser.execute_script('const t=arguments[0],a=t.previousElementSibling,b=t.parentElement.previousElementSibling,r=document.documentElement,was=r.classList.contains("dark");let match=true;for(const dark of [false,true]){r.classList.toggle("dark",dark);match=match&&getComputedStyle(a).borderLeftColor===getComputedStyle(b).borderLeftColor;}r.classList.toggle("dark",was);return match;',control),('matching separators in both themes',width)
        grid=browser.find_element(By.CSS_SELECTOR,'[data-search-poster-grid]')
        browser.execute_script('arguments[0].scrollTop=arguments[0].scrollHeight',grid)
        time.sleep(.15)
        last=browser.find_elements(By.CSS_SELECTOR,'[data-search-poster-card]')[-1].find_element(By.CSS_SELECTOR,'button[aria-label="Search result actions"]')
        last.click()
        download=wait.until(EC.visibility_of_element_located((By.XPATH,'//*[@role="menuitem" and normalize-space(.)="Download"]')))
        wait.until(lambda d:download.rect['height']>=43.99)
        assert browser.execute_script('const r=arguments[0].getBoundingClientRect();return arguments[0].contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))',download),('last grid action',width,height)
        browser.find_element(By.TAG_NAME,'body').send_keys(Keys.ESCAPE)
        browser.execute_script('arguments[0].scrollTop=0',grid)
        time.sleep(.1)
        if width in (320,390):browser.save_screenshot(f'/data/search-posters-phone-{width}.png')
        toggle(browser,'list')
        wait.until(lambda d:not d.find_elements(By.CSS_SELECTOR,'[data-search-poster-grid]'))
        assert browser.execute_script('return document.documentElement.scrollWidth <= innerWidth+1'),('list',width)
        listing=browser.find_element(By.CSS_SELECTOR,'[data-search-list]')
        browser.execute_script('arguments[0].scrollTop=arguments[0].scrollHeight',listing)
        time.sleep(.1)
        buttons=[button for button in listing.find_elements(By.CSS_SELECTOR,'button[title="Download"]') if button.is_displayed()]
        assert buttons
        assert browser.execute_script('const r=arguments[0].getBoundingClientRect();return arguments[0].contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))',buttons[-1]),('last list action',width,height)
        toggle(browser,'grid')
        wait.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,'[data-search-poster-card]')))
    browser.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride',{})
    browser.execute_cdp_cmd('Emulation.setTouchEmulationEnabled',{'enabled':False})
    # Both modes must survive a real refresh using the account endpoint.
    browser.refresh()
    wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="Thumbnail view"]').get_attribute('aria-pressed')=='true')
    print('PASS: real posters, release deduplication, no list-view lookups, copy magnet, silent refresh, desktop and phone/tablet layouts (320/375/390/414/768)')

# A fresh browser profile has no stored layout preference; the server supplies it.
other=webdriver.ChromeOptions()
for arg in ('--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=390,844','--user-data-dir=/data/poster-second-browser'):other.add_argument(arg)
with webdriver.Chrome(options=other) as browser:
    wait=WebDriverWait(browser,30,ignored_exceptions=(StaleElementReferenceException,))
    browser.get('http://127.0.0.1/account/signin')
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys('single-container-smoke@example.test')
    browser.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys('Smoke-Test-Password-123!')
    browser.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click()
    wait.until(EC.url_contains('/home'))
    browser.get('http://127.0.0.1/home?tab=search')
    wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="Thumbnail view"]').get_attribute('aria-pressed')=='true')
    toggle(browser,'list')
    browser.refresh()
    wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="List view"]').get_attribute('aria-pressed')=='true')
    browser.execute_cdp_cmd('Network.enable',{})
    browser.execute_cdp_cmd('Network.setBlockedURLs',{'urls':['*://*/api/auth/preferences']})
    browser.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="Thumbnail view"]').click()
    wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="List view"]').get_attribute('aria-pressed')=='true' and d.find_element(By.CSS_SELECTOR,'[aria-label="Search result view"] button[aria-label="List view"]').is_enabled())
    browser.execute_cdp_cmd('Network.setBlockedURLs',{'urls':[]})
    print('PASS: failed preference save restores the previous view')
    print('PASS: fresh-browser account sync; grid and list preferences both persist after reload')
