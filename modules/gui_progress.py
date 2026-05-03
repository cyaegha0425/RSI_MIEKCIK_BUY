#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.2 咩咩Kick!
GUI进度界面模块
"""

import os
import queue
import time
from datetime import datetime

from . import config

# 导入config中的常量
CFG = config.CFG
GUI_BG_COLOR = config.GUI_BG_COLOR
GUI_TITLE_COLOR = config.GUI_TITLE_COLOR
GUI_TEXT_COLOR = config.GUI_TEXT_COLOR
GUI_BG_DARK = config.GUI_BG_DARK
# 延迟获取args，避免PyInstaller导入时触发parse_args
def _get_args():
    return config.get_args()
log = config.log


# ============================================================
# GUI 进度界面 (tkinter)
# ============================================================

class RSIGUI:
    """咩咩Kick! V3.0.2 咩咩Kick! - 进度GUI，非阻塞显示层"""
    
    def __init__(self, target_time: str, mode_label: str = "[正面硬刚]"):
        if _get_args().no_gui:
            self.enabled = False
            return
        
        self.enabled = True
        self.target_time = target_time
        self.mode_label = mode_label
        self.root = None
        self.countdown_label = None
        self.step_labels = {}
        self.log_text = None
        self._running = True
        self._result = None  # None=进行中, True=成功, False=失败
        self._cancel_clicked = False  # 取消按钮是否被点击
        self._result_confirmed = False  # 结果弹窗是否已确认
        self.cancel_btn = None
        self.status_label = None
        self._gui_thread = None  # 保存GUI线程引用
        self._quit_requested = False  # 主线程请求退出标记
        self._gui_queue = queue.Queue()  # GUI消息队列（线程安全）
        self._after_ids = []  # 跟踪所有after回调ID，退出时统一取消
        
        # 步骤定义 - V2.0.0 新流程
        self.steps = [
            ("calibrate", "时间校准..."),
            ("wait", "等待抢购时间..."),
            ("login", "登录验证..."),
            ("warmup", "预热加载..."),
            ("cart", "加入购物车..."),
            ("checkout", "极速结账..."),
            ("done", "完成！"),
        ]
        # 伏击模式步骤
        self.ambush_steps = [
            ("ambush", "伏击预装填..."),
            ("wait", "等待T-0卡点..."),
            ("checkout", "T-0验证..."),
            ("done", "完成！"),
        ]
        
        self._start_gui_thread()
    
    def _start_gui_thread(self):
        """启动GUI（不启动子线程，由主线程调用run_mainloop）"""
        pass
    
    def run_mainloop(self):
        """在主线程运行GUI mainloop（tkinter要求mainloop在主线程）"""
        self._gui_loop()
    
    def stop_mainloop(self):
        """从外部请求停止mainloop"""
        self._quit_requested = True
    
    def _gui_loop(self):
        """GUI主循环"""
        try:
            import tkinter as tk
            from tkinter import scrolledtext
            from PIL import Image, ImageTk
            
            # 进度窗口背景色常量
            PROGRESS_BG_COLOR = GUI_BG_COLOR  # 小底色条颜色（浅蓝灰白）
            
            self.root = tk.Tk()
            mode_suffix = getattr(self, 'mode_label', '[正面硬刚]')
            self.root.title(f"咩咩蹄到好船来 V3.0.2 咩咩KICK！ {mode_suffix}")
            self.root.geometry("546x683")  # 竖版4:5比例
            self.root.resizable(False, False)
            self.root.attributes('-topmost', True)
            # 根窗口不设实色bg，让背景图显示
            
            # 尝试加载背景图 gui_bg.png
            self._bg_image = None
            try:
                bg_img_path = config.resource_path('gui_bg.png')
                if os.path.exists(bg_img_path):
                    bg_img = Image.open(bg_img_path)
                    bg_img = bg_img.resize((546, 683), Image.Resampling.LANCZOS)
                    self._bg_image = ImageTk.PhotoImage(bg_img, master=self.root)
            except Exception as e:
                print(f"背景图加载失败: {e}")
            
            # 背景图作为底层全窗口显示
            if self._bg_image:
                bg_label = tk.Label(self.root, image=self._bg_image)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            
            # ===== 标题（用place直接放在root上） =====
            title_label = tk.Label(
                self.root, text="咩咩蹄到好船来 V3.0.2 咩咩KICK！", 
                font=("Microsoft YaHei UI", 14, "bold"),
                fg="#1a3a5c", bg=PROGRESS_BG_COLOR, padx=6, pady=2
            )
            title_label.place(relx=0.5, y=15, anchor='n')
            
            # ===== 副标题 =====
            subtitle_label = tk.Label(
                self.root, text="抢光CIG的机库", 
                font=("Microsoft YaHei UI", 9),
                fg=GUI_TEXT_COLOR, bg=PROGRESS_BG_COLOR, padx=6, pady=1
            )
            subtitle_label.place(relx=0.5, y=45, anchor='n')
            
            # ===== 作者署名（右下角，使用背景色无底色） =====
            author_label = tk.Label(
                self.root, text="by 咩咩莉娅",
                font=("Microsoft YaHei UI", 8),
                fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR
            )
            author_label.place(relx=1.0, rely=1.0, x=-5, y=-5, anchor='se')
            
            # ===== 倒计时标签套小Frame底色 =====
            countdown_frame = tk.Frame(self.root, bg=PROGRESS_BG_COLOR, padx=4, pady=2)
            countdown_frame.place(relx=0.5, y=70, anchor='n')
            
            self.countdown_label = tk.Label(
                countdown_frame, text="初始化中...",
                font=("Microsoft YaHei UI", 13),
                fg="#f9e2af", bg=PROGRESS_BG_COLOR
            )
            self.countdown_label.pack()
            
            # ===== 状态标签套小Frame底色 =====
            status_frame = tk.Frame(self.root, bg=PROGRESS_BG_COLOR, padx=4, pady=1)
            status_frame.place(relx=0.5, y=100, anchor='n')
            
            self.status_label = tk.Label(
                status_frame, text="⏳ 等待开始",
                font=("Microsoft YaHei UI", 10),
                fg="#a6e3a1", bg=PROGRESS_BG_COLOR
            )
            self.status_label.pack()
            
            # ===== 取消抢购按钮（窗口底部，暗玫红，用lift确保不被遮挡） =====
            self.cancel_btn = tk.Button(
                self.root, text="取消抢购",
                font=("Microsoft YaHei UI", 10, "bold"),
                fg="white", bg="#9E6B7A", relief='flat',
                padx=15, pady=5, cursor='hand2',
                command=self._on_cancel_clicked
            )
            self.cancel_btn.place(relx=0.5, y=480, anchor='n')
            
            # ===== 步骤列表套小Frame底色 =====
            self.steps_container = tk.Frame(self.root, bg=PROGRESS_BG_COLOR, padx=6, pady=3)
            self.steps_container.place(relx=0.5, y=165, anchor='n')
            
            for key, name in self.steps:
                row = tk.Frame(self.steps_container, bg=PROGRESS_BG_COLOR)
                row.pack(anchor='w', pady=1)
                
                # 状态图标
                status_icon = tk.Label(
                    row, text="⏳", width=3,
                    font=("Segoe UI Emoji", 10),
                    fg=GUI_TEXT_COLOR, bg=PROGRESS_BG_COLOR
                )
                status_icon.pack(side='left')
                
                # 步骤名称
                name_label = tk.Label(
                    row, text=name,
                    font=("Microsoft YaHei UI", 10),
                    fg=GUI_TEXT_COLOR, bg=PROGRESS_BG_COLOR
                )
                name_label.pack(side='left')
                
                self.step_labels[key] = status_icon
            
            # 白屏提示（步骤列表和取消按钮之间）
            hint_label = tk.Label(
                self.root, text="💡 如浏览器白屏且无URL，请关闭当前窗口重试",
                font=("Microsoft YaHei UI", 8),
                fg="#9399B2", bg=PROGRESS_BG_COLOR
            )
            hint_label.place(relx=0.5, y=440, anchor='n')
            
            # 确保取消按钮在步骤容器上层（不被遮挡）
            self.cancel_btn.lift()
            
            # 更新倒计时
            self._update_countdown()
            
            # 合并的poll：处理GUI队列 + 检查退出
            def _poll_queue():
                if not self._running or self._quit_requested:
                    self._cancel_all_after()
                    try:
                        self.root.quit()
                    except:
                        pass
                    return
                # 批量处理queue中的所有消息
                try:
                    for _ in range(50):  # 每次最多处理50条，防止无限循环
                        try:
                            msg_type, msg_data = self._gui_queue.get_nowait()
                        except queue.Empty:
                            break
                        self._handle_gui_message(msg_type, msg_data)
                except Exception as e:
                    pass  # mainloop退出后回调可能残留，静默忽略
                try:
                    if self._running and self.root:
                        self._after_ids.append(self.root.after(50, _poll_queue))
                except:
                    pass
            self._after_ids.append(self.root.after(50, _poll_queue))
            
            self.root.mainloop()
            # mainloop退出后，清理残留after回调防止Tcl报invalid command
            self._cancel_all_after()
            try:
                self.root.update()  # 让Tcl处理完残留事件
            except:
                pass
        except Exception as e:
            print(f"GUI启动失败: {e}")
            self.enabled = False
    
    def _on_cancel_clicked(self):
        """取消按钮点击"""
        self._cancel_clicked = True
        self._running = False
        self._result_confirmed = True
        log.info("⚠️ 用户点击取消抢购")
        # 取消所有after回调后退出mainloop
        self._cancel_all_after()
        try:
            self.root.quit()
        except:
            pass
    
    def is_cancel_clicked(self):
        """检查是否点击了取消"""
        return self._cancel_clicked
    
    def is_result_confirmed(self):
        """检查结果弹窗是否已确认"""
        return self._result_confirmed
    
    def show_cancel_button(self):
        """显示取消按钮（进度窗口取消按钮已初始显示，无需此方法）"""
        pass
    
    def close_and_return_to_config(self):
        """关闭进度窗口，准备回配置界面（线程安全：通过queue）"""
        self._running = False
        self._cancel_clicked = True
        self._result_confirmed = True
        self._gui_queue.put(("quit", None))
    
    def _handle_gui_message(self, msg_type, msg_data):
        """在主线程处理GUI消息（由_poll_queue调用）"""
        try:
            if msg_type == "update_status":
                status, key = msg_data
                if self.status_label:
                    self.status_label.config(text=f"⏳ {status}")
                if key and key in self.step_labels:
                    self.step_labels[key].config(text="▶", fg="#f9e2af")
            
            elif msg_type == "update_step":
                key, success = msg_data
                icon = "✅" if success else "❌"
                color = "#a6e3a1" if success else "#f38ba8"
                if key in self.step_labels:
                    self.step_labels[key].config(text=icon, fg=color)
                keys = [k for k, _ in self.steps]
                if key in keys:
                    idx = keys.index(key)
                    if idx + 1 < len(keys):
                        next_key = keys[idx + 1]
                        if next_key in self.step_labels:
                            self.step_labels[next_key].config(text="⏳", fg=GUI_TEXT_COLOR)
            
            elif msg_type == "update_calibration":
                offset, is_manual = msg_data
                offset_text = f"+{offset:.3f}" if offset >= 0 else f"{offset:.3f}"
                if self.status_label:
                    if is_manual:
                        self.status_label.config(text=f"🕐 手动偏移: {offset_text}秒", fg="#89B4FA")
                    else:
                        self.status_label.config(text=f"🕐 自动校准: {offset_text}秒", fg="#89B4FA")
            
            elif msg_type == "show_result":
                success, msg = msg_data
                self._result = success
                if success:
                    self.status_label.config(text="🎉 好船来啦！不愧是我！", fg="#1a3a5c")
                else:
                    self.status_label.config(text="❌ 咩失前蹄啦！", fg="#f38ba8")
                self._show_result_dialog(success, msg)
            
            elif msg_type == "quit":
                self._running = False
                self._result_confirmed = True
                self._cancel_all_after()
                try:
                    self.root.quit()
                except:
                    pass
            
            elif msg_type == "clear_cart":
                event = msg_data
                self._show_clear_cart_dialog(event)
        
        except Exception as e:
            print(f"GUI message handler error: {e}")
    
    def _cancel_all_after(self):
        """取消所有已注册的after回调，防止mainloop退出后Tcl报错"""
        for aid in self._after_ids:
            try:
                self.root.after_cancel(aid)
            except:
                pass
        self._after_ids.clear()
    
    def _show_clear_cart_dialog(self, event):
        """在主线程显示清空购物车确认弹窗"""
        try:
            import tkinter as tk
            dialog = tk.Toplevel(self.root)
            dialog.title("⚠️ 清空购物车")
            dialog.geometry("400x200")
            dialog.attributes('-topmost', True)
            dialog.transient(self.root)
            dialog.grab_set()
            
            frame = tk.Frame(dialog, bg=GUI_BG_COLOR, padx=20, pady=20)
            frame.pack(fill='both', expand=True)
            
            tk.Label(frame, text="请确认已清空购物车！", 
                     font=("Microsoft YaHei UI", 12, "bold"),
                     fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack(pady=15)
            
            tk.Label(frame, text="购物车中有其他商品可能导致购买失败",
                     font=("Microsoft YaHei UI", 9),
                     fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack(pady=5)
            
            def on_confirm():
                event.set()
                try:
                    dialog.destroy()
                except:
                    pass
            
            tk.Button(frame, text="已清空，继续", font=("Microsoft YaHei UI", 10, "bold"),
                      fg="white", bg="#7B8FB7", relief='flat', padx=20, pady=8,
                      command=on_confirm).pack(pady=15)
            
            dialog.protocol("WM_DELETE_WINDOW", on_confirm)
        except Exception as e:
            print(f"清空购物车弹窗失败: {e}")
            event.set()
    
    def _update_countdown(self):
        """更新倒计时显示"""
        if not self.enabled or not self.countdown_label or not self._running:
            return
        
        try:
            from datetime import timedelta
            from calendar import timegm
            tz_offset = timedelta(hours=8)
            local_dt = datetime.strptime(self.target_time, "%Y-%m-%d %H:%M:%S")
            target_ts = timegm((local_dt - tz_offset).timetuple())
            now_ts = time.time()
            diff = target_ts - now_ts
            
            if diff > 0:
                hours = int(diff // 3600)
                mins = int((diff % 3600) // 60)
                secs = int(diff % 60)
                ms = int((diff % 1) * 1000)
                
                if hours > 0:
                    text = f"⏰ 距抢购: {hours}小时 {mins}分 {secs}秒"
                elif mins > 0:
                    text = f"⏰ 距抢购: {mins}分 {secs}.{ms:03d}秒"
                else:
                    text = f"⏰ 距抢购: {secs}.{ms:03d}秒"
                
                self.countdown_label.config(text=text, fg="#1a3a5c")
            else:
                elapsed = abs(diff)
                self.countdown_label.config(
                    text=f"🔥 抢购进行中 (已过 {elapsed:.1f}秒)", 
                    fg="#f38ba8"
                )
            
            # 继续更新
            if self._running:
                try:
                    if self.root:
                        self._after_ids.append(self.root.after(50, self._update_countdown))
                except:
                    pass
        except:
            pass
    
    def update_status(self, status: str, key: str = None):
        """更新当前状态（线程安全：通过queue）"""
        if not self.enabled or not self._running:
            return
        self._gui_queue.put(("update_status", (status, key)))
    
    def update_step(self, key: str, success: bool):
        """更新步骤状态（线程安全：通过queue）"""
        if not self.enabled or not self._running:
            return
        self._gui_queue.put(("update_step", (key, success)))
    
    def update_calibration(self, offset: float, is_manual: bool = False):
        """显示时间校准结果（线程安全：通过queue）"""
        if not self.enabled:
            return
        self._gui_queue.put(("update_calibration", (offset, is_manual)))
    
    def show_result(self, success: bool, msg: str = None):
        """显示结果弹窗（线程安全：通过queue）"""
        if not self.enabled:
            return
        self._gui_queue.put(("show_result", (success, msg)))
    
    def _show_result_dialog(self, success: bool, msg: str):
        """显示结果对话框"""
        try:
            import tkinter as tk
            from PIL import Image, ImageTk
            
            DIALOG_BG_COLOR = GUI_BG_COLOR  # 小底色条颜色（浅蓝灰白）
            
            # 创建顶层窗口
            dialog = tk.Toplevel(self.root)
            dialog.title("🎉 抢购结果" if success else "❌ 抢购结果")
            dialog.geometry("560x400")
            dialog.attributes('-topmost', True)
            
            # 居中
            dialog.transient(self.root)
            dialog.grab_set()
            
            # 尝试加载背景图
            self._result_bg_image = None
            try:
                if success:
                    bg_img_path = config.resource_path('gui_bg_success.png')
                else:
                    bg_img_path = config.resource_path('gui_bg_fail.png')
                if os.path.exists(bg_img_path):
                    bg_img = Image.open(bg_img_path)
                    bg_img = bg_img.resize((560, 400), Image.Resampling.LANCZOS)
                    self._result_bg_image = ImageTk.PhotoImage(bg_img, master=dialog)
            except Exception:
                self._result_bg_image = None
            
            # 背景图作为底层全窗口显示
            if self._result_bg_image:
                bg_label = tk.Label(dialog, image=self._result_bg_image)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            else:
                dialog.configure(bg=DIALOG_BG_COLOR)
            
            # 标题颜色
            if success:
                title_text = "🎉 好船来啦！Nice Boat!"
                title_color = "#1a3a5c"
            else:
                title_text = "❌ 咩咩Kick！失败，下次一定！"
                title_color = "#f38ba8"
            
            # ===== 标题套小Frame底色（靠右，紧凑间距） =====
            title_frame = tk.Frame(dialog, bg=DIALOG_BG_COLOR, padx=6, pady=3)
            title_frame.place(relx=0.83, rely=0.28, anchor='e')
            
            title = tk.Label(
                title_frame, text=title_text,
                font=("Microsoft YaHei UI", 18, "bold"),
                fg=title_color, bg=DIALOG_BG_COLOR
            )
            title.pack()
            
            # ===== 消息（跟标题同字体同颜色） =====
            if msg:
                msg_frame = tk.Frame(dialog, bg=DIALOG_BG_COLOR, padx=6, pady=3)
                msg_frame.place(relx=0.85, rely=0.52, anchor='e')
                
                msg_label = tk.Label(
                    msg_frame, text=msg,
                    font=("Microsoft YaHei UI", 18, "bold"),
                    fg=title_color, bg=DIALOG_BG_COLOR
                )
                msg_label.pack()
            
            # ===== 确定按钮（中暗蓝，靠右，紧凑间距） =====
            def on_confirm():
                self._result_confirmed = True
                self._running = False
                try:
                    dialog.destroy()
                except:
                    pass
                # mainloop在主线程，quit()直接退出mainloop即可
                try:
                    self.root.quit()
                except:
                    pass
            
            btn = tk.Button(
                dialog, text="确定",
                font=("Microsoft YaHei UI", 11, "bold"),
                fg="white", bg="#7B8FB7",
                activebackground="#6A8CBA",
                relief='flat', padx=25, pady=8, cursor='hand2',
                command=on_confirm
            )
            btn.place(relx=0.85, rely=0.72, anchor='e')
            
            # 点X也关闭弹窗
            dialog.protocol("WM_DELETE_WINDOW", on_confirm)
            
        except Exception as e:
            print(f"结果弹窗失败: {e}")
    
    def destroy(self):
        """关闭GUI（线程安全：通过queue）"""
        if self.enabled and self._running:
            self._running = False
            self._gui_queue.put(("quit", None))
