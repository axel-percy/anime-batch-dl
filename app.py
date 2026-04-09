import os
import json
import threading
import uuid
import re
import time
import asyncio
import requests
import httpx
from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from fake_useragent import UserAgent
import cloudscraper
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
app.secret_key = 'anime-batch-downloader-secret-key-2024'
app.config['DOWNLOAD_FOLDER'] = os.path.expanduser('~/Downloads/Anime')
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

CONFIG_FILE = 'config.json'
download_jobs = {}

# Initialize Rich console for terminal output
console = Console()

# Initialize fake user agent
ua = UserAgent()

def load_config():
    default_config = {
        'quality': '1080p',
        'language': 'DUB',
        'download_folder': os.path.expanduser('~/Downloads/Anime'),
        'source': 'animepahe',
        'external_downloader': False,
        'max_threads': 5
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def create_driver():
    """Create Chrome driver - uses installed Chrome"""
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

def search_anime_pahe(query):
    """Search anime using AnimePahe's JavaScript search"""
    domains = ['animepahe.com', 'animepahe.org', 'animepahe.pw']
    
    for domain in domains:
        driver = None
        try:
            driver = create_driver()
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
                                    'source': 'animepahe',
                                    'domain': domain
                                })
                    if results:
                        break
                except:
                    continue
            
            if results:
                # Remove duplicates
                seen = set()
                unique_results = []
                for r in results:
                    if r['id'] not in seen:
                        seen.add(r['id'])
                        unique_results.append(r)
                
                console.print(f"[green]Found {len(unique_results)} results on {domain}[/green]")
                return unique_results[:15]
                
        except Exception as e:
            console.print(f"[red]Error with domain {domain}: {e}[/red]")
            continue
        finally:
            if driver:
                driver.quit()
    
    return []

def search_anime_kai(query):
    """Search anime using AniKai"""
    try:
        scraper = cloudscraper.create_scraper()
        url = f"https://anikai.to/search?keyword={query}"
        response = scraper.get(url, timeout=20)
        
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

def get_episodes_pahe(anime_id):
    """Get episodes from AnimePahe using Selenium"""
    domains = ['animepahe.com', 'animepahe.org', 'animepahe.pw']
    
    for domain in domains:
        driver = None
        try:
            driver = create_driver()
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
                console.print(f"[green]Found {len(episodes)} episodes on {domain}[/green]")
                return episodes
                
        except Exception as e:
            console.print(f"[red]Error getting episodes from {domain}: {e}[/red]")
            continue
        finally:
            if driver:
                driver.quit()
    
    return []

def get_download_link_pahe(anime_id, episode_session, quality='1080p', language='DUB'):
    """Get the final download link by following redirects"""
    try:
        pahe_win_url = f"https://pahe.win/{episode_session}"
        console.print(f"[yellow]Getting download link: {pahe_win_url}[/yellow]")
        
        scraper = cloudscraper.create_scraper()
        response = scraper.get(pahe_win_url, allow_redirects=False, timeout=20)
        
        if response.status_code in [301, 302]:
            kwik_url = response.headers.get('Location', '')
            if kwik_url and 'kwik' in kwik_url:
                console.print(f"[green]Found kwik link: {kwik_url}[/green]")
                return kwik_url
        
        # Fallback: try to get from the play page directly
        domains = ['animepahe.com', 'animepahe.org', 'animepahe.pw']
        for domain in domains:
            try:
                play_url = f"https://{domain}/play/{anime_id}/{episode_session}"
                response = scraper.get(play_url, timeout=20)
                
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

def get_episodes_kai(anime_id):
    """Get episodes from AniKai"""
    try:
        scraper = cloudscraper.create_scraper()
        url = f"https://anikai.to/anime/{anime_id}"
        response = scraper.get(url, timeout=20)
        
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

def get_download_link_kai(anime_id, episode_session, quality='1080p', language='DUB'):
    """Get download link from AniKai"""
    try:
        scraper = cloudscraper.create_scraper()
        episode_url = f"https://anikai.to/watch/{anime_id}/{episode_session}"
        response = scraper.get(episode_url, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            mega_links = soup.find_all('a', href=re.compile(r'megaup\.cc|mega\.nz'))
            if mega_links:
                return mega_links[0].get('href', '')
    except Exception as e:
        console.print(f"[red]AniKai download link error: {e}[/red]")
    return None

def download_file(url, filepath, max_retries=3):
    """Download a file with retries and progress display"""
    for attempt in range(max_retries):
        try:
            console.print(f"[cyan]Downloading: {os.path.basename(filepath)}[/cyan]")
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, stream=True, timeout=120)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeRemainingColumn(),
                ) as progress:
                    task = progress.add_task("Downloading", total=total_size)
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, advance=len(chunk))
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                console.print(f"[green]Successfully downloaded: {os.path.basename(filepath)}[/green]")
                return True
                
        except Exception as e:
            console.print(f"[red]Download attempt {attempt + 1} failed: {e}[/red]")
            if attempt == max_retries - 1:
                return False
            time.sleep(3)
    
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/api/search')
def api_search():
    try:
        query = request.args.get('q', '')
        source = request.args.get('source', load_config()['source'])
        
        console.print(f"[blue]Searching for: {query} using source: {source}[/blue]")
        
        if not query or len(query) < 2:
            return jsonify([])
        
        results = []
        
        if source == 'animepahe':
            results = search_anime_pahe(query)
        elif source == 'animekai':
            results = search_anime_kai(query)
        
        return jsonify(results)
    
    except Exception as e:
        console.print(f"[red]API search error: {str(e)}[/red]")
        return jsonify([])

@app.route('/details/<anime_id>')
def details_page(anime_id):
    try:
        source = request.args.get('source', load_config()['source'])
        
        details = {
            'title': 'Anime',
            'description': 'Fetching details...',
            'air_date': 'Unknown',
            'genres': [],
            'thumbnail': '',
            'source': source
        }
        
        return render_template('details.html', anime=details, anime_id=anime_id)
    
    except Exception as e:
        console.print(f"[red]Details page error: {str(e)}[/red]")
        return render_template('details.html', anime={
            'title': 'Error',
            'description': f'Error: {str(e)}',
            'air_date': 'Unknown',
            'genres': ['Error'],
            'thumbnail': ''
        }, anime_id=anime_id)

@app.route('/select/<anime_id>')
def select_page(anime_id):
    try:
        source = request.args.get('source', load_config()['source'])
        
        episodes = []
        if source == 'animepahe':
            episodes = get_episodes_pahe(anime_id)
        elif source == 'animekai':
            episodes = get_episodes_kai(anime_id)
        
        return render_template('select.html', anime={'title': 'Select Episodes', 'thumbnail': ''}, 
                             anime_id=anime_id, episodes=episodes)
    
    except Exception as e:
        console.print(f"[red]Select page error: {str(e)}[/red]")
        return render_template('select.html', anime={'title': 'Error', 'thumbnail': ''}, 
                             anime_id=anime_id, episodes=[])

@app.route('/api/episodes')
def api_episodes():
    try:
        anime_id = request.args.get('anime_id')
        source = request.args.get('source', load_config()['source'])
        
        episodes = []
        if source == 'animepahe':
            episodes = get_episodes_pahe(anime_id)
        elif source == 'animekai':
            episodes = get_episodes_kai(anime_id)
        
        return jsonify(episodes)
    
    except Exception as e:
        console.print(f"[red]API episodes error: {str(e)}[/red]")
        return jsonify([])

@app.route('/api/download', methods=['POST'])
def api_download():
    try:
        data = request.json
        anime_id = data['anime_id']
        anime_title = data.get('anime_title', 'anime')
        episode_range = data['episode_range']
        config = load_config()
        source = config['source']
        quality = config['quality']
        language = config['language']
        
        job_id = str(uuid.uuid4())
        
        # Parse episode range
        episodes_to_download = []
        if '-' in episode_range:
            start, end = map(int, episode_range.split('-'))
            episodes_to_download = list(range(start, end+1))
        elif ',' in episode_range:
            episodes_to_download = [int(x.strip()) for x in episode_range.split(',')]
        else:
            episodes_to_download = [int(episode_range)]
        
        # Get all episodes
        all_episodes = []
        if source == 'animepahe':
            all_episodes = get_episodes_pahe(anime_id)
        elif source == 'animekai':
            all_episodes = get_episodes_kai(anime_id)
        
        # Filter episodes to download
        episodes_to_get = [ep for ep in all_episodes if ep['episode'] in episodes_to_download]
        
        # Create anime-specific folder
        safe_title = sanitize_filename(anime_title)
        anime_folder = os.path.join(config['download_folder'], safe_title)
        os.makedirs(anime_folder, exist_ok=True)
        
        download_jobs[job_id] = {
            'status': 'downloading',
            'progress': 0,
            'total': len(episodes_to_get),
            'completed': 0,
            'episodes': episodes_to_get,
            'zip_path': None,
            'anime_folder': anime_folder,
            'anime_title': anime_title
        }
        
        def download_task():
            try:
                temp_dir = os.path.join(anime_folder, f'temp_{job_id}')
                os.makedirs(temp_dir, exist_ok=True)
                
                downloaded_files = []
                total = len(episodes_to_get)
                
                for idx, episode in enumerate(episodes_to_get):
                    # Get download link
                    download_url = None
                    if source == 'animepahe':
                        download_url = get_download_link_pahe(anime_id, episode['session'], quality, language)
                        
                        if not download_url and language == 'DUB':
                            console.print(f"[yellow]DUB not found for episode {episode['episode']}, trying SUB[/yellow]")
                            download_url = get_download_link_pahe(anime_id, episode['session'], quality, 'SUB')
                    
                    elif source == 'animekai':
                        download_url = get_download_link_kai(anime_id, episode['session'], quality, language)
                        
                        if not download_url and language == 'DUB':
                            console.print(f"[yellow]DUB not found for episode {episode['episode']}, trying SUB[/yellow]")
                            download_url = get_download_link_kai(anime_id, episode['session'], quality, 'SUB')
                    
                    if download_url:
                        filename = f"Episode_{episode['episode']:03d}.mp4"
                        filepath = os.path.join(temp_dir, filename)
                        
                        if download_file(download_url, filepath):
                            downloaded_files.append(filepath)
                    else:
                        console.print(f"[red]No download link for episode {episode['episode']}[/red]")
                    
                    download_jobs[job_id]['completed'] = idx + 1
                    download_jobs[job_id]['progress'] = ((idx + 1) / total) * 100 if total > 0 else 0
                
                if downloaded_files:
                    zip_filename = f"{safe_title}_Episodes_{episode_range.replace(',', '_')}.zip"
                    zip_path = os.path.join(anime_folder, zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for filepath in downloaded_files:
                            zipf.write(filepath, os.path.basename(filepath))
                    
                    for filepath in downloaded_files:
                        try:
                            os.remove(filepath)
                        except:
                            pass
                    try:
                        os.rmdir(temp_dir)
                    except:
                        pass
                    
                    download_jobs[job_id]['status'] = 'completed'
                    download_jobs[job_id]['zip_path'] = zip_path
                    console.print(f"[green]Download complete! ZIP saved to: {zip_path}[/green]")
                else:
                    download_jobs[job_id]['status'] = 'failed'
                    console.print(f"[red]Download failed for all episodes[/red]")
            
            except Exception as e:
                console.print(f"[red]Download task error: {e}[/red]")
                download_jobs[job_id]['status'] = 'failed'
        
        thread = threading.Thread(target=download_task)
        thread.start()
        
        return jsonify({'job_id': job_id})
    
    except Exception as e:
        console.print(f"[red]API download error: {str(e)}[/red]")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/status/<job_id>')
def download_status(job_id):
    if job_id in download_jobs:
        return jsonify(download_jobs[job_id])
    return jsonify({'status': 'not_found'})

@app.route('/api/download/zip/<job_id>')
def download_zip(job_id):
    if job_id in download_jobs and download_jobs[job_id].get('zip_path'):
        zip_path = download_jobs[job_id]['zip_path']
        if os.path.exists(zip_path):
            return send_file(zip_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/source')
def source_page():
    return render_template('source.html')

@app.route('/api/source', methods=['POST'])
def api_set_source():
    try:
        source = request.json['source']
        config = load_config()
        config['source'] = source
        save_config(config)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/source/current')
def api_current_source():
    try:
        config = load_config()
        return jsonify({'source': config['source']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/settings')
def settings_page():
    config = load_config()
    return render_template('settings.html', config=config)

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    try:
        config = load_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def api_settings():
    try:
        config = load_config()
        config['quality'] = request.json.get('quality', config['quality'])
        config['language'] = request.json.get('language', config['language'])
        config['download_folder'] = request.json.get('download_folder', config['download_folder'])
        config['external_downloader'] = request.json.get('external_downloader', config['external_downloader'])
        config['max_threads'] = int(request.json.get('max_threads', config.get('max_threads', 5)))
        save_config(config)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/downloads')
def downloads_page():
    return render_template('downloads.html')

if __name__ == '__main__':
    console.print("[bold green]Anime Batch Downloader Started![/bold green]")
    console.print("[cyan]Visit http://localhost:5000 to use the application[/cyan]")
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)