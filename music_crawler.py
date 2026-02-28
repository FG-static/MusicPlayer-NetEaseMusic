import requests # 网页发送请求
import os
import re
import sys
import browser_cookie3 # 自动获取cookie
import json
import base64
import random
import string
from Crypto.Cipher import AES

class NetEaseEncrypt:
    # Implements the typical *weapi* encryption used by the official web client.
    #
    # Request parameters are JSON-serialized, then encrypted twice with AES-CBC
    # using a fixed nonce and a random 16-byte secret. The secret key itself is
    # RSA-encrypted using the server's public modulus & exponent. This mirrors
    # the logic found in the site's JavaScript and is required for all modern
    # `/weapi/` endpoints; a hard‑coded `encSecKey` will be rejected.
    def __init__(self):
        # 参数参考网易云前端脚本
        self.nonce = "0CoJUm6Qyw8W8jud"  # 固定盐/密钥1
        self.iv = "0102030405060708"
        self.pubKey = "010001"
        # 下面是公钥模数（hex）
        self.modulus = (
            "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725"
            "152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312"
            "ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424"
            "d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8"
            "e7"
        )

    def full_bytes(self, text):
        tlen = 16 - (len(text.encode('utf-8')) % 16)
        return text + (chr(tlen) * tlen)

    def aes_encrypt(self, text, key):
        key_bytes = key.encode('utf-8')
        iv_bytes = self.iv.encode('utf-8')
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        full_text = self.full_bytes(text).encode('utf-8')
        encrypted = cipher.encrypt(full_text)
        return base64.b64encode(encrypted).decode('utf-8')

    def rsa_encrypt(self, text):
        # RSA加密时先反转字符串
        text = text[::-1]
        hex_text = text.encode('utf-8').hex()
        num = int(hex_text, 16)
        exp = int(self.pubKey, 16)
        mod = int(self.modulus, 16)
        rs = pow(num, exp, mod)
        return format(rs, 'x').zfill(256)

    def get_weapi_params(self, data_text):
        text = json.dumps(data_text, separators=(',', ':'))
        sec_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        enc_text = self.aes_encrypt(self.aes_encrypt(text, self.nonce), sec_key)
        enc_sec_key = self.rsa_encrypt(sec_key)
        return {
            'params': enc_text,
            'encSecKey': enc_sec_key
        }

# helper to pull CSRF token from cookie jar

def _csrf_from_cookie(cookie):
    try:
        cj = requests.utils.dict_from_cookiejar(cookie)
        return cj.get('__csrf', '')
    except Exception:
        return ''


def get_playlist_music(playlist_id, cookie):
    """Use the modern encrypted weapi to fetch playlist details.

    Returns a list of track dictionaries similar to the old implementation.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://music.163.com/'
    }

    api_url = "https://music.163.com/weapi/v6/playlist/detail"
    payload = NetEaseEncrypt().get_weapi_params({
        'id': playlist_id,
        'n': 1000,      # 返回的歌曲数量上限
        's': 8,         # 排序字段（无实际影响）
        'csrf_token': _csrf_from_cookie(cookie)
    })

    try:
        resp = requests.post(api_url, headers=headers, data=payload, cookies=cookie, timeout=5)
        try:
            data = resp.json()
        except ValueError:
            print("get_playlist_music: non-json response", resp.status_code, resp.text[:200])
            return []
        song_list = []
        for track in data.get('playlist', {}).get('tracks', []):
            s_id = track.get('id')
            s_name = track.get('name')
            s_alb = track.get('al', {}).get('name') or track.get('album', {}).get('name')
            s_arts = [ar.get('name') for ar in track.get('ar', track.get('artists', []))]
            s_is_cloud = False
            # 云盘歌曲识别
            if not s_name or not s_arts:
                s_name = "云盘歌曲"
                s_arts = ["个人上传"]
                s_alb = "音乐云盘"
                s_is_cloud = True

            song_list.append({
                'name': s_name,
                'id': s_id,
                'artist': s_arts,
                'album': s_alb,
                'length': track.get('dt', track.get('duration', 0)),
                'is_cloud': s_is_cloud
            })
        return song_list
    except Exception as e:
        print(f"Failed to get playlist: {e}")
        return []


# helper to pull CSRF token from cookie jar

def _csrf_from_cookie(cookie):
    try:
        cj = requests.utils.dict_from_cookiejar(cookie)
        return cj.get('__csrf', '')
    except Exception:
        return ''
 

def get_music(song_name, cookie):
    """Search for a song using the encrypted weapi endpoint."""
    api_url = "https://music.163.com/weapi/search/get"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://music.163.com/search/',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    params = {
        's': song_name,
        'type': '1',
        'offset': '0',
        'total': 'true',
        'limit': '50',
        'csrf_token': _csrf_from_cookie(cookie)
    }

    payload = NetEaseEncrypt().get_weapi_params(params)
    try:
        res = requests.post(api_url, headers=headers, data=payload, cookies=cookie, timeout=5)
        try:
            data = res.json()
        except ValueError:
            print("get_music: non-json response", res.status_code, res.text[:200])
            return []
        if data.get('code') == 200:
            songs = data.get('result', {}).get('songs', []) or data.get('songs', [])
            song_list = []
            for song in songs:
                song_info = {
                    'name': song.get('name'),
                    'id': song.get('id'),
                    'artist': [ar.get('name') for ar in song.get('ar', song.get('artists', []))],
                    'album': song.get('al', song.get('album', {})).get('name', ''),
                    'length': song.get('dt', song.get('duration', 0)),
                    'is_cloud': False
                }
                song_list.append(song_info)
            return song_list
        else:
            print(f"API Error: {data}")
            return []
    except Exception as e:
        print(f"Failed to search song: {e}")
        return []

def get_encrypted_payload(song_name):

    data = {
        's': song_name,
        'type': "1",
        'offset': "0",
        'total': "true",
        'limit': "30",
        'csrf_token': CSRF
    }
    encryptor = NetEaseEncrypt()
    p, s = encryptor.get_weapi_params(data)
    return {
        'params': p,
        'encSecKey': s
    }

def get_cloud_url(song_id, cookie):
    """Retrieve a cloud (personal uploaded) song using the legacy interface.

    The modern weapi endpoint works for both normal and cloud songs, but some
    cloud entries still require the interface3 URL. We keep this as a fallback.
    """
    params = {
        "ids": f"[{song_id}]",
        "level": "standard",
        "encodeType": "mp3"
    }
    url = "https://interface3.music.163.com/api/song/enhance/player/url/v1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://music.163.com/'
    }
    try:
        res = requests.get(url, params=params, cookies=cookie, headers=headers, timeout=5)
        data = res.json()
        if data.get('code') == 200 and data.get('data'):
            return data['data'][0].get('url')
    except Exception as e:
        print(f"获取云盘链接失败: {e}")
    return None


# 获取歌曲播放链接

def get_song_url(song_id, cookie, br=320000):
    """Return a playable URL for a song id using the encrypted weapi endpoint.

    Works for normal tracks, VIP tracks (if the cookie has login permissions),
    and usually for cloud songs as well. If the weapi call fails we fall back to
    the older `get_cloud_url` when necessary.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://music.163.com/'
    }
    api = "https://music.163.com/weapi/song/enhance/player/url"
    params = {
        'ids': [song_id],
        'br': br,
        'csrf_token': _csrf_from_cookie(cookie)
    }
    try:
        payload = NetEaseEncrypt().get_weapi_params(params)
        res = requests.post(api, headers=headers, data=payload, cookies=cookie, timeout=5)
        data = res.json()
        print(f"[get_song_url] weapi code={data.get('code')}, has_data={bool(data.get('data'))}")
        if data.get('code') == 200 and data.get('data'):
            url = data['data'][0].get('url')
            if url:
                print(f"[get_song_url] got_url from weapi")
                return url
    except Exception as e:
        print(f"[get_song_url] weapi error: {e}")

    # fallback for cloud songs or old behaviour
    print(f"[get_song_url] falling back to get_cloud_url")
    return get_cloud_url(song_id, cookie)

# 获取歌词
def get_lyrics(song_id):
    url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1"
    res = requests.get(url)
    lyric_data = res.json().get('lrc', {}).get('lyric', '')
    
    # {时间(秒): 歌词文字}
    lyrics_dict = {}
    pattern = re.compile(r'\[(\d+):(\d+\.\d+)\](.*)')
    for line in lyric_data.split('\n'):
        match = pattern.match(line)
        if match:
            m, s, text = match.groups()
            time_sec = int(m) * 60 + float(s)
            lyrics_dict[time_sec] = text.strip()
    return lyrics_dict

def download_music(song_id, song_name, cookie, download_folder = 'downloaded_music'):
    """Download a song to disk.  Automatically fetches a working URL via
    `get_song_url` (which itself handles cloud-special cases)."""
    music_folder = download_folder
    if not os.path.exists(music_folder):
        os.makedirs(music_folder)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://music.163.com/'
    }
    # try obtain play url dynamically
    song_url = get_song_url(song_id, cookie)
    print(f"[download_music] song_id={song_id}, got_url={bool(song_url)}")
    if song_url:
        print(f"[download_music] url_preview: {song_url[:80]}...")
    if not song_url:
        # fallback to outer url
        song_url = f'http://music.163.com/song/media/outer/url?id={song_id}.mp3'
    try:
        res = requests.get(song_url, headers=headers, allow_redirects=True, cookies=cookie)
        # 检查是否成功获取
        # 1.检查HTTP状态码是否为成功（2xx）
        if (res.status_code == 200):
            # 2.进一步检查最终URL，排除已知的错误模式
            if (res.url and 'music.163.com/error' not in res.url):
                # 3.检查响应内容的MIME类型，确认是音频文件
                content_type = res.headers.get('Content-Type', '').lower()
                if ('audio' in content_type or 'application/octet-stream' in content_type):
                    safe_song_name = re.sub(r'[\\/*?:"<>|]', "_", song_name)
                    file_path = os.path.join(download_folder, f"{safe_song_name}.mp3")

                    with open(file_path, 'wb') as f:
                        f.write(res.content)
                    print(f"Success to download: {song_name}")
                    return True
                else:
                    print(f"Failed to download: {song_name}. Server returned an unexpected content type: {content_type}")
                    return False
            else:
                print(f"Failed to download: {song_name}. Redirected to an error page.")
                return False
        else:
            # 如果状态码不是200，直接判断为失败
            print(f"Failed to download: {song_name}. HTTP Status Code: {res.status_code}")
            return False
    except Exception as e:

        print(f"When downloaded {song_name} encountered error: {e}")
        return False

# 获取本地缓存的cookie，注意这里获取的不是单纯的字符串形式，不能用于请求头中的cookie，
# 但是直接填到请求的cookies栏可以自动转换
def get_cookie():
    try:
        # 抓取 .163.com 才能获取到完整的登录凭证
        ck = browser_cookie3.firefox(domain_name='.163.com')
        print("Successfully loaded cookies from Firefox (.163.com)")
        return ck
    except Exception as e:
        print(f"Error loading cookies: {e}")
        return None

if __name__ == "__main__":
    
    # 注意，复制cookie时需要用原始模式下复制，否则会产生'...'截断
    COOKIE = get_cookie()
    
    cookie_dict = requests.utils.dict_from_cookiejar(COOKIE) # 获取csrf_token值
    CSRF = cookie_dict.get('__csrf', '')
    # 歌单id
    PLAYLISTID = "9077800989"
    MUSICNAME = sys.stdin.readline().strip()
    songs = get_music(MUSICNAME, COOKIE)
    for i, song in enumerate(songs):
        print(f"[{i}] {song['name']} - {song['artist']} (ID: {song['id']})")
        # download_music(song['id'], song['name'], COOKIE)
    print("Enter index to download song...")
    idx = int(sys.stdin.readline().strip())
    download_music(songs[idx]['id'], songs[idx]['name'], COOKIE)
