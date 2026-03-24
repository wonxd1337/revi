# proxy_manager.py - Dioptimalkan
import threading
import time
import random
import requests
from queue import Queue
from collections import defaultdict
from config import Config

class ProxyManager:
    def __init__(self):
        self.proxy_list = []
        self.proxy_stats = defaultdict(lambda: {
            'success': 0, 'fail': 0, 'total_time': 0,
            'avg_time': 1.0, 'weight': 1.0, 'last_used': 0
        })
        self.lock = threading.Lock()
        self.running = True
        self.last_refresh = 0
        self.working_proxy_cache = None  # Cache proxy yang sedang aktif
        self.working_proxy_time = 0
        
        # Weight settings
        self.min_weight = 0.1
        self.max_weight = 3.0
        
        # Download initial proxies
        self.download_proxies()
        
        # Mulai thread auto-refresh background
        self.start_auto_refresh()
    
    def download_proxies(self):
        """Download proxy list dari GitHub"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(
                Config.PROXY_URL, 
                headers=headers, 
                timeout=30, 
                verify=False
            )
            
            if response.status_code == 200:
                proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                valid_proxies = [p for p in proxies if '://' in p]
                
                with self.lock:
                    # Reset stats untuk proxy baru
                    old_proxies = set(self.proxy_list)
                    new_proxies = set(valid_proxies)
                    
                    # Hapus proxy yang tidak ada di list baru
                    for proxy in old_proxies - new_proxies:
                        if proxy in self.proxy_stats:
                            del self.proxy_stats[proxy]
                    
                    # Tambah proxy baru
                    self.proxy_list = valid_proxies
                    for proxy in new_proxies - old_proxies:
                        self.proxy_stats[proxy] = {
                            'success': 0, 'fail': 0, 'total_time': 0,
                            'avg_time': 1.0, 'weight': 1.0, 'last_used': 0
                        }
                
                print(f"[+] Proxy Manager: {len(valid_proxies)} proxies loaded")
                return valid_proxies
                
        except Exception as e:
            print(f"[-] Proxy download error: {str(e)[:50]}")
            return self.proxy_list
    
    def refresh_proxies_background(self):
        """Refresh proxy di background tanpa mengganggu proses utama"""
        while self.running:
            time.sleep(Config.PROXY_REFRESH_INTERVAL)
            print("\n[*] Refreshing proxy list in background...")
            self.download_proxies()
            print(f"[+] Proxy refreshed: {len(self.proxy_list)} proxies available")
    
    def start_auto_refresh(self):
        """Mulai thread auto-refresh background"""
        refresh_thread = threading.Thread(target=self.refresh_proxies_background, daemon=True)
        refresh_thread.start()
    
    def update_stats(self, proxy, success, response_time=None):
        """Update statistik proxy"""
        if proxy not in self.proxy_stats:
            return
            
        with self.lock:
            stats = self.proxy_stats[proxy]
            stats['last_used'] = time.time()
            
            if success:
                stats['success'] += 1
                if response_time:
                    total = stats['total_time'] + response_time
                    count = stats['success'] + stats['fail']
                    stats['avg_time'] = total / count if count > 0 else response_time
                    stats['total_time'] = total
            else:
                stats['fail'] += 1
            
            # Hitung ulang bobot
            total_reqs = stats['success'] + stats['fail']
            if total_reqs > 0:
                success_rate = stats['success'] / total_reqs
                speed_score = 1.0 / stats['avg_time'] if stats['avg_time'] > 0 else 1.0
                speed_score = min(speed_score, 2.0)
                
                weight = (success_rate * 0.6 + speed_score * 0.4) * 2
                stats['weight'] = max(self.min_weight, min(self.max_weight, weight))
    
    def get_proxy(self):
        """Dapatkan proxy dengan weighted selection (tanpa testing)"""
        with self.lock:
            if not self.proxy_list:
                return None
            
            # Hitung total weight
            total_weight = sum(
                self.proxy_stats[p]['weight'] 
                for p in self.proxy_list 
                if p in self.proxy_stats
            )
            
            if total_weight == 0:
                # Random selection jika semua weight 0
                proxy = random.choice(self.proxy_list)
                return {"http": proxy, "https": proxy}
            
            # Weighted random
            r = random.uniform(0, total_weight)
            cumulative = 0
            
            for proxy in self.proxy_list:
                if proxy in self.proxy_stats:
                    cumulative += self.proxy_stats[proxy]['weight']
                    if r <= cumulative:
                        return {"http": proxy, "https": proxy}
            
            # Fallback
            proxy = random.choice(self.proxy_list)
            return {"http": proxy, "https": proxy}
    
    def print_stats(self):
        """Tampilkan statistik proxy"""
        print("\n" + "="*60)
        print("PROXY STATISTICS")
        print("="*60)
        
        with self.lock:
            # Count active proxies
            active_proxies = len(self.proxy_list)
            print(f"Total proxies: {active_proxies}")
            
            # Show top 10
            sorted_proxies = sorted(
                [(p, s) for p, s in self.proxy_stats.items() if p in self.proxy_list],
                key=lambda x: x[1]['weight'],
                reverse=True
            )[:10]
            
            if sorted_proxies:
                print("\nTop 10 proxies by performance:")
                for proxy, stats in sorted_proxies:
                    total = stats['success'] + stats['fail']
                    if total > 0:
                        success_rate = (stats['success'] / total) * 100
                        print(f"  {proxy[:60]} | Rate: {success_rate:.0f}% | W: {stats['weight']:.2f}")
    
    def cleanup(self):
        """Bersihkan resources"""
        self.running = False