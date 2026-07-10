import tkinter as tk
from tkinter import ttk, scrolledtext
import random
import threading
import time
from dataclasses import dataclass
from typing import List, Dict
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from datetime import datetime

@dataclass
class Civilization:
    id: int
    alive: bool
    initial_development: int
    current_development: int
    
    def __str__(self):
        status = "存活" if self.alive else "灭绝"
        return f"文明{self.id}: {status}, 初始发达程度: {self.initial_development}, 当前发达程度: {self.current_development}"

@dataclass
class SimulationEvent:
    timestamp: str
    event_type: str  # "extinction", "merge", "development"
    description: str
    civilizations_involved: List[int]
    
    def __str__(self):
        return f"[{self.timestamp}] {self.description}"

class CivilizationSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("文明模拟器")
        self.root.geometry("1200x800")
        
        self.civilizations: List[Civilization] = []
        self.events: List[SimulationEvent] = []
        self.running = False
        self.simulation_thread = None
        self.step_counter = 0
        
        # 参数变量
        self.num_civilizations = tk.IntVar(value=10)
        self.time_interval = tk.DoubleVar(value=1.0)
        self.development_change_range = tk.IntVar(value=5)
        self.discovery_probability = tk.DoubleVar(value=0.1)
        self.advanced_destroy_probability = tk.DoubleVar(value=0.3)
        self.primitive_destroy_probability = tk.DoubleVar(value=0.05)
        self.merge_probability = tk.DoubleVar(value=0.2)
        self.merge_change_range = tk.IntVar(value=3)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 参数设置
        ttk.Label(control_frame, text="文明总数:").pack(anchor=tk.W)
        ttk.Spinbox(control_frame, from_=2, to=100, textvariable=self.num_civilizations, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="时间间隔(秒):").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=0.1, to=10.0, increment=0.1, textvariable=self.time_interval, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="发达程度变化范围:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=1, to=50, textvariable=self.development_change_range, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="发现概率:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=0.01, to=1.0, increment=0.01, textvariable=self.discovery_probability, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="高级文明消灭概率:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=0.01, to=1.0, increment=0.01, textvariable=self.advanced_destroy_probability, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="低级文明消灭概率:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=0.01, to=1.0, increment=0.01, textvariable=self.primitive_destroy_probability, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="融合概率:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=0.01, to=1.0, increment=0.01, textvariable=self.merge_probability, width=15).pack(pady=2)
        
        ttk.Label(control_frame, text="融合变化范围:").pack(anchor=tk.W, pady=(10,0))
        ttk.Spinbox(control_frame, from_=1, to=20, textvariable=self.merge_change_range, width=15).pack(pady=2)
        
        # 控制按钮
        ttk.Button(control_frame, text="初始化文明", command=self.initialize_civilizations).pack(pady=(20,5), fill=tk.X)
        ttk.Button(control_frame, text="开始模拟", command=self.start_simulation).pack(pady=5, fill=tk.X)
        ttk.Button(control_frame, text="停止模拟", command=self.stop_simulation).pack(pady=5, fill=tk.X)
        ttk.Button(control_frame, text="重置", command=self.reset_simulation).pack(pady=5, fill=tk.X)
        
        # 右侧显示区域
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 创建notebook用于切换显示
        self.notebook = ttk.Notebook(display_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 文本显示标签页
        text_frame = ttk.Frame(self.notebook)
        self.notebook.add(text_frame, text="文明状态")
        
        self.text_output = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=60, height=30)
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 事件记录标签页
        events_frame = ttk.Frame(self.notebook)
        self.notebook.add(events_frame, text="事件记录")
        
        # 事件记录工具栏
        events_toolbar = ttk.Frame(events_frame)
        events_toolbar.pack(fill=tk.X, padx=10, pady=(10,5))
        
        ttk.Button(events_toolbar, text="清空记录", command=self.clear_events).pack(side=tk.LEFT)
        ttk.Button(events_toolbar, text="导出记录", command=self.export_events).pack(side=tk.LEFT, padx=(10,0))
        
        # 事件过滤器
        ttk.Label(events_toolbar, text="筛选事件:").pack(side=tk.LEFT, padx=(20,5))
        self.event_filter = ttk.Combobox(events_toolbar, values=["全部", "灭绝事件", "融合事件", "发展变化"], width=12)
        self.event_filter.set("全部")
        self.event_filter.bind("<<ComboboxSelected>>", self.filter_events)
        self.event_filter.pack(side=tk.LEFT)
        
        self.events_output = scrolledtext.ScrolledText(events_frame, wrap=tk.WORD, width=60, height=25)
        self.events_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 统计信息标签页
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="统计信息")
        
        self.stats_output = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, width=60, height=30)
        self.stats_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 图表显示标签页
        chart_frame = ttk.Frame(self.notebook)
        self.notebook.add(chart_frame, text="发达程度图表")
        
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X, pady=(10,0))
        
    def initialize_civilizations(self):
        """初始化文明"""
        self.civilizations.clear()
        self.events.clear()
        self.step_counter = 0
        num_civs = self.num_civilizations.get()
        
        for i in range(num_civs):
            initial_dev = random.randint(0, num_civs)
            civ = Civilization(
                id=i,
                alive=True,
                initial_development=initial_dev,
                current_development=initial_dev
            )
            self.civilizations.append(civ)
        
        # 记录初始化事件
        self.add_event("initialization", f"初始化了 {num_civs} 个文明", list(range(num_civs)))
        
        self.update_display()
        self.status_var.set(f"已初始化 {num_civs} 个文明")
        
    def start_simulation(self):
        """开始模拟"""
        if not self.civilizations:
            self.status_var.set("请先初始化文明")
            return
            
        if not self.running:
            self.running = True
            self.simulation_thread = threading.Thread(target=self.simulation_loop, daemon=True)
            self.simulation_thread.start()
            self.status_var.set("模拟运行中...")
            
    def stop_simulation(self):
        """停止模拟"""
        self.running = False
        self.status_var.set("模拟已停止")
        
    def reset_simulation(self):
        """重置模拟"""
        self.stop_simulation()
        self.civilizations.clear()
        self.events.clear()
        self.step_counter = 0
        self.text_output.delete(1.0, tk.END)
        self.events_output.delete(1.0, tk.END)
        self.stats_output.delete(1.0, tk.END)
        self.ax.clear()
        self.canvas.draw()
        self.status_var.set("已重置")
        
    def simulation_loop(self):
        """模拟主循环"""
        while self.running:
            self.simulate_step()
            time.sleep(self.time_interval.get())
            
    def simulate_step(self):
        """执行一步模拟"""
        self.step_counter += 1
        alive_civs = [civ for civ in self.civilizations if civ.alive]
        
        if len(alive_civs) <= 1:
            self.running = False
            winner = alive_civs[0] if alive_civs else None
            if winner:
                self.add_event("simulation_end", f"模拟结束 - 文明{winner.id} 成为最后的幸存者！", [winner.id])
            else:
                self.add_event("simulation_end", "模拟结束 - 所有文明都已灭绝", [])
            self.root.after(0, lambda: self.status_var.set("模拟结束"))
            return
            
        # 记录每步开始
        if self.step_counter % 10 == 1:  # 每10步记录一次
            alive_count = len(alive_civs)
            self.add_event("development", f"第{self.step_counter}步: {alive_count}个文明仍在发展", [civ.id for civ in alive_civs])
            
        # 1. 文明发达程度随机变化
        development_changes = []
        for civ in alive_civs:
            old_dev = civ.current_development
            change = random.randint(-self.development_change_range.get(), self.development_change_range.get())
            civ.current_development = max(0, civ.current_development + change)
            
            # 记录显著的发展变化
            if abs(change) >= self.development_change_range.get() // 2:
                direction = "大幅提升" if change > 0 else "急剧衰退"
                development_changes.append(f"文明{civ.id}{direction}(变化{change:+d})")
                
        if development_changes:
            self.add_event("development", f"发展变化: {', '.join(development_changes)}", 
                          [civ.id for civ in alive_civs if abs(civ.current_development - civ.initial_development) >= self.development_change_range.get() // 2])
            
        # 2. 文明间的相互作用
        for i, civ1 in enumerate(alive_civs):
            for j, civ2 in enumerate(alive_civs):
                if i >= j or not civ1.alive or not civ2.alive:
                    continue
                    
                # 检查是否发现对方
                if random.random() < self.discovery_probability.get():
                    self.handle_civilization_encounter(civ1, civ2)
                    
        # 更新显示
        self.root.after(0, self.update_display)
        
    def handle_civilization_encounter(self, civ1: Civilization, civ2: Civilization):
        """处理文明相遇"""
        if not civ1.alive or not civ2.alive:
            return
            
        # 确定哪个文明更发达
        if civ1.current_development > civ2.current_development:
            advanced, primitive = civ1, civ2
        elif civ2.current_development > civ1.current_development:
            advanced, primitive = civ2, civ1
        else:
            # 发达程度相同，随机选择
            advanced, primitive = random.choice([(civ1, civ2), (civ2, civ1)])
            
        encounter_roll = random.random()
        
        # 融合
        if encounter_roll < self.merge_probability.get():
            self.merge_civilizations(advanced, primitive)
        # 高级文明消灭低级文明
        elif encounter_roll < self.merge_probability.get() + self.advanced_destroy_probability.get():
            primitive.alive = False
            self.add_event("extinction", 
                          f"高级文明{advanced.id}(发达程度{advanced.current_development}) 消灭了低级文明{primitive.id}(发达程度{primitive.current_development})", 
                          [advanced.id, primitive.id])
        # 低级文明消灭高级文明（小概率事件）
        elif encounter_roll < (self.merge_probability.get() + 
                              self.advanced_destroy_probability.get() + 
                              self.primitive_destroy_probability.get()):
            advanced.alive = False
            self.add_event("extinction", 
                          f"低级文明{primitive.id}(发达程度{primitive.current_development}) 奇迹般地消灭了高级文明{advanced.id}(发达程度{advanced.current_development})", 
                          [primitive.id, advanced.id])
            
    def merge_civilizations(self, civ1: Civilization, civ2: Civilization):
        """融合两个文明"""
        old_dev1, old_dev2 = civ1.current_development, civ2.current_development
        
        # 新的发达程度 = 两者之和 + 随机变化
        base_development = civ1.current_development + civ2.current_development
        change = random.randint(-self.merge_change_range.get(), self.merge_change_range.get())
        new_development = max(0, base_development + change)
        
        # 保留ID较小的文明，更新其属性
        if civ1.id < civ2.id:
            survivor, absorbed = civ1, civ2
        else:
            survivor, absorbed = civ2, civ1
            
        survivor.current_development = new_development
        absorbed.alive = False
        
        self.add_event("merge", 
                      f"文明{survivor.id}(发达程度{old_dev1}) 和文明{absorbed.id}(发达程度{old_dev2}) 融合成新文明{survivor.id}(发达程度{new_development}, 变化{change:+d})", 
                      [survivor.id, absorbed.id])
        
    def add_event(self, event_type: str, description: str, civilizations_involved: List[int]):
        """添加事件记录"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        event = SimulationEvent(
            timestamp=timestamp,
            event_type=event_type,
            description=description,
            civilizations_involved=civilizations_involved
        )
        self.events.append(event)
        
        # 实时更新事件显示
        def update_events():
            self.events_output.insert(tk.END, str(event) + "\n")
            self.events_output.see(tk.END)
        self.root.after(0, update_events)
        
    def clear_events(self):
        """清空事件记录"""
        self.events.clear()
        self.events_output.delete(1.0, tk.END)
        
    def export_events(self):
        """导出事件记录"""
        filename = f"civilization_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("文明模拟器事件记录\n")
                f.write("=" * 50 + "\n\n")
                for event in self.events:
                    f.write(str(event) + "\n")
            self.status_var.set(f"事件记录已导出到 {filename}")
        except Exception as e:
            self.status_var.set(f"导出失败: {str(e)}")
            
    def filter_events(self, event=None):
        """筛选事件显示"""
        filter_type = self.event_filter.get()
        self.events_output.delete(1.0, tk.END)
        
        for event in self.events:
            show_event = False
            if filter_type == "全部":
                show_event = True
            elif filter_type == "灭绝事件" and event.event_type == "extinction":
                show_event = True
            elif filter_type == "融合事件" and event.event_type == "merge":
                show_event = True
            elif filter_type == "发展变化" and event.event_type == "development":
                show_event = True
                
            if show_event:
                self.events_output.insert(tk.END, str(event) + "\n")
                
    def update_statistics(self):
        """更新统计信息"""
        self.stats_output.delete(1.0, tk.END)
        
        # 基本统计
        total_civs = len(self.civilizations)
        alive_civs = [civ for civ in self.civilizations if civ.alive]
        dead_civs = [civ for civ in self.civilizations if not civ.alive]
        
        self.stats_output.insert(tk.END, "=== 文明统计 ===\n")
        self.stats_output.insert(tk.END, f"总文明数: {total_civs}\n")
        self.stats_output.insert(tk.END, f"存活文明数: {len(alive_civs)}\n")
        self.stats_output.insert(tk.END, f"灭绝文明数: {len(dead_civs)}\n")
        self.stats_output.insert(tk.END, f"存活率: {len(alive_civs)/total_civs*100:.1f}%\n\n")
        
        if alive_civs:
            developments = [civ.current_development for civ in alive_civs]
            self.stats_output.insert(tk.END, "=== 存活文明发达程度统计 ===\n")
            self.stats_output.insert(tk.END, f"平均发达程度: {sum(developments)/len(developments):.1f}\n")
            self.stats_output.insert(tk.END, f"最高发达程度: {max(developments)} (文明{alive_civs[developments.index(max(developments))].id})\n")
            self.stats_output.insert(tk.END, f"最低发达程度: {min(developments)} (文明{alive_civs[developments.index(min(developments))].id})\n\n")
        
        # 事件统计
        extinction_events = [e for e in self.events if e.event_type == "extinction"]
        merge_events = [e for e in self.events if e.event_type == "merge"]
        
        self.stats_output.insert(tk.END, "=== 事件统计 ===\n")
        self.stats_output.insert(tk.END, f"总事件数: {len(self.events)}\n")
        self.stats_output.insert(tk.END, f"灭绝事件: {len(extinction_events)}\n")
        self.stats_output.insert(tk.END, f"融合事件: {len(merge_events)}\n")
        self.stats_output.insert(tk.END, f"模拟步数: {self.step_counter}\n\n")
        
        # 最活跃的文明
        if self.events:
            civ_activity = {}
            for event in self.events:
                for civ_id in event.civilizations_involved:
                    civ_activity[civ_id] = civ_activity.get(civ_id, 0) + 1
                    
            if civ_activity:
                most_active = max(civ_activity.items(), key=lambda x: x[1])
                self.stats_output.insert(tk.END, f"最活跃文明: 文明{most_active[0]} (参与{most_active[1]}次事件)\n")
                
        # 详细的存活文明信息
        if alive_civs:
            self.stats_output.insert(tk.END, "\n=== 存活文明详情 ===\n")
            for civ in sorted(alive_civs, key=lambda x: x.current_development, reverse=True):
                growth = civ.current_development - civ.initial_development
                growth_str = f"(成长{growth:+d})" if growth != 0 else "(无变化)"
                self.stats_output.insert(tk.END, f"文明{civ.id}: 当前{civ.current_development}, 初始{civ.initial_development} {growth_str}\n")
        
    def update_display(self):
        """更新显示"""
        # 更新文本显示
        self.text_output.delete(1.0, tk.END)
        alive_count = 0
        
        for civ in self.civilizations:
            self.text_output.insert(tk.END, str(civ) + "\n")
            if civ.alive:
                alive_count += 1
                
        self.text_output.insert(tk.END, f"\n存活文明数量: {alive_count}\n")
        
        # 更新图表
        self.update_chart()
        
        # 更新统计信息
        self.update_statistics()
        
    def update_chart(self):
        """更新图表显示"""
        self.ax.clear()
        
        alive_civs = [civ for civ in self.civilizations if civ.alive]
        dead_civs = [civ for civ in self.civilizations if not civ.alive]
        
        if alive_civs:
            alive_ids = [civ.id for civ in alive_civs]
            alive_developments = [civ.current_development for civ in alive_civs]
            self.ax.bar(alive_ids, alive_developments, color='green', alpha=0.7, label='存活文明')
            
        if dead_civs:
            dead_ids = [civ.id for civ in dead_civs]
            dead_developments = [civ.current_development for civ in dead_civs]
            self.ax.bar(dead_ids, dead_developments, color='red', alpha=0.7, label='灭绝文明')
            
        self.ax.set_xlabel('文明编号')
        self.ax.set_ylabel('发达程度')
        self.ax.set_title('文明发达程度分布')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        self.canvas.draw()

def main():
    root = tk.Tk()
    app = CivilizationSimulator(root)
    root.mainloop()

if __name__ == "__main__":
    main()