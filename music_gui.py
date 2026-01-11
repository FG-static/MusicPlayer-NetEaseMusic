import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os
import pygame
import random
import json

from music_crawler import get_playlist_music, download_music, get_music, get_cookie, get_lyrics

# 注意，复制cookie时需要用原始模式下复制，否则会产生'...'截断
COOKIE = get_cookie()
DEFAULT_DOWNLOAD_FOLDER = "downloaded_music"
DEFAULT_SAVE_FOLDER = "cache"

class MusDownloadGUI:
    # 构造函数=初始化方法
    def __init__(self, root): # self就是实例本身，类似于this，root为窗口根节点
        # 检查文件夹
        if not os.path.exists(DEFAULT_DOWNLOAD_FOLDER + "//temp"):
            os.makedirs(DEFAULT_DOWNLOAD_FOLDER + "//temp", exist_ok = True)
            print(f"Create: {DEFAULT_DOWNLOAD_FOLDER + "//temp"}")
        if not os.path.exists(DEFAULT_SAVE_FOLDER):
            os.makedirs(DEFAULT_SAVE_FOLDER, exist_ok = True)
            print(f"Create: {DEFAULT_SAVE_FOLDER}")
        self.root = root
        self.root.title("NetEaseMusic")
        self.root.geometry("1200x800") # 窗口大小
        self.songs_list = [] # 储存搜索列表
        # 在线播放
        pygame.mixer.init() # 初始化播放器
        self.is_playing = False
        self.cur_song = None # 记录歌曲url
        self.pause = False
        # 进度条
        self.is_changing = False # 是否拖拽中
        self.drag_offset = 0 # 拖拽偏移量
        self.song_length = 0 # 歌曲总长度(s)
        self.update_progress() # 更新进度条
        # 播放歌词
        self.cur_lyrics_dict = {}
        self.lyric_times = []      # 键值排序
        # 播放列表
        self.playlist = []         # 播放列表
        self.cur_index = -1        # 当前播放歌曲在列表中的索引
        # 播放模式
        self.REPEAT_ALL = 0    # 列表循环
        self.REPEAT_ONE = 1    # 单曲循环
        self.RANDOM = 2        # 随机播放
        self.mode_type = self.REPEAT_ALL
        self.mode_text = ["Repeat All", "Single Repeat", "Random"]
        self.setup_ui() 
        # 加载播放列表
        self.load_playlist_from_local()
    
    # 创建用户图形界面
    def setup_ui(self):
        # 搜索框
        search_frame = tk.Frame(self.root) # 容器框架
        # 使用pack容器，设置左右和上下边距为10px，框架在水平方向上填充父容器的可用空间
        search_frame.pack(padx = 10, pady = 10, fill = tk.X)
        
        # 提示输入内容，放在最左侧
        tk.Label(search_frame, text = "Search songs or Enter songlistsID:").pack(side = tk.LEFT)

        # 搜索内容
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable = self.search_var, width = 40) # 输入框
        self.search_entry.pack(side = tk.LEFT, padx = 5)

        # 搜索按钮
        self.search_button = tk.Button(search_frame, text = "Search", command = self.search_songs)
        self.search_button.pack(side = tk.LEFT, padx = 5)

        # 结果列表
        list_frame = tk.Frame(self.root)

        # 水平竖直方向都填充可用空间，并随窗口大小伸缩
        list_frame.pack(padx = 10, pady = 10, fill = tk.BOTH, expand = True)

        # 标签文字靠左对齐
        tk.Label(list_frame, text = "Search Result:").pack(anchor = tk.W)

        # 初始显示15行，可滚动列表组件
        self.results_listbox = tk.Listbox(list_frame, height = 15)
        self.results_listbox.pack(fill = tk.BOTH, expand = True, side = tk.LEFT)
        # 双击+按钮添加歌曲到播放列表
        self.add_btn = tk.Button(list_frame, text = "Add to Playlist ➔", command = self.add_to_playlist)
        self.add_btn.pack(pady = 5)
        self.results_listbox.bind('<Double-1>', self.add_to_playlist)
        
        # 垂直滚动条，command部分表示控制列表视图
        scrollbar = tk.Scrollbar(list_frame, orient = tk.VERTICAL, command = self.results_listbox.yview)
        scrollbar.pack(fill = tk.Y, side = tk.RIGHT)

        button_frame = tk.Frame(self.root)
        button_frame.pack(padx = 10, pady = 10, fill = tk.X)

        # 下载选中歌曲的按钮
        self.download_button = tk.Button(button_frame, text = "Download", command = self.download_selected_song)
        self.download_button.pack(side = tk.LEFT, padx = 5)

        # 状态栏 tk.SUNKEN->凹陷效果 tk.BOTTOM->窗口底部
        self.status_label = tk.Label(self.root, text = "Ready", relief = tk.SUNKEN, anchor = tk.W)
        self.status_label.pack(side = tk.BOTTOM, fill = tk.X)

        play_frame = tk.Frame(self.root)
        play_frame.pack(pady = 5)
        self.play_button = tk.Button(play_frame, text = "Play", command = self.play_selected_song)
        self.play_button.pack(side = tk.LEFT, padx = 5)

        self.pause_button = tk.Button(play_frame, text = "Pause", command = self.pause_song)
        self.pause_button.pack(side = tk.LEFT, padx = 5)

        self.stop_button = tk.Button(play_frame, text = "Stop", command = self.stop_song)
        self.stop_button.pack(side = tk.LEFT, padx = 5)

        top_info_frame = tk.Frame(self.root) 
        top_info_frame.pack(side = tk.TOP, fill = tk.X, padx = 10, pady = (5, 0))

        # 歌曲名字显示
        self.name_label = tk.Label(top_info_frame, text = "未知歌曲", fg = "blue")
        self.name_label.pack(side = tk.LEFT, pady = (0, 5))

        # 歌词
        self.lrc_label = tk.Label(top_info_frame, text = "🚫无歌词", fg = "gray")
        self.lrc_label.pack(side = tk.LEFT, expand = True, fill = tk.X, anchor = "center")

        # 播放进度显示
        self.time_label = tk.Label(top_info_frame, text = "00:00/00:00")
        self.time_label.pack(side = tk.RIGHT)

        self.progress_var = tk.DoubleVar()
        self.progress_scale = tk.Scale(
            self.root,
            from_ = 0,                        
            to = 1000,                         
            orient = 'horizontal',            
            variable = self.progress_var,    
            showvalue = False,                # 不显示滑块上的数值，用标签代替
            length = 1000,                     # 进度条长度
            command = self.progress_draging
        )
        self.progress_scale.pack(fill = 'x', padx = 10, pady = 5)
        self.progress_scale.bind('<ButtonRelease-1>', self.progress_release)

        # 音量调
        #volume_frame = tk.Frame(self.root)
        #volume_frame.pack(padx = 5)
        tk.Label(play_frame, text = "Volume:").pack(side = tk.LEFT)
        self.volume_scale = tk.Scale(

            play_frame,
            from_ = 0,
            to = 100,
            orient = 'horizontal',
            command = self.volume_changing
        )
        self.volume_scale.set(40)
        self.volume_scale.pack(side = tk.LEFT)

        # 播放列表
        tk.Label(list_frame, text = "Current Playlist:").pack(anchor = tk.W)
        self.playlist_listbox = tk.Listbox(list_frame, height = 15)
        self.playlist_listbox.pack(fill = tk.X, padx = 5, pady = 5)
        self.add_all_button = tk.Button(search_frame, text = "Add All to Playlist", command = self.add_all_to_playlist)
        self.add_all_button.pack(side = tk.LEFT, padx = 5)

        # 删除歌曲
        self.del_btn1 = tk.Button(list_frame, text = "Delete from Playlist ↓", command = self.delete_from_playlist)
        self.del_btn1.pack(pady = 5)
        self.del_btn2 = tk.Button(list_frame, text = "Clear Playlist", command = self.delete_all_playlist)
        self.del_btn2.pack(pady = 5)

        # 播放模式调节
        self.switch_button = tk.Button(play_frame, text = self.mode_text[self.mode_type], command = self.switch_playmode)
        self.switch_button.pack(side = tk.LEFT, padx = 5)

        # 关闭按钮
        self.exit_button = tk.Button(button_frame, text = "Exit", command = self.exit)
        self.exit_button.pack(side = tk.RIGHT, padx = 5)
        self.root.protocol("WM_DELETE_WINDOW", self.exit) # 右上角的红x

    # 更新状态
    def update_status(self, message):
        self.status_label.config(text = message) # 更新状态栏标签
        self.root.update_idletasks() # 强制界面更新

    # 搜索歌曲
    def search_songs(self):
        # 按钮按下事件
        ser = self.search_var.get().strip()
        if (not ser):
            messagebox.showwarning("Error entry", "Please enter songs name or songlists ID")
            return
        # 搜歌还是歌单
        if ser.isdigit():
            res = messagebox.askyesno("Detect ID", f"Detected pure numbers: {ser}\nDo you want to search for a Playlist instead of a song?")
            if res:
                self.search_button.config(state = tk.DISABLED)
                self.update_status("Fetching playlist...")
                search_thread = threading.Thread(target = self.perform_playlist_fetch, args = (ser,))
                search_thread.daemon = True
                search_thread.start()
                return

        # 禁用按钮重复按下
        self.search_button.config(state = tk.DISABLED)
        self.update_status("Searching...")
        
        # 分离新线程
        search_thread = threading.Thread(target = self.perform_search, args = (ser, ))
        search_thread.daemon = True
        search_thread.start()

    def perform_playlist_fetch(self, ser):
        try:
            raw_songs = get_playlist_music(ser, COOKIE)
            if not raw_songs:
                self.root.after(0, lambda: self.update_status("No songs found in this playlist."))
                self.root.after(0, lambda: self.search_button.config(state = tk.NORMAL))
                return
            self.root.after(0, self.update_search_results, raw_songs, f"Playlist ID: {ser}")
            self.root.after(0, lambda: self.update_status(f"Success: Fetched {len(raw_songs)} songs."))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Fetch Error: {e}"))
        finally:
            self.root.after(0, lambda: self.search_button.config(state = tk.NORMAL))

    # 执行搜索
    def perform_search(self, ser):
        try:
            songs = get_music(ser, COOKIE)
            # 更新搜索结果
            self.root.after(0, self.update_search_results, songs, ser)
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Failed to search: {e}"))
            self.root.after(0, lambda: self.search_button.config(state = tk.NORMAL))

    # 更新搜索结果
    def update_search_results(self, songs, ser):
        self.songs_list = songs
        self.results_listbox.delete(0, tk.END) # 清空
        if (not songs):
            self.results_listbox.insert(tk.END, f"No find the result related to '{ser}'")
            self.download_button.config(state = tk.DISABLED) # 禁止下载
        else:
            for song in songs:
                ms = song.get('length', 0)
                minu = int(ms // 60000)
                sec = int((ms % 60000) // 1000)

                show = f"{song.get('name', 'Unknown song')}"
                if ('artist' in song):
                    show += f" - {song['artist']}"
                show += f" - Length: {minu}:{sec:02d}"
                self.results_listbox.insert(tk.END, show)

            self.download_button.config(state = tk.NORMAL)
            self.update_status(f"Found {len(songs)} songs")

        self.search_button.config(state = tk.NORMAL)

    # 下载选中歌曲
    def download_selected_song(self):
        selection1 = self.results_listbox.curselection()
        selection2 = self.playlist_listbox.curselection()
        if (not selection1 and not selection2):
            messagebox.showwarning("Selection Error", "Please select a song")
            return
        selection = 0
        wait_songs_list = []
        if (not selection1):
            selection = selection2
            wait_songs_list = self.playlist
        else:
            selection = selection1
            wait_songs_list = self.songs_list
        song_index = selection[0]
        selected_song = wait_songs_list[song_index]
        # selected_song.get('name', 'Unknown song')表示尝试获取name的键值，如果获取失败则返回默认值
        self.update_status(f"Prepare to download: {selected_song.get('name', 'Unknown song')}")

        # 分离新线程
        download_thread = threading.Thread(target = self.perform_download, args = (selected_song,))
        download_thread.daemon = True # 结束程序时强制结束该线程
        download_thread.start()

    # 退出程序
    def exit(self):
        res = messagebox.askyesno(title = "Confirm to exit", message = "Really want to exit the application?")
        if res:
            # 保存播放列表
            self.save_playlist_to_local() 
            self.root.destroy()

    #下载歌曲
    def perform_download(self, song):
        try:
            if_cloud = song['is_cloud']
            success = download_music(song['id'], song['name'], COOKIE, DEFAULT_DOWNLOAD_FOLDER, if_cloud)
            if success:
                self.root.after(0, lambda: self.update_status(f"Successed to download: {song['name']}"))
            else:
                self.root.after(0, lambda: self.update_status(f"Failed to download: {song['name']}"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Encountered Error when download song: {str(e)}"))
    
    def download_complete(self, suc, total):
        self.progress_bar.pack_forget()
        self.update_status(f"Complete! Success: {suc}/{total}")
        messagebox.showinfo("Complete!", f"Successed to download {suc}/{total} songs")

    def play_selected_song(self):
        # 选中歌曲并分离线程
        selection1 = self.results_listbox.curselection()
        selection2 = self.playlist_listbox.curselection()
        if (not selection1 and not selection2):
            messagebox.showwarning("Selection Error", "Please select a song")
            return
        selection = 0
        wait_songs_list = []
        if (not selection1):
            selection = selection2
            wait_songs_list = self.playlist
        else:
            selection = selection1
            wait_songs_list = self.songs_list
        song_index = selection[0]
        if (song_index >= len(self.songs_list)):
            return
        selected_song = wait_songs_list[song_index]

        self.update_status(f"Prepare to play: {selected_song.get('name', 'Unknown song')}")
        
        play_thread = threading.Thread(target = self.play_song, args = (song_index,))
        play_thread.daemon = True
        play_thread.start()

    # 如果不自动获取id则后两项参数无需填写
    # 否则第二项参数为整首歌信息，第四项参数为时长
    def play_song(self, song_index, auto_get_id = False, song_len = 0): 
        # 播放歌曲
        # 临时文件，方便播放音乐
        temp_path = os.path.join(DEFAULT_DOWNLOAD_FOLDER + "//temp", "__TEMP_PREVIEW__.mp3")
        try:
            pygame.mixer.music.stop()  # 停止当前播放
            pygame.mixer.music.unload()  # 卸载当前音乐
    
            wait_songs_list = []
            selection1 = self.results_listbox.curselection()
            selection2 = self.playlist_listbox.curselection()
            if (not selection1):
                wait_songs_list = self.playlist
            else:
                wait_songs_list = self.songs_list
            if not auto_get_id:
                song_data = wait_songs_list[song_index]
                song_id = wait_songs_list[song_index]['id']
                self.song_length = int(wait_songs_list[song_index]['length'])
            else:
                song_data = song_index
                song_id = song_data['id']
                self.song_length = song_len
            self.drag_offset = 0 # 清空偏移
            self.progress_var.set(0)
            # 下载临时文件
            if_cloud = song_data['is_cloud']
            self.update_name_label(song_data['name'])
            download_music(song_id, "__TEMP_PREVIEW__", COOKIE, DEFAULT_DOWNLOAD_FOLDER + "//temp", if_cloud)
            
            # 获取歌词
            self.cur_lyrics_dict = get_lyrics(song_id)
            self.lyric_times = sorted(self.cur_lyrics_dict.keys())

            # 加载并播放
            pygame.mixer.music.load(temp_path)  # 加载本地临时文件
            pygame.mixer.music.play()
            
            # 更新状态到主线程
            self.root.after(0, self.playing_start)
            
        except pygame.error as e:
            self.root.after(0, lambda: self.update_status(f"Playing Error: {e}"))
            self.root.after(0, self.playing_stop)
    
    def playing_start(self):
        # UI更新
        self.is_playing = True
        self.drag_flag = 0
        self.update_time_label(0, self.song_length)
        self.pause = False
        self.play_button.config(state = tk.DISABLED)
        self.pause_button.config(state = tk.NORMAL, text = "Pause")
        self.stop_button.config(state = tk.NORMAL)
        self.update_status("Playing song...")
    
    def pause_song(self):
        if (not self.is_playing): return
        if (self.pause):
            pygame.mixer.music.unpause()
            self.pause = False
            self.pause_button.config(text = "Pause")
            self.update_status("Continue to play")
        else:
            pygame.mixer.music.pause()
            self.pause = True
            self.pause_button.config(text = "Continue")
            self.update_status("Pause to play")
    
    def stop_song(self):
        pygame.mixer.music.stop()
        self.playing_stop()
        self.cur_lyrics_dict = {}
        self.lrc_label.config(text = "🚫无歌词", fg = "gray")
        self.update_status("Playing had been stopped")

    def playing_stop(self):
        self.is_playing = False
        self.paused = False
        self.play_button.config(state = tk.NORMAL)
        self.pause_button.config(state = tk.DISABLED, text = "Pause")
        self.stop_button.config(state = tk.DISABLED)

    def volume_changing(self, val):
        volume = int(val) / 100.0
        pygame.mixer.music.set_volume(volume)

    def update_progress(self):
        if (not self.is_changing): # 未拖拽
            # 自动切歌
            if self.is_playing and not pygame.mixer.music.get_busy() and not self.pause:
                self.auto_next_song()
            # 均表示正在播放
            if (self.is_playing and pygame.mixer.music.get_busy()):
                current_pos = pygame.mixer.music.get_pos()
                current_pos_offset = current_pos / 1000.0 + self.drag_offset
                if current_pos_offset > self.song_length / 1000.0:
                    current_pos_offset = self.song_length / 1000.0
                if (self.song_length > 0):
                    progress_val = current_pos_offset * 1000000 / self.song_length
                    self.progress_var.set(progress_val)
                # 分:秒
                self.update_time_label(current_pos_offset, self.song_length)
                # 更新歌词
                # 从字典中查找当前秒数对应的歌词
                if hasattr(self, 'cur_lyrics_dict') and self.cur_lyrics_dict:
                    current_lrc = None
                    # 遍历找到当前时间应该显示的最后一句歌词
                    for t in self.lyric_times:
                        if t <= current_pos_offset:
                            current_lrc = self.cur_lyrics_dict[t]
                        else:
                            # 因为是排序的，一旦时间超过当前时间，后面的都不用看了
                            break
                    # 只有当找到歌词且内容不为空时才更新
                    if current_lrc:
                        self.lrc_label.config(text=current_lrc, fg="black")
        # 每隔0.125s自调用
        self.root.after(125, self.update_progress)
    
    def update_time_label(self, cpo, sl):
        # 两位小数字符串
        sl /= 1000.0
        cur_str = f"{int(cpo // 60):02d}:{int(cpo % 60):02d}"
        total_str = f"{int(sl // 60):02d}:{int(sl % 60):02d}"
        self.time_label.config(text = f"{cur_str} / {total_str}")

    def update_name_label(self, song_name):
        
        self.name_label.config(text = song_name)

    def progress_draging(self, val):
        self.is_changing = True

    def progress_release(self, event):
        target = self.progress_var.get() / 1000.0
        target = target * self.song_length / 1000.0
        self.drag_offset = target
        # 跳转
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start = target)
        self.update_time_label(target, self.song_length)
        self.root.after(100, lambda: self.__setattr__('is_changing', False))

    def auto_next_song(self):
        if not self.playlist:
            return
        if self.mode_type == self.REPEAT_ONE:
            # 单曲循环
            pass 
        elif self.mode_type == self.RANDOM:
            # 随机播放
            self.cur_index = random.randint(0, len(self.playlist) - 1)
        else:
            # 列表循环
            self.cur_index = (self.cur_index + 1) % len(self.playlist)
        
        self.play_specific_song(self.cur_index)

    def play_specific_song(self, index):
        if (0 <= index < len(self.playlist)):
            self.cur_index = index
            self.stop_song()
            song_data = self.playlist[index]
            
            artists = ", ".join(song_data['artist']) if isinstance(song_data['artist'], list) else song_data['artist']
            self.update_status(f"Playing: {song_data['name']} - {artists}")

            play_thread = threading.Thread(target = self.play_song, args = (song_data, True, song_data.get('length', 0),))
            play_thread.daemon = True
            play_thread.start()

    def update_playlist_show(self, song):
        # 更新右侧 Listbox 显示
        artists = ", ".join(song['artist']) if isinstance(song['artist'], list) else song['artist']
        self.playlist_listbox.insert(tk.END, f"{song['name']} - {artists}")

    def add_all_to_playlist(self):
        if not self.songs_list:
            messagebox.showinfo("Warning", "Search results are empty!")
            return
        
        count = 0
        for song in self.songs_list:
            if not any(p['id'] == song['id'] for p in self.playlist): # 防止重复添加
                self.playlist.append(song)
                self.update_playlist_show(song)
                count += 1
                
        self.update_status(f"Added {count} new songs to playlist.")

    def add_to_playlist(self, event = None):
        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showwarning("Add Error", "Please select a song from result list")
            return
        
        index = selection[0]
        selected_song = self.songs_list[index]
        
        # 检查是否已经在播放列表中
        if any(item['id'] == selected_song['id'] for item in self.playlist):
            messagebox.showwarning("Add Error", f"'{selected_song['name']}' is already in playlist.")
            return
        
        self.playlist.append(selected_song)
        self.update_playlist_show(selected_song)
        self.update_status(f"Added to playlist: {selected_song['name']}")

    def delete_from_playlist(self):
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("Delete Error", "Please select a song from playlist")
            return
        index = selection[0]
        song_name = self.playlist[index]['name']
        
        del self.playlist[index]
        self.playlist_listbox.delete(index)
        
        # 如果删除的是当前播放歌曲之前的歌，当前索引需要减1
        if index <= self.cur_index:
            self.cur_index -= 1
            
        self.update_status(f"Removed: {song_name}")

    def delete_all_playlist(self):
        if not self.playlist:
            messagebox.showinfo("Clear Info", "The playlist is empty")
            return
        # 误触
        if messagebox.askyesno("Confirm", "Really want to clear the playlist?"):
            self.playlist.clear()
            self.playlist_listbox.delete(0, tk.END)
            
            self.cur_index = -1
                
            self.update_status(f"Removed all songs in playlist")

    # 保存播放列表
    def save_playlist_to_local(self):
        try:
            # 只保存必要的歌曲信息，减少体积
            save_data = []
            for song in self.playlist:
                save_data.append({
                    'name': song.get('name'),
                    'id': song.get('id'),
                    'artist': song.get('artist'),
                    'album': song.get('album'),
                    'length': song.get('length'),
                    'is_cloud': song.get('is_cloud')
                })
            with open(DEFAULT_SAVE_FOLDER + "//playlist_config.json", "w", encoding = "utf-8") as f:
                json.dump(save_data, f, ensure_ascii = False, indent = 4)
        except Exception as e:
            print(f"Failed to save playlist: {e}")
    
    # 从本地加载到播放列表
    def load_playlist_from_local(self):
        if os.path.exists(DEFAULT_SAVE_FOLDER + "//playlist_config.json"):
            try:
                with open(DEFAULT_SAVE_FOLDER + "//playlist_config.json", "r", encoding = "utf-8") as f:
                    loaded_data = json.load(f)
                    self.playlist = loaded_data
                    
                    # 更新到 Listbox 界面
                    for song in self.playlist:
                        artists = ", ".join(song['artist'])
                        self.playlist_listbox.insert(tk.END, f"{song['name']} - {artists}")
                        
                self.update_status(f"Had loaded {len(self.playlist)} historical songs")
            except Exception as e:
                print(f"Failed to load playlist: {e}")

    def switch_playmode(self):
        # 切换模式索引 0->1->2->0
        self.mode_type = (self.mode_type + 1) % 3
        # 更新按钮文字
        self.switch_button.config(text = self.mode_text[self.mode_type])
        self.update_status(f"Mode changed to: {self.mode_text[self.mode_type]}")

if __name__ == "__main__":
    if (not os.path.exists(DEFAULT_DOWNLOAD_FOLDER)):
        os.makedirs(DEFAULT_DOWNLOAD_FOLDER)

    root = tk.Tk()
    app = MusDownloadGUI(root)
    root.mainloop()