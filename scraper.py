import re
import time
import cloudscraper
from bs4 import BeautifulSoup
from rich.console import Console
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

console = Console()
ua = UserAgent()

class AnimePaheScraper:
    def __init__(self):
        self.domains = ['animepahe.com', 'animepahe.org', 'animepahe.pw']
        self.scraper = cloudscraper.create_scraper()
    
    def create_driver(self):
        """Create Chrome driver for JavaScript-heavy sites"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(f'--user-agent={ua.random}')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    
    def search(self, query):
        """Search for anime"""
        for domain in self.domains:
            driver = None
            try:
                driver = self.create_driver()
                driver.get(f"https://{domain}")
                time.sleep(2)
                
                search_selectors = [
                    "input[placeholder*='Search']",
                    "input[type='search']",
                    ".search-input",
                    "input[name='q']",
                    "#search"
                ]
                
                search_input = None
                for selector in search_selectors:
                    try:
                        search_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if search_input:
                            break
                    except:
                        continue
                
                if not search_input:
                    continue
                
                search_input.clear()
                search_input.send_keys(query)
                time.sleep(2)
                
                result_selectors = [
                    ".search-result a",
                    ".dropdown-item a",
                    ".autocomplete-item a",
                    ".ui-menu-item a",
                    ".tt-suggestion a"
                ]
                
                results = []
                for selector in result_selectors:
                    try:
                        result_items = driver.find_elements(By.CSS_SELECTOR, selector)
                        for item in result_items:
                            href = item.get_attribute('href')
                            if href and '/anime/' in href:
                                anime_id = href.split('/anime/')[-1].split('/')[0].split('?')[0]
                                title = item.text.strip()
                                if title and anime_id and len(title) > 2:
                                    results.append({
                                        'id': anime_id,
                                        'title': title,
                                        'thumbnail': '',
                                        'source': 'animepahe'
                                    })
                        if results:
                            break
                    except:
                        continue
                
                if results:
                    seen = set()
                    unique_results = []
                    for r in results:
                        if r['id'] not in seen:
                            seen.add(r['id'])
                            unique_results.append(r)
                    
                    return unique_results[:15]
                    
            except Exception as e:
                console.print(f"[red]Error with domain {domain}: {e}[/red]")
                continue
            finally:
                if driver:
                    driver.quit()
        
        return []
    
    def get_episodes(self, anime_id):
        """Get episodes for an anime"""
        for domain in self.domains:
            driver = None
            try:
                driver = self.create_driver()
                url = f"https://{domain}/anime/{anime_id}"
                driver.get(url)
                
                time.sleep(3)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                episode_selectors = [
                    ".episode-list a",
                    ".episodes a",
                    "a[href*='/play/']",
                    ".episode-item a"
                ]
                
                episodes = []
                episode_elements = []
                
                for selector in episode_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            episode_elements = elements
                            break
                    except:
                        continue
                
                for elem in episode_elements:
                    href = elem.get_attribute('href')
                    if href and '/play/' in href:
                        text = elem.text.strip()
                        ep_num_match = re.search(r'(\d+)', text)
                        episode_num = int(ep_num_match.group(1)) if ep_num_match else len(episodes) + 1
                        session_id = href.split('/play/')[-1].split('/')[-1]
                        
                        episodes.append({
                            'episode': episode_num,
                            'session': session_id,
                            'title': f"Episode {episode_num}"
                        })
                
                if episodes:
                    episodes.sort(key=lambda x: x['episode'])
                    return episodes
                    
            except Exception as e:
                console.print(f"[red]Error getting episodes from {domain}: {e}[/red]")
                continue
            finally:
                if driver:
                    driver.quit()
        
        return []
    
    def get_download_link(self, anime_id, episode_session, quality='1080p', language='DUB'):
        """Get download link for an episode"""
        try:
            pahe_win_url = f"https://pahe.win/{episode_session}"
            response = self.scraper.get(pahe_win_url, allow_redirects=False, timeout=20)
            
            if response.status_code in [301, 302]:
                kwik_url = response.headers.get('Location', '')
                if kwik_url and 'kwik' in kwik_url:
                    return kwik_url
            
            for domain in self.domains:
                try:
                    play_url = f"https://{domain}/play/{anime_id}/{episode_session}"
                    response = self.scraper.get(play_url, timeout=20)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        kwik_links = soup.find_all('a', href=re.compile(r'kwik\.|pahe\.win'))
                        for link in kwik_links:
                            href = link.get('href', '')
                            if 'kwik' in href:
                                return href
                except:
                    continue
                        
        except Exception as e:
            console.print(f"[red]Error getting download link: {e}[/red]")
        
        return None


class AniKaiScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.base_url = "https://anikai.to"
    
    def search(self, query):
        """Search for anime on AniKai"""
        try:
            url = f"{self.base_url}/search?keyword={query}"
            response = self.scraper.get(url, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                anime_items = soup.select('.film-poster, .anime-item')
                for item in anime_items[:20]:
                    link = item.find('a')
                    if link and link.get('href'):
                        anime_id = link['href'].split('/')[-1]
                        title_elem = item.find('h3') or item.find('.title')
                        title = title_elem.text.strip() if title_elem else 'Unknown'
                        results.append({
                            'id': anime_id,
                            'title': title,
                            'thumbnail': '',
                            'source': 'animekai'
                        })
                return results
        except Exception as e:
            console.print(f"[red]AniKai search error: {e}[/red]")
        return []
    
    def get_episodes(self, anime_id):
        """Get episodes from AniKai"""
        try:
            url = f"{self.base_url}/anime/{anime_id}"
            response = self.scraper.get(url, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                episodes = []
                episode_links = soup.select('.episodes-list a, .episode-item a')
                for idx, ep_link in enumerate(episode_links, 1):
                    href = ep_link.get('href', '')
                    if href:
                        episodes.append({
                            'episode': idx,
                            'session': href.split('/')[-1],
                            'title': f"Episode {idx}"
                        })
                return episodes
        except Exception as e:
            console.print(f"[red]AniKai episodes error: {e}[/red]")
        return []
    
    def get_download_link(self, anime_id, episode_session, quality='1080p', language='DUB'):
        """Get download link from AniKai"""
        try:
            episode_url = f"{self.base_url}/watch/{anime_id}/{episode_session}"
            response = self.scraper.get(episode_url, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                mega_links = soup.find_all('a', href=re.compile(r'megaup\.cc|mega\.nz'))
                if mega_links:
                    return mega_links[0].get('href', '')
        except Exception as e:
            console.print(f"[red]AniKai download link error: {e}[/red]")
        return None