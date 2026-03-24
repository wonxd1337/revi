# config.py
import os
import tempfile

# Konfigurasi Scanner
class Config:
    # Thread settings
    MAX_THREADS_REVERSE = 30  # Thread untuk reverse IP (pakai proxy)
    MAX_THREADS_SCAN = 100     # Thread untuk scan domain (tanpa proxy)
    
    # Proxy settings
    PROXY_REFRESH_INTERVAL = 1800  # 30 menit dalam detik
    # config.py - Updated with multiple proxy sources
import os
import tempfile

class Config:
    # Thread settings
    MAX_THREADS_REVERSE = 30
    MAX_THREADS_SCAN = 100
    
    # Proxy settings - MULTIPLE SOURCES
    PROXY_REFRESH_INTERVAL = 1800  # 30 menit
    PROXY_URLS = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTP_RAW.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
    ]
    
    # RNG settings
    MAX_VALID_RNG = 50
    MAX_VALID_RNG_LIMIT = 200
    
    # Cache settings
    MAX_CACHE_SIZE = 10000
    CACHE_CLEANUP_INTERVAL = 3600
    
    # Memory management
    TEMP_DIR = tempfile.gettempdir() + "/mt_scanner/"
    MAX_MEMORY_ITEMS = 5000
    
    # File output
    OUTPUT_FILES = {
        'movable_type': 'movable_type.txt',
        'movable_type_v4': 'movable_type_v4.txt',
        'processed_ips': 'processed_ips.txt',
        'cache': 'cache.db'
    }
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    # Timeout settings
    TIMEOUT_REVERSE = 30
    TIMEOUT_SCAN = 10
    
    @staticmethod
    def ensure_temp_dir():
        if not os.path.exists(Config.TEMP_DIR):
            os.makedirs(Config.TEMP_DIR)
    # RNG settings
    MAX_VALID_RNG = 50
    MAX_VALID_RNG_LIMIT = 200  # Batas maksimal
    
    # Cache settings
    MAX_CACHE_SIZE = 10000  # Maksimal entries di cache
    CACHE_CLEANUP_INTERVAL = 3600  # Bersihkan cache setiap 1 jam
    
    # Memory management
    TEMP_DIR = tempfile.gettempdir() + "/mt_scanner/"
    MAX_MEMORY_ITEMS = 5000  # Maksimal item dalam memory
    
    # File output
    OUTPUT_FILES = {
        'movable_type': 'movable_type.txt',
        'movable_type_v4': 'movable_type_v4.txt',
        'processed_ips': 'processed_ips.txt',  # Track IP sudah diproses
        'cache': 'cache.db'  # Database cache
    }
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    # Timeout settings
    TIMEOUT_REVERSE = 30
    TIMEOUT_SCAN = 10
    
    @staticmethod
    def ensure_temp_dir():
        """Pastikan direktori temporary ada"""
        if not os.path.exists(Config.TEMP_DIR):
            os.makedirs(Config.TEMP_DIR)
