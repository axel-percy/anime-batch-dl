import os
import zipfile
import cloudscraper
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time

class AnimeDownloader:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
    
    def download_file(self, url, filepath, max_retries=3):
        """Download a single file with retries"""
        for attempt in range(max_retries):
            try:
                response = self.scraper.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
            except Exception as e:
                print(f"Download attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(2)
        return False
    
    def download_batch(self, episodes, anime_title, episode_range, download_folder):
        """Download multiple episodes and create ZIP"""
        temp_dir = os.path.join(download_folder, f'temp_{int(time.time())}')
        os.makedirs(temp_dir, exist_ok=True)
        
        downloaded_files = []
        
        for episode in episodes:
            file_path = os.path.join(temp_dir, f"Episode_{episode['episode']:03d}.mp4")
            
            # Simulate download for now - in production, get real download URL
            # This is where you'd integrate with the actual download links
            with open(file_path, 'w') as f:
                f.write(f"Sample content for episode {episode['episode']}")
            
            downloaded_files.append(file_path)
        
        if downloaded_files:
            safe_title = re.sub(r'[^\w\-_\. ]', '_', anime_title)
            zip_filename = f"{safe_title}_Episodes_{episode_range.replace(',', '_')}.zip"
            zip_path = os.path.join(download_folder, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for filepath in downloaded_files:
                    zipf.write(filepath, os.path.basename(filepath))
            
            # Cleanup
            for filepath in downloaded_files:
                try:
                    os.remove(filepath)
                except:
                    pass
            try:
                os.rmdir(temp_dir)
            except:
                pass
            
            return zip_path
        
        return None