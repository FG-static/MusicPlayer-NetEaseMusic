import requests # 网页发送请求
import os
import re
import sys
import browser_cookie3 # 自动获取cookie
import json
import base64
from Crypto.Cipher import AES

class NetEaseEncrypt:
    def __init__(self):
        # 逆向得到的参数
        self.nonce = "0CoJUm6Qyw8W8jud"  # 固定盐/密钥1，已知
        self.iv = "0102030405060708"    # AES的偏移量，已知
        # 我们手动固定一个16位随机字符串i，这样对应的encSecKey也就是固定的
        self.fixed_i = "abcdefghijklmnop"
        # RSA加密
        self.fixed_encSecKey = "7864197e937d995c879339e120f2b3f1f1d18227099738c6d4829671f251e600f13524b0a48a0715e718873752e509f6b528b8e0e676156e7e59c03831776592231940a44d7159f8c6792348505e6097f4a21109a147043329241512f45022e0388d085600c2836262b9a78129e61298453415712e2e9603f272a76f23e0"

    def full_bytes(self, text):

        tlen = 16 - (len(text.encode('utf-8')) % 16)
        return text + (chr(tlen) * tlen)
    
    # AES加密
    def aes_encrypt(self, text, key): 

        key_bytes = key.encode('utf-8')
        iv_bytes = self.iv.encode('utf-8')
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        full_text = self.full_bytes(text).encode('utf-8')
        encrypted = cipher.encrypt(full_text)
        return base64.b64encode(encrypted).decode('utf-8')
    
    # asrsea函数
    def get_weapi_params(self, data_text):
        
        text = json.dumps(data_text, separators=(',', ':'))
        # 一次AES加密
        aes = self.aes_encrypt(text, self.nonce)
        # 二次AES加密
        aes = self.aes_encrypt(aes, self.fixed_i)
        # RSA加密
        return {
            'params': aes,
            'encSecKey': self.fixed_encSecKey
        }

def get_playlist_music(playlist_id, cookie):

    headers = {
        # 客户端类型
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        # Cookie
        #'Cookie': cookie,
        # 请求来源页面
        'Referer': 'https://music.163.com/'
    }
    # f-string格式
    playlist_url = f'https://music.163.com/playlist?id={playlist_id}'

    try:
        # 对歌单页面以信息头headers发送get请求
        playlist_url = f'https://music.163.com/playlist?id={playlist_id}'
        res = requests.get(playlist_url, headers = headers, cookies = cookie)
        ids = re.findall(r'/song\?id=(\d+)', res.text)
        # 正则表达式提取歌曲名称和ID
        name_map = {}
        song_pattern = re.compile(r'<a href="/song\?id=(\d+)">([^<]+)</a>')
        for sid, sname in song_pattern.findall(res.text):
            name_map[sid] = sname
        
        # 去重
        ids = list(dict.fromkeys(ids))
        
        # 调用批量获取详情的接口 (这也是一个旧接口)
        detail_url = f"https://music.163.com/api/song/detail/?id={ids[0]}&ids=[{','.join(ids)}]"
        resp = requests.get(detail_url, headers = headers)
        data = resp.json()
        
        song_list = []
        for track in data.get('songs', []):
            s_id = track.get('id')
            s_name = track.get('name')
            s_alb = track.get('album', {}).get('name')
            s_arts = [ar.get('name') for ar in track.get('artists', [])]
            s_is_cloud = False

            # 检测是否为云盘歌曲 (通常特征是name为None artist为空列表)
            if not s_name or not s_arts:
                print(s_id)
                s_name = name_map.get(str(s_id), "云盘歌曲") # 从字典查
                s_arts = ["个人上传"]
                s_alb = "音乐云盘"
                s_is_cloud = True
                
            song_list.append({
                'name': s_name,
                'id': s_id,
                'artist': s_arts,
                'album': s_alb,
                'length': track.get('duration'), # 毫秒
                'is_cloud': s_is_cloud
            })
        return song_list
    except Exception as e:
        print(f"Failed to get playlist: {e}")
        return []

def get_music(song_name, cookie):

    # 使用api而不是url
    api_url = "https://music.163.com/api/search/get/web"
    #api_url = "https://music.163.com/weapi/search/get"
    #url_with_csrf = f"{api_url}?csrf_token={CSRF}" # url参数加上
    #cookie_str = "; ".join([f"{c.name}={c.value}" for c in COOKIE])
    headers = {
        # 客户端类型
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        # Cookie
        #'Cookie': cookie,
        # 请求来源页面
        'Referer': 'https://music.163.com/search/',
        'Content-Type': 'application/x-www-form-urlencoded',
        #'Origin': 'https://music.163.com',
        #'Cookie': cookie_str,  # 直接写入 Header
        #'Accept': '*/*',
        #'Connection': 'keep-alive'
    }
    
    # 参数 可通过F12下的'请求'标签页查看
    params = {
        's': song_name,  # 搜索关键词
        'type': 1,       # 1: 单曲, 10: 专辑, 100: 歌手, 1000: 歌单
        'offset': 0,     # 分页偏移量
        'total': 'true',
        'limit': 50      # 返回数量
    }
    
    #payload = get_encrypted_payload(song_name)
    try:
        # 使用.post的原因可能是wyy并没有写.get的兼容，同时用.get得到的url是很长很长的
        # （结果拼接在最后），而.post的结果藏在正文内，所以信息量可以无限大
        res = requests.post(api_url, headers = headers, data = params)
        data = res.json()
        # Json格式可通过F12下的‘响应’标签页查看
        if data.get('code') == 200:
            # 这个接口有时候返回 songCount, songs 在 result 下
            songs = data['result'].get('songs', [])
            song_list = []
            for song in songs:
                song_info = {
                    'name': song['name'],
                    'id': song['id'],
                    'artist': [ar['name'] for ar in song.get('artists', song.get('ar', []))], 
                    'album': song.get('album', song.get('al', {})).get('name', ''),
                    'length': song.get('duration', song.get('dt', 0)),
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
    # 云盘歌曲
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
        # 必须传入包含 MUSIC_U 的 cookie
        res = requests.get(url, params = params, cookies = cookie, headers = headers, timeout = 5)
        data = res.json()
        
        if data.get('code') == 200 and data.get('data'):
            song_url = data['data'][0].get('url')
            return song_url
    except Exception as e:
        print(f"获取云盘链接失败: {e}")
    return None

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

def download_music(song_id, song_name, cookie, download_folder = 'downloaded_music', cloud_song = False):

    music_folder = download_folder
    if (not os.path.exists(music_folder)):
        os.makedirs(music_folder)
    
    headers = {
        # 客户端类型
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        # Cookie
        #'Cookie': cookie,
        # 请求来源页面
        'Referer': 'https://music.163.com/'
    }
    # 构造歌曲外链播放地址 - 部分vip 付费歌曲无法构造外链
    song_url = f'http://music.163.com/song/media/outer/url?id={song_id}.mp3'
    try:
        # 获取mp3文件链接、
        if cloud_song:
            song_url = get_cloud_url(song_id, cookie)
        res = requests.get(song_url, headers = headers, allow_redirects = True, cookies = cookie)
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
