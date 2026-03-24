# proxy_manager.py - Fix attribute name
import threading
import time
import random
import requests
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
        
        self.min_weight = 0.1
        self.max_weight = 3.0
        
        # Download initial proxies
        self.download_proxies()
        self.start_auto_refresh()
    
    def download_proxies(self):
        """Download proxy dari multiple sources"""
        all_proxies = []
        
        # Cek apakah menggunakan PROXY_URLS (multiple) atau PROXY_URL (single)
        if hasattr(Config, 'PROXY_URLS'):
            proxy_sources = Config.PROXY_URLS
        elif hasattr(Config, 'PROXY_URL'):
            proxy_sources = [Config.PROXY_URL]
        else:
            # Fallback default
            proxy_sources = [
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
                "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            ]
        
        for proxy_url in proxy_sources:
            try:
                print(f"[*] Downloading proxies from: {proxy_url.split('/')[-1][:50]}")
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(proxy_url, headers=headers, timeout=30, verify=False)
                
                if response.status_code == 200:
                    proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                    
                    # Filter hanya HTTP/HTTPS proxy
                    http_proxies = []
                    for p in proxies:
                        if '://' in p:
                            # Already has protocol
                            if 'http' in p.lower() or 'https' in p.lower():
                                http_proxies.append(p)
                        else:
                            # Add http:// prefix
                            http_proxies.append(f"http://{p}")
                    
                    all_proxies.extend(http_proxies)
                    print(f"    ✓ Got {len(http_proxies)} HTTP proxies")
                else:
                    print(f"    ✗ Failed: Status {response.status_code}")
                    
            except Exception as e:
                print(f"    ✗ Error: {str(e)[:50]}")
                continue
        
        # Tambahkan manual proxy jika ada
        if hasattr(Config, 'MANUAL_PROXIES') and Config.MANUAL_PROXIES:
            print(f"[*] Adding {len(Config.MANUAL_PROXIES)} manual proxies")
            all_proxies.extend(Config.MANUAL_PROXIES)
        
        # Remove duplicates
        all_proxies = list(set(all_proxies))
        
        # Filter hanya HTTP/HTTPS (pastikan tidak ada SOCKS)
        filtered_proxies = []
        for proxy in all_proxies:
            if 'socks' not in proxy.lower():
                filtered_proxies.append(proxy)
        
        all_proxies = filtered_proxies
        
        with self.lock:
            # Reset stats untuk proxy baru
            old_proxies = set(self.proxy_list)
            new_proxies = set(all_proxies)
            
            # Hapus proxy yang tidak ada di list baru
            for proxy in old_proxies - new_proxies:
                if proxy in self.proxy_stats:
                    del self.proxy_stats[proxy]
            
            # Update proxy list
            self.proxy_list = all_proxies
            
            # Tambah stats untuk proxy baru
            for proxy in new_proxies - old_proxies:
                self.proxy_stats[proxy] = {
                    'success': 0, 'fail': 0, 'total_time': 0,
                    'avg_time': 1.0, 'weight': 1.0, 'last_used': 0
                }
        
        print(f"\n[+] Total HTTP/HTTPS proxies: {len(all_proxies)}")
        return all_proxies
    
    def refresh_proxies_background(self):
        """Refresh proxy di background"""
        while self.running:
            time.sleep(Config.PROXY_REFRESH_INTERVAL)
            print("\n[*] Refreshing proxy list...")
            self.download_proxies()
            print(f"[+] Proxy count: {len(self.proxy_list)}")
    
    def start_auto_refresh(self):
        """Mulai thread auto-refresh"""
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
        """Dapatkan proxy dengan weighted selection"""
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
            print(f"Total proxies: {len(self.proxy_list)}")
            
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
                        print(f"  {proxy[:60]} | S: {stats['success']} | F: {stats['fail']} | Rate: {success_rate:.0f}%")
    
    def cleanup(self):
        """Bersihkan resources"""
        self.running = False
