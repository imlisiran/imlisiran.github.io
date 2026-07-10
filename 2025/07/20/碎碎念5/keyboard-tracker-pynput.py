import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from datetime import datetime
import threading
import time
import sys
import webbrowser
import sqlite3
import queue
from pynput import keyboard

class KeyboardTracker:
    def __init__(self):
        self.running = False
        self.start_time = None
        self.end_time = None
        self.listener = None
        # 修改数据库文件路径，使用程序所在目录
        self.db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyboard_stats.db")
        self.listener_thread = None
        # 软件说明网页URL
        self.about_url = "https:2am.top"
        
        # 数字键盘映射
        self.numpad_mapping = {
            96: "小键盘0", 97: "小键盘1", 98: "小键盘2", 99: "小键盘3",
            100: "小键盘4", 101: "小键盘5", 102: "小键盘6", 103: "小键盘7",
            104: "小键盘8", 105: "小键盘9", 106: "小键盘*", 107: "小键盘+",
            108: "小键盘Enter", 109: "小键盘-", 110: "小键盘.", 111: "小键盘/"
        }
        
        # 使用队列处理按键事件，减轻主线程负担
        self.key_queue = queue.Queue()
        
        # 使用全局计数变量，避免频繁数据库查询
        self.total_count = 0
        
        # 批量插入的缓冲区
        self.key_buffer = {}
        self.buffer_size = 20  # 缓冲区大小
        self.last_flush_time = time.time()
        self.flush_interval = 5  # 每5秒强制写入一次
        
        # 线程控制标志
        self.worker_running = True
        
        # 添加线程锁，避免多线程资源竞争 -- 修复: 先初始化锁，再使用锁
        self._buffer_lock = threading.Lock()
        self._db_lock = threading.Lock()
        
        # 确保pynput库可用
        try:
            self.keyboard = keyboard
            print("已加载pynput库")
        except ImportError:
            print("错误：未安装pynput库，请安装：")
            print("pip install pynput")
            messagebox.showerror("依赖缺失", "未安装必要的库。请安装pynput：\npip install pynput")
            sys.exit(1)
        
        # 初始化数据库
        self.init_database()
        
        # 加载缓存的总计数
        self.load_total_count()
        
        # 创建GUI
        self.create_gui()
        
        # 启动按键处理线程
        self.start_db_worker()
    
    def init_database(self):
        """初始化SQLite数据库"""
        try:
            # 确保数据库目录存在
            db_dir = os.path.dirname(self.db_file)
            if not os.path.exists(db_dir) and db_dir:
                os.makedirs(db_dir)
                
            # 连接数据库（避免使用check_same_thread=False，改用锁机制）
            self.conn = sqlite3.connect(self.db_file)
            self.conn.execute('PRAGMA journal_mode=WAL')  # 启用WAL模式提高并发性能
            self.conn.execute('PRAGMA synchronous=NORMAL')  # 降低同步级别提高性能
            self.conn.execute('PRAGMA temp_store=MEMORY')  # 使用内存临时表，提高性能
            
            # 创建表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS key_stats (
                    key_name TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            ''')
            
            # 创建元数据表
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # 创建索引
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_key_name ON key_stats(key_name)')
            
            self.conn.commit()
            print(f"成功初始化数据库: {self.db_file}")
        except Exception as e:
            print(f"初始化数据库时出错: {e}")
            messagebox.showerror("数据库错误", f"初始化数据库时出错: {e}\n数据库路径: {self.db_file}")
            sys.exit(1)
    
    def get_db_connection(self):
        """获取线程安全的数据库连接"""
        with self._db_lock:
            return sqlite3.connect(self.db_file)
    
    def load_total_count(self):
        """从数据库加载总按键次数"""
        try:
            with self._db_lock:
                cursor = self.conn.execute('SELECT SUM(count) FROM key_stats')
                result = cursor.fetchone()
                self.total_count = result[0] if result[0] is not None else 0
        except Exception as e:
            print(f"加载总计数时出错: {e}")
            self.total_count = 0
    
    def start_db_worker(self):
        """启动数据库工作线程，处理队列中的按键事件"""
        def worker():
            while self.worker_running:
                try:
                    # 获取队列中的按键或等待超时
                    try:
                        key_name = self.key_queue.get(timeout=0.5)
                        
                        # 添加到缓冲区
                        with self._buffer_lock:
                            if key_name in self.key_buffer:
                                self.key_buffer[key_name] += 1
                            else:
                                self.key_buffer[key_name] = 1
                            
                            # 增加总计数
                            self.total_count += 1
                        
                        # 标记任务完成
                        self.key_queue.task_done()
                    except queue.Empty:
                        # 队列超时，检查是否需要刷新缓冲区
                        pass
                    
                    # 检查是否需要刷新缓冲区
                    current_time = time.time()
                    buffer_size = 0
                    time_elapsed = False
                    
                    with self._buffer_lock:
                        buffer_size = len(self.key_buffer)
                        time_elapsed = (current_time - self.last_flush_time) >= self.flush_interval
                    
                    if (buffer_size >= self.buffer_size or time_elapsed) and buffer_size > 0:
                        self.flush_buffer_to_db()
                        with self._buffer_lock:
                            self.last_flush_time = current_time
                    
                except Exception as e:
                    print(f"数据库工作线程出错: {e}")
                    # 避免线程崩溃导致整个程序无响应
                    time.sleep(0.5)
        
        self.db_worker = threading.Thread(target=worker, daemon=True)
        self.db_worker.start()
    
    def flush_buffer_to_db(self):
        """将按键缓冲区写入数据库"""
        # 复制缓冲区并清空，减少锁的持有时间
        buffer_copy = {}
        with self._buffer_lock:
            if not self.key_buffer:
                return
            buffer_copy = self.key_buffer.copy()
            self.key_buffer.clear()
            
        if not buffer_copy:
            return
            
        try:
            # 使用独立连接和事务，避免阻塞其他操作
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                # 使用事务批量更新
                cursor.execute('BEGIN TRANSACTION')
                
                for key_name, count in buffer_copy.items():
                    # 使用UPSERT语法
                    cursor.execute('''
                        INSERT INTO key_stats (key_name, count) VALUES (?, ?)
                        ON CONFLICT(key_name) DO UPDATE SET count = count + ?
                    ''', (key_name, count, count))
                
                conn.commit()
            
        except Exception as e:
            print(f"写入数据库时出错: {e}")
            # 如果写入失败，恢复缓冲区
            with self._buffer_lock:
                for key, count in buffer_copy.items():
                    if key in self.key_buffer:
                        self.key_buffer[key] += count
                    else:
                        self.key_buffer[key] = count
    
    def on_press(self, key):
        """按键按下时的回调函数 (用于pynput)"""
        try:
            # 获取按键名称
            key_name = self.get_key_name(key)
            
            # 添加到队列，由工作线程处理
            if self.running:
                self.key_queue.put(key_name)
        except Exception as e:
            print(f"处理按键时出错: {e}")
    
    def get_key_name(self, key):
        """获取按键的友好名称 (用于pynput)"""
        try:
            # 处理数字键盘按键
            if isinstance(key, keyboard.KeyCode):
                # 检查是否为数字键盘按键
                vk = key.vk if hasattr(key, 'vk') else None
                if vk is not None and vk in self.numpad_mapping:
                    return self.numpad_mapping[vk]
                
                # 常规键盘字符
                if hasattr(key, 'char') and key.char is not None:
                    return key.char
                
                # 如果只有vk，尝试使用它
                if vk is not None:
                    return f"键码{vk}"
            
            # 处理特殊按键
            if isinstance(key, keyboard.Key):
                return key.name
            
            # 默认转换
            return str(key).replace("'", "")
        except:
            # 如果无法确定按键名称，返回原始表示
            return str(key)
    
    def on_release(self, key):
        """按键释放时的回调函数 (用于pynput)"""
        # 如果不再运行，则停止监听
        if not self.running:
            return False
    
    def start_tracking(self):
        """开始记录按键"""
        if not self.running:
            self.running = True
            self.start_time = datetime.now()
            self.status_var.set("状态: 正在记录...")
            
            # 使用pynput
            def start_listener():
                with keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release) as listener:
                    self.listener = listener
                    try:
                        listener.join()
                    except Exception as e:
                        print(f"监听器错误: {e}")
            
            # 确保之前的线程已经结束
            if self.listener_thread and self.listener_thread.is_alive():
                self.running = False
                if hasattr(self, 'listener') and self.listener:
                    self.listener.stop()
                self.listener_thread.join(timeout=1.0)
            
            self.listener_thread = threading.Thread(target=start_listener, daemon=True)
            self.listener_thread.start()
            
            # 更新UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_stats_display()
    
    def stop_tracking(self):
        """停止记录按键"""
        if self.running:
            self.running = False
            self.end_time = datetime.now()
            
            # 停止pynput监听器
            if hasattr(self, 'listener') and self.listener:
                try:
                    self.listener.stop()
                except:
                    pass
            
            # 确保线程正确停止（设置超时避免永久阻塞）
            if self.listener_thread and self.listener_thread.is_alive():
                try:
                    self.listener_thread.join(timeout=2.0)
                except:
                    pass
            
            # 强制刷新缓冲区
            self.flush_buffer_to_db()
            
            # 更新UI
            self.status_var.set("状态: 已停止")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_stats_display()
    
    def reset_data(self):
        """重置按键计数数据"""
        if messagebox.askyesno("确认重置", "确定要重置所有按键计数数据吗？"):
            try:
                # 确保停止记录
                was_running = self.running
                if was_running:
                    self.stop_tracking()
                
                # 清空内存中的计数
                with self._buffer_lock:
                    self.total_count = 0
                    self.key_buffer.clear()
                
                # 清空数据库表
                with self.get_db_connection() as conn:
                    conn.execute("DELETE FROM key_stats")
                    conn.commit()
                
                # 更新UI
                self.update_stats_display()
                messagebox.showinfo("重置完成", "按键计数数据已重置")
                
                # 如果之前在记录，则重新开始
                if was_running:
                    self.start_tracking()
            except Exception as e:
                print(f"重置数据时出错: {e}")
                messagebox.showerror("重置失败", f"重置数据时出错: {e}")
    
    def get_top_keys(self, limit=100):
        """获取按键点击次数最多的记录"""
        try:
            # 合并缓冲区中的数据和数据库中的数据
            with self._buffer_lock:
                buffer_copy = self.key_buffer.copy()
            
            results = {}
            
            # 从数据库获取记录
            with self.get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT key_name, count FROM key_stats 
                    ORDER BY count DESC LIMIT ?
                ''', (limit,))
                
                for key_name, count in cursor:
                    # 加上缓冲区中的计数
                    buffer_count = buffer_copy.pop(key_name, 0)
                    results[key_name] = count + buffer_count
            
            # 添加只在缓冲区中的键
            for key_name, count in buffer_copy.items():
                if key_name in results:
                    results[key_name] += count
                else:
                    results[key_name] = count
            
            # 返回排序后的结果
            return sorted(results.items(), key=lambda x: x[1], reverse=True)[:limit]
        except Exception as e:
            print(f"获取排名前列按键时出错: {e}")
            return []
    
    def update_stats_display(self):
        """更新统计显示，使用分页加载减少负担"""
        try:
            # 使用after_idle确保在主线程中执行UI更新
            self.root.after_idle(self._do_update_stats_display)
        except Exception as e:
            print(f"安排更新统计显示时出错: {e}")
    
    def _do_update_stats_display(self):
        """实际执行UI更新操作（在主线程）"""
        try:
            # 获取当前选择的行，以便更新后可以保持选择
            selected_items = self.tree.selection()
            selected_keys = []
            for item in selected_items:
                item_values = self.tree.item(item, 'values')
                if item_values:
                    selected_keys.append(item_values[0])
            
            # 清空现有项目
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # 加载前100个按键
            sorted_keys = self.get_top_keys(100)
            
            # 插入数据
            for i, (key_name, count) in enumerate(sorted_keys):
                self.tree.insert('', i, values=(key_name, count))
            
            # 尝试恢复之前的选择
            for key in selected_keys:
                for item in self.tree.get_children():
                    if self.tree.item(item, 'values')[0] == key:
                        self.tree.selection_add(item)
                        break
            
            # 更新总计
            self.total_var.set(f"总按键次数: {self.total_count}")
            
            # 更新运行时间
            if self.start_time:
                end = self.end_time if self.end_time else datetime.now()
                duration = end - self.start_time
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours}小时 {minutes}分钟 {seconds}秒"
                self.time_var.set(f"运行时间: {time_str}")
        except Exception as e:
            print(f"更新统计显示时出错: {e}")
    
    def export_data(self):
        """导出数据到CSV文件"""
        try:
            # 强制刷新缓冲区
            self.flush_buffer_to_db()
            
            filename = f"keyboard_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # 获取所有数据
            with self.get_db_connection() as conn:
                cursor = conn.execute('SELECT key_name, count FROM key_stats ORDER BY count DESC')
                rows = cursor.fetchall()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("按键,次数\n")
                for key_name, count in rows:
                    f.write(f"{key_name},{count}\n")
            messagebox.showinfo("导出成功", f"数据已导出至 {filename}")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出数据时出错: {e}")
    
    def open_about_page(self):
        """打开关于页面"""
        try:
            webbrowser.open(self.about_url)
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开网页: {e}")
    
    def create_gui(self):
        """创建图形用户界面"""
        self.root = tk.Tk()
        self.root.title("键盘使用统计")
        self.root.geometry("600x500")
        
        # 创建框架
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)
        
        stats_frame = ttk.Frame(self.root, padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控制按钮
        self.start_button = ttk.Button(control_frame, text="开始记录", command=self.start_tracking)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="停止记录", command=self.stop_tracking, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = ttk.Button(control_frame, text="重置数据", command=self.reset_data)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        self.export_button = ttk.Button(control_frame, text="导出CSV", command=self.export_data)
        self.export_button.pack(side=tk.LEFT, padx=5)
        
        # 添加关于按钮
        self.about_button = ttk.Button(control_frame, text="关于", command=self.open_about_page)
        self.about_button.pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        status_frame = ttk.Frame(self.root, padding=5)
        status_frame.pack(fill=tk.X)
        
        self.status_var = tk.StringVar(value="状态: 就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, padx=5)
        
        self.total_var = tk.StringVar(value="总按键次数: 0")
        total_label = ttk.Label(status_frame, textvariable=self.total_var)
        total_label.pack(side=tk.LEFT, padx=15)
        
        self.time_var = tk.StringVar(value="运行时间: 0小时 0分钟 0秒")
        time_label = ttk.Label(status_frame, textvariable=self.time_var)
        time_label.pack(side=tk.LEFT, padx=5)
        
        # 创建表格显示
        columns = ('key', 'count')
        self.tree = ttk.Treeview(stats_frame, columns=columns, show='headings')
        self.tree.heading('key', text='按键')
        self.tree.heading('count', text='次数')
        self.tree.column('key', width=100)
        self.tree.column('count', width=80)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 添加库信息标签
        lib_text = "使用pynput库 (可能无法捕获全屏游戏按键)"
        lib_label = ttk.Label(self.root, text=lib_text, foreground="gray")
        lib_label.pack(side=tk.BOTTOM, pady=5)
        
        # 添加数据库信息标签
        db_label = ttk.Label(self.root, text=f"使用SQLite数据库存储: {self.db_file}", foreground="gray")
        db_label.pack(side=tk.BOTTOM, pady=0)
        
        # 加载并显示现有数据
        self.update_stats_display()
        
        # 当窗口关闭时保存数据并停止记录
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化定时更新计数器
        self._update_counter = 0
    
    def on_closing(self):
        """窗口关闭时的处理函数"""
        # 停止按键记录
        if self.running:
            self.stop_tracking()
        
        # 停止工作线程
        self.worker_running = False
        
        # 刷新并等待队列清空
        try:
            self.flush_buffer_to_db()
            # 等待队列处理完成
            if hasattr(self, 'key_queue') and self.key_queue:
                try:
                    self.key_queue.join(timeout=2.0)
                except:
                    pass
        except:
            pass
        
        # 等待工作线程结束
        if hasattr(self, 'db_worker') and self.db_worker and self.db_worker.is_alive():
            try:
                self.db_worker.join(timeout=2.0)
            except:
                pass
        
        # 关闭数据库
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except:
            pass
        
        # 销毁窗口
        self.root.destroy()
    
    def periodic_update(self):
        """定期更新UI"""
        try:
            if not hasattr(self, 'root') or not self.root:
                return  # 如果窗口已经关闭，则不再继续
                
            if self.running:
                # 更新运行时间和总计数，这是比较轻量的操作
                if self.start_time:
                    end = datetime.now()
                    duration = end - self.start_time
                    hours, remainder = divmod(duration.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{hours}小时 {minutes}分钟 {seconds}秒"
                    self.time_var.set(f"运行时间: {time_str}")
                
                # 每10次更新才执行完整的统计更新，减少UI负担
                self._update_counter += 1
                if self._update_counter >= 10:
                    self._update_counter = 0
                    self.update_stats_display()
                else:
                    # 仅更新总计数
                    self.total_var.set(f"总按键次数: {self.total_count}")
            
            # 重新安排下一次更新
            self.root.after(2000, self.periodic_update)
        except Exception as e:
            print(f"定期更新UI时出错: {e}")
            # 发生错误时也要重新安排，确保更新不会中断
            self.root.after(2000, self.periodic_update)

    def run(self):
        """启动应用程序主循环"""
        # 开始定期更新UI
        self.root.after(2000, self.periodic_update)
        
        # 如果配置了自动开始，则启动记录
        if self.get_auto_start():
            self.start_tracking()
        
        # 启动主循环
        self.root.mainloop()
    
    def get_auto_start(self):
        """获取自动启动设置"""
        try:
            with self._db_lock:
                cursor = self.conn.execute('SELECT value FROM metadata WHERE key = "auto_start"')
                result = cursor.fetchone()
                if result:
                    return result[0].lower() == 'true'
            return False
        except Exception as e:
            print(f"获取自动启动设置时出错: {e}")
            return False
    
    def set_auto_start(self, auto_start):
        """设置自动启动"""
        try:
            value = 'true' if auto_start else 'false'
            with self._db_lock:
                self.conn.execute('''
                    INSERT INTO metadata (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = ?
                ''', ('auto_start', value, value))
                self.conn.commit()
            return True
        except Exception as e:
            print(f"设置自动启动时出错: {e}")
            return False

def main():
    """主函数"""
    try:
        # 创建并运行键盘跟踪器
        tracker = KeyboardTracker()
        tracker.run()
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
        messagebox.showerror("程序错误", f"程序运行时发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
