# scanner.py - Rombakan total
import requests
import re
import time
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent
from urllib3.exceptions import InsecureRequestWarning
from config import Config

# Nonaktifkan warning SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class MovableTypeScanner:
    def __init__(self, proxy_manager, cache_manager):
        self.ua = UserAgent()
        self.proxy_manager = proxy_manager
        self.cache_manager = cache_manager
        self.found_urls = set()
        self.lock = threading.Lock()
        
        # Headers
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "close"
        }
        
        # Session untuk requests
        self.session = requests.Session()
        
        # Output files (di direktori utama)
        self.output_files = Config.OUTPUT_FILES
    
    def get_working_proxy(self):
        """Cari proxy yang benar-benar aktif dengan menguji ke target"""
        max_attempts = 50  # Coba maksimal 50 proxy
        
        for attempt in range(max_attempts):
            proxy_dict = self.proxy_manager.get_proxy()
            if not proxy_dict:
                # Jika tidak ada proxy, refresh dulu
                print("[!] No proxies available, refreshing...")
                self.proxy_manager.download_proxies()
                time.sleep(2)
                continue
            
            proxy = list(proxy_dict.values())[0]
            
            # Uji proxy dengan koneksi sederhana
            try:
                test_url = "https://httpbin.org/ip"
                response = self.session.get(
                    test_url,
                    proxies=proxy_dict,
                    timeout=15,
                    verify=False
                )
                
                if response.status_code == 200:
                    # Proxy berfungsi
                    self.proxy_manager.update_stats(proxy, True, 1.0)
                    print(f"[✓] Found working proxy: {proxy[:50]}")
                    return proxy_dict
                else:
                    self.proxy_manager.update_stats(proxy, False)
                    
            except Exception as e:
                self.proxy_manager.update_stats(proxy, False)
                continue
        
        print("[!] No working proxy found after multiple attempts!")
        return None
    
    def reverse_ip_with_proxy(self, ip, source='tntcode'):
        """Reverse IP menggunakan proxy dengan retry hingga berhasil"""
        max_retries = 10  # Maksimal 10 kali percobaan dengan proxy berbeda
        
        for retry in range(max_retries):
            # Dapatkan proxy aktif
            proxy_dict = self.get_working_proxy()
            if not proxy_dict:
                print(f"[!] No working proxy for attempt {retry+1}/{max_retries}")
                time.sleep(3)
                continue
            
            proxy_used = list(proxy_dict.values())[0]
            start_time = time.time()
            
            try:
                if source == 'tntcode':
                    url = f"https://domains.tntcode.com/ip/{ip}"
                else:
                    url = f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
                
                headers = self.headers.copy()
                headers["User-Agent"] = self.ua.random
                
                response = self.session.get(
                    url, headers=headers, proxies=proxy_dict,
                    timeout=Config.TIMEOUT_REVERSE, verify=False
                )
                
                response_time = time.time() - start_time
                self.proxy_manager.update_stats(proxy_used, True, response_time)
                
                if response.status_code == 200:
                    if source == 'tntcode':
                        domains = re.findall(r'<a href="/domain/(.+?)"', response.text)
                        return domains
                    else:
                        if "error" not in response.text.lower():
                            domains = response.text.strip().split('\n')
                            return [d.strip() for d in domains if d.strip()]
                        return []
                else:
                    print(f"[-] {source} returned status {response.status_code}")
                    
            except Exception as e:
                self.proxy_manager.update_stats(proxy_used, False)
                print(f"[-] {source} attempt {retry+1} failed: {str(e)[:50]}")
                time.sleep(2)
                continue
        
        print(f"[!] Failed to reverse IP {ip} after {max_retries} attempts")
        return []
    
    def reverse_ip_both_sources(self, ip):
        """Reverse IP dari kedua sumber dengan proxy aktif"""
        print(f"\n[+] Reverse IP: {ip}")
        
        # Cek cache terlebih dahulu
        cache_key_tnt = f"tnt_{ip}"
        cache_key_ht = f"ht_{ip}"
        
        cached_tnt = self.cache_manager.get_reverse_cache(cache_key_tnt)
        cached_ht = self.cache_manager.get_reverse_cache(cache_key_ht)
        
        # Jika keduanya ada di cache, langsung gunakan
        if cached_tnt is not None and cached_ht is not None:
            print(f"[↺] Using cached results for {ip}")
            domains_tnt = cached_tnt
            domains_ht = cached_ht
        else:
            # Proses reverse IP dengan proxy
            print("[*] Fetching domains from TNTCODE...")
            domains_tnt = self.reverse_ip_with_proxy(ip, 'tntcode')
            if domains_tnt:
                self.cache_manager.save_reverse_cache(cache_key_tnt, domains_tnt, 'tntcode')
                print(f"    TNTCODE: {len(domains_tnt)} domains")
            
            print("[*] Fetching domains from HACKERTARGET...")
            domains_ht = self.reverse_ip_with_proxy(ip, 'hackertarget')
            if domains_ht:
                self.cache_manager.save_reverse_cache(cache_key_ht, domains_ht, 'hackertarget')
                print(f"    HACKERTARGET: {len(domains_ht)} domains")
        
        # Gabungkan domain
        all_domains = []
        domain_set = set()
        
        for domain in domains_tnt:
            if domain not in domain_set:
                domain_set.add(domain)
                all_domains.append(domain)
        
        for domain in domains_ht:
            if domain not in domain_set:
                domain_set.add(domain)
                all_domains.append(domain)
        
        print(f"[+] Total domains found: {len(all_domains)} (TNT: {len(domains_tnt)}, HT: {len(domains_ht)})")
        
        return all_domains
    
    def check_rsd_xml(self, domain):
        """Cek rsd.xml tanpa proxy (langsung)"""
        paths = ['/rsd.xml', '/blog/rsd.xml']
        
        for protocol in ['http', 'https']:
            for path in paths:
                try:
                    url = f"{protocol}://{domain}{path}"
                    headers = self.headers.copy()
                    headers["User-Agent"] = self.ua.random
                    
                    response = self.session.get(
                        url, headers=headers, 
                        timeout=Config.TIMEOUT_SCAN, 
                        verify=False,
                        allow_redirects=False
                    )
                    
                    if response.status_code == 200 and 'rsd' in response.text.lower():
                        return response.text, url
                except:
                    continue
        
        return None, None
    
    def extract_mt_info(self, rsd_content):
        """Ekstrak info Movable Type"""
        info = {'engine': None, 'api_link': None, 'version': None}
        
        engine_match = re.search(r'<engineName>(.+?)</engineName>', rsd_content, re.IGNORECASE)
        if engine_match:
            info['engine'] = engine_match.group(1)
            if 'movable type' in info['engine'].lower():
                version_match = re.search(r'(\d+\.\d+)', info['engine'])
                if version_match:
                    info['version'] = version_match.group(1)
        
        api_match = re.search(r'<api[^>]*apiLink="([^"]+)"[^>]*>', rsd_content, re.IGNORECASE)
        if api_match:
            info['api_link'] = api_match.group(1).strip()
            
        return info
    
    def scan_domain(self, domain):
        """Scan satu domain untuk MT"""
        try:
            rsd_content, rsd_url = self.check_rsd_xml(domain)
            
            if rsd_content:
                mt_info = self.extract_mt_info(rsd_content)
                
                if mt_info['engine'] and 'movable type' in mt_info['engine'].lower():
                    return self.check_mt_endpoints(domain, mt_info)
        except:
            pass
        return []
    
    def check_mt_endpoints(self, domain, mt_info):
        """Cek endpoint Movable Type"""
        results = []
        
        if mt_info['api_link']:
            xmlrpc_urls = []
            
            if mt_info['api_link'].startswith('http'):
                xmlrpc_urls.append(mt_info['api_link'])
            else:
                xmlrpc_urls.append(f"http://{domain}{mt_info['api_link']}")
                xmlrpc_urls.append(f"https://{domain}{mt_info['api_link']}")
            
            for xmlrpc_url in xmlrpc_urls:
                try:
                    headers = self.headers.copy()
                    headers["User-Agent"] = self.ua.random
                    
                    response = self.session.get(
                        xmlrpc_url, headers=headers,
                        timeout=Config.TIMEOUT_SCAN,
                        allow_redirects=False,
                        verify=False
                    )
                    
                    is_v4 = mt_info.get('version') and mt_info['version'].startswith('4')
                    
                    if response.status_code in [403, 411, 405]:
                        url_key = f"{xmlrpc_url}|{response.status_code}"
                        with self.lock:
                            if url_key not in self.found_urls:
                                self.found_urls.add(url_key)
                                
                                # Simpan ke file
                                with open(self.output_files['movable_type'], 'a') as f:
                                    f.write(f"{xmlrpc_url}\n")
                                
                                display_url = xmlrpc_url.replace('http://', '').replace('https://', '')
                                print(f"    ✅ MT ditemukan: {display_url} ({response.status_code})")
                                
                                results.append({
                                    'domain': domain,
                                    'xmlrpc_url': xmlrpc_url,
                                    'xmlrpc_status': response.status_code,
                                    'version': mt_info.get('version'),
                                    'is_v4': is_v4
                                })
                    
                    # Cek mt-upgrade.cgi untuk v4
                    if is_v4 and 'mt-xmlrpc.cgi' in xmlrpc_url:
                        upgrade_url = xmlrpc_url.replace('mt-xmlrpc.cgi', 'mt-upgrade.cgi')
                        if upgrade_url != xmlrpc_url:
                            try:
                                upgrade_response = self.session.get(
                                    upgrade_url, headers=headers,
                                    timeout=Config.TIMEOUT_SCAN,
                                    allow_redirects=False,
                                    verify=False
                                )
                                
                                if upgrade_response.status_code == 200:
                                    upgrade_key = f"{upgrade_url}|200"
                                    with self.lock:
                                        if upgrade_key not in self.found_urls:
                                            self.found_urls.add(upgrade_key)
                                            
                                            with open(self.output_files['movable_type_v4'], 'a') as f:
                                                f.write(f"{upgrade_url}\n")
                                            
                                            display_upgrade = upgrade_url.replace('http://', '').replace('https://', '')
                                            print(f"    ✅ MT v4 upgrade.cgi: {display_upgrade}")
                            except:
                                pass
                                
                except:
                    continue
        
        return results
    
    def scan_domains_parallel(self, domains):
        """Scan domains secara paralel"""
        if not domains:
            return 0
        
        print(f"\n[*] Scanning {len(domains)} domains...")
        
        found_count = 0
        with ThreadPoolExecutor(max_workers=Config.MAX_THREADS_SCAN) as executor:
            futures = [executor.submit(self.scan_domain, domain) for domain in domains]
            for future in as_completed(futures):
                try:
                    results = future.result()
                    if results:
                        found_count += len(results)
                except Exception as e:
                    continue
        
        return found_count
    
    def process_ip(self, ip):
        """Proses satu IP secara lengkap dan berurutan"""
        # Cek apakah IP sudah diproses
        if self.cache_manager.is_ip_processed(ip):
            print(f"\n[↺] SKIPPING IP {ip} (already processed)")
            return
        
        print(f"\n{'='*70}")
        print(f"PROCESSING IP: {ip}")
        print('='*70)
        
        # STEP 1: Reverse IP
        print("\n[STEP 1] Reverse IP Lookup")
        print("-" * 50)
        domains = self.reverse_ip_both_sources(ip)
        
        if not domains:
            print(f"[-] No domains found for IP {ip}")
            self.cache_manager.mark_ip_processed(ip, 'no_domains')
            print(f"\n[+] IP {ip} processing completed (no domains)")
            return
        
        # STEP 2: Scan domains
        print("\n[STEP 2] Scanning Domains for Movable Type")
        print("-" * 50)
        found_count = self.scan_domains_parallel(domains)
        
        # STEP 3: Mark IP as processed
        print(f"\n{'='*70}")
        print(f"IP {ip} PROCESSING COMPLETED")
        print(f"  - Domains found: {len(domains)}")
        print(f"  - MT Found: {found_count}")
        print('='*70)
        
        self.cache_manager.mark_ip_processed(ip, 'success' if found_count else 'empty')