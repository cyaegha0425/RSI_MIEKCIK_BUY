#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.4
配置窗口模块 - 包含配置对话框、清空购物车弹窗、配置读写
"""

import os
import json
import subprocess
import threading
from datetime import datetime

from . import config

# 导入config中的常量
CFG = config.CFG
GUI_TEXT_COLOR = config.GUI_TEXT_COLOR
GUI_TITLE_COLOR = config.GUI_TITLE_COLOR
GUI_BG_DARK = config.GUI_BG_DARK
GUI_BG_COLOR = config.GUI_BG_COLOR
log = config.log


# ============================================================
# 通用UI工具函数（模块级，供多个弹窗共用）
# ============================================================

def _show_tooltip(widget, text):
    """显示tooltip提示"""
    import tkinter as tk
    def on_enter(event):
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.attributes('-topmost', True)
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tooltip, text=text, bg="#313244", fg="white",
                         font=("Microsoft YaHei UI", 11), padx=12, pady=10,
                         justify="left", relief="solid", borderwidth=1)
        label.pack()
    def on_leave(event):
        for w in widget.winfo_children():
            if isinstance(w, tk.Toplevel):
                w.destroy()
    widget.bind('<Enter>', on_enter)
    widget.bind('<Leave>', on_leave)


def _create_help_button(parent, help_text):
    """创建❓帮助按钮"""
    import tkinter as tk
    btn = tk.Label(parent, text="❓", font=("Microsoft YaHei UI", 11),
                  fg="#555555", bg=GUI_BG_COLOR, cursor='hand2')
    _show_tooltip(btn, help_text)
    return btn


# ============================================================
# 配置保存/加载函数
# ============================================================

def _load_saved_config():
    """加载保存的配置"""
    config_file = os.path.join(config.BASE_PATH, "scautobuy", "rsi_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None

def _save_config(data):
    """保存配置"""
    config_file = os.path.join(config.BASE_PATH, "scautobuy", "rsi_config.json")
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


# ============================================================
# 清空购物车弹窗 (630x480)
# ============================================================

def _show_clear_cart_dialog(gui, _clear_cart_event):
    """显示清空购物车确认对话框（在GUI线程中调用）"""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
        
        dialog = tk.Toplevel(gui.root)
        dialog.title("⚠️ 温馨提示")
        dialog.geometry("630x480")
        dialog.attributes('-topmost', True)
        dialog.transient(gui.root)
        dialog.grab_set()
        
        # 尝试加载背景图
        cart_bg_image = None
        try:
            bg_img_path = config.resource_path('gui_bg.png')
            if os.path.exists(bg_img_path):
                bg_img = Image.open(bg_img_path)
                bg_img = bg_img.resize((630, 480), Image.Resampling.LANCZOS)
                cart_bg_image = ImageTk.PhotoImage(bg_img, master=dialog)
        except:
            pass
        
        # 背景图作为底层全窗口显示
        if cart_bg_image:
            bg_label = tk.Label(dialog, image=cart_bg_image)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        
        # 标题居中
        title_frame = tk.Frame(dialog, bg=GUI_BG_COLOR, padx=6, pady=3)
        title_frame.place(relx=0.5, rely=0.3, anchor='center')
        
        title = tk.Label(
            title_frame, text="⚠️ 请清空购物车",
            font=("Microsoft YaHei UI", 24, "bold"),
            fg="#1a3a5c", bg=GUI_BG_COLOR
        )
        title.pack()
        
        # 说明居中
        desc_frame = tk.Frame(dialog, bg=GUI_BG_COLOR, padx=6, pady=3)
        desc_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        desc = tk.Label(
            desc_frame, text="请在浏览器中清空购物车后\n点击下方确认按钮继续",
            font=("Microsoft YaHei UI", 16),
            fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR
        )
        desc.pack()
        
        def on_confirm():
            _clear_cart_event.set()
            dialog.destroy()
        
        # 确认按钮（居中）
        btn = tk.Button(
            dialog, text="我已清空，确认继续",
            font=("Microsoft YaHei UI", 14, "bold"),
            fg="white", bg="#7B8FB7",
            activebackground="#6A8CBA",
            relief='flat', padx=30, pady=12, cursor='hand2',
            command=on_confirm
        )
        btn.place(relx=0.5, rely=0.75, anchor='center')
        
        dialog.protocol("WM_DELETE_WINDOW", on_confirm)
        dialog.wait_window(dialog)
    except:
        _clear_cart_event.set()  # 出错时也要设置，避免卡死


# ============================================================
# 高级设置弹窗 (570x450)
# ============================================================

def _show_advanced_settings_dialog(parent, current_manual_offset="-0.1", current_auto_calibrate=False, current_proxy=""):
    """显示高级设置对话框"""
    import tkinter as tk

    dialog = tk.Toplevel(parent)
    dialog.title("高级设置")
    dialog.geometry("570x480")
    dialog.attributes('-topmost', True)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)

    # 背景色
    dialog.configure(bg=GUI_BG_COLOR)

    # 主容器（用于pack布局）
    container = tk.Frame(dialog, bg=GUI_BG_COLOR)
    container.pack(fill='both', expand=True)

    # ========== 1. 标题 ==========
    title_frame = tk.Frame(container, bg=GUI_BG_COLOR)
    title_frame.pack(pady=(18, 6))
    tk.Label(title_frame, text="高级设置", font=("Microsoft YaHei UI", 18, "bold"),
             fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack()

    # ========== 2. ⏱️ 启用自动时间校准 ==========
    calib_section = tk.Frame(container, bg=GUI_BG_COLOR)
    calib_section.pack(fill='x', padx=30, pady=6)
    calib_row = tk.Frame(calib_section, bg=GUI_BG_COLOR)
    calib_row.pack(anchor='w')
    auto_calib_var = tk.BooleanVar(value=current_auto_calibrate)
    tk.Checkbutton(calib_row, text="⏱️ 启用自动时间校准", variable=auto_calib_var,
                   font=("Microsoft YaHei UI", 13), fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR,
                   selectcolor="white", activebackground=GUI_BG_COLOR,
                   activeforeground=GUI_TEXT_COLOR).pack(side='left')
    _create_help_button(calib_row, "默认关闭，使用手动偏移即可\n开启后会自动测量与RSI服务器的时差\n网络延迟不稳定时校准可能不准").pack(side='left', padx=3)

    # ========== 3. 🕐 手动偏移 ==========
    manual_section = tk.Frame(container, bg=GUI_BG_COLOR)
    manual_section.pack(fill='x', padx=30, pady=6)
    manual_label_row = tk.Frame(manual_section, bg=GUI_BG_COLOR)
    manual_label_row.pack(anchor='w')
    tk.Label(manual_label_row, text="🕐 手动偏移", font=("Microsoft YaHei UI", 14, "bold"),
             fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack(side='left')
    _create_help_button(manual_label_row, "正数=本地比服务器快，需多等\n负数=本地比服务器慢，可提前发\n如本地快0.15秒，填+0.15").pack(side='left', padx=3)
    manual_row = tk.Frame(manual_section, bg=GUI_BG_COLOR)
    manual_row.pack(anchor='w', pady=(4, 0))
    manual_offset_entry = tk.Entry(manual_row, font=("Microsoft YaHei UI", 12), width=10,
                                   bg="white", fg="black", insertbackground="black", relief='flat', bd=2)
    manual_offset_entry.insert(0, current_manual_offset)
    manual_offset_entry.pack(side='left')
    tk.Label(manual_row, text="秒(正值=提前)", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR, padx=8).pack(side='left')

    # ========== 4. 🌐 代理地址 ==========
    proxy_section = tk.Frame(container, bg=GUI_BG_COLOR)
    proxy_section.pack(fill='x', padx=30, pady=6)
    tk.Label(proxy_section, text="🌐 代理地址", font=("Microsoft YaHei UI", 14, "bold"),
             fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack(anchor='w')
    proxy_row = tk.Frame(proxy_section, bg=GUI_BG_COLOR)
    proxy_row.pack(anchor='w', pady=(4, 0))
    proxy_entry = tk.Entry(proxy_row, font=("Microsoft YaHei UI", 12), width=28,
                           bg="white", fg="black", insertbackground="black", relief='flat', bd=2)
    proxy_entry.insert(0, current_proxy or "")
    proxy_entry.pack(side='left')
    tk.Label(proxy_row, text="(留空自动检测)", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR, padx=12).pack(side='left')

    # ========== 底部按钮 ==========
    btn_frame = tk.Frame(container, bg=GUI_BG_COLOR)
    btn_frame.pack(pady=18)

    # 返回值存储（必须在on_confirm定义之前初始化）
    result = {"manual_offset": current_manual_offset,
              "auto_calibrate": current_auto_calibrate,
              "proxy": current_proxy or ""}

    def on_confirm():
        result["manual_offset"] = manual_offset_entry.get().strip()
        result["auto_calibrate"] = auto_calib_var.get()
        result["proxy"] = proxy_entry.get().strip()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    tk.Button(btn_frame, text="确认", command=on_confirm, font=("Microsoft YaHei UI", 12, "bold"),
              fg="white", bg="#7B8FB7", relief='flat', padx=22, pady=8, cursor='hand2').pack(side='left', padx=15)
    tk.Button(btn_frame, text="取消", command=on_cancel, font=("Microsoft YaHei UI", 12, "bold"),
              fg="white", bg="#9E6B7A", relief='flat', padx=22, pady=8, cursor='hand2').pack(side='left', padx=15)

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.wait_window(dialog)

    return result

def _show_bookmarks_dialog(parent, sku_entry, price_entry, input_mode_var, on_mode_change):
    """显示SKU收藏夹弹窗，支持搜索和选择"""
    import tkinter as tk
    from tkinter import messagebox
    from .sku_bookmarks import load_bookmarks, remove_bookmark, add_bookmark
    
    dialog = tk.Toplevel(parent)
    dialog.title("📦 SKU收藏夹")
    dialog.geometry("520x520")
    dialog.minsize(400, 350)
    dialog.attributes('-topmost', True)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(True, True)
    dialog.configure(bg=GUI_BG_COLOR)
    
    # 标题
    tk.Label(dialog, text="📦 SKU收藏夹", font=("Microsoft YaHei UI", 16, "bold"),
             fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack(pady=(15, 5))
    
    # 搜索栏
    search_frame = tk.Frame(dialog, bg=GUI_BG_COLOR)
    search_frame.pack(fill='x', padx=20, pady=(5, 10))
    
    tk.Label(search_frame, text="🔍", font=("Microsoft YaHei UI", 12),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack(side='left')
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var,
                            font=("Microsoft YaHei UI", 11), width=30,
                            bg="white", fg="black", insertbackground="black",
                            relief='flat', bd=2)
    search_entry.pack(side='left', padx=5, fill='x', expand=True)
    
    # 列表容器（用Canvas+Scrollbar实现滚动）
    list_frame = tk.Frame(dialog, bg=GUI_BG_COLOR)
    list_frame.pack(fill='both', expand=True, padx=20, pady=5)
    
    canvas = tk.Canvas(list_frame, bg="white", highlightthickness=0)
    scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="white")
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # 窗口拉伸时canvas宽度跟随
    def _on_canvas_resize(event):
        canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", _on_canvas_resize)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # 绑定鼠标滚轮（Enter/Leave方式，确保鼠标在子控件上也能滚动）
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def _on_enter(event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    def _on_leave(event):
        canvas.unbind_all("<MouseWheel>")
    canvas.bind("<Enter>", _on_enter)
    canvas.bind("<Leave>", _on_leave)
    
    item_frames = []
    
    def refresh_list(*args):
        """刷新列表"""
        for f in item_frames:
            f.destroy()
        item_frames.clear()
        
        query = search_var.get().strip().lower()
        bookmarks = load_bookmarks()
        
        for b in bookmarks:
            name = b.get('name', 'Unknown')
            sku_id = b.get('sku_id', '')
            price = b.get('price', 0)
            
            # 搜索过滤
            if query and query not in name.lower() and query not in str(sku_id):
                continue
            
            # 每个条目
            row = tk.Frame(scrollable_frame, bg="white", pady=3)
            row.pack(fill='x', padx=5, pady=2)
            item_frames.append(row)
            
            # 名称+SKU信息
            info_frame = tk.Frame(row, bg="white")
            info_frame.pack(side='left', fill='x', expand=True)
            
            tk.Label(info_frame, text=name, font=("Microsoft YaHei UI", 11, "bold"),
                     fg="#1a3a5c", bg="white", anchor='w').pack(fill='x')
            tk.Label(info_frame, text=f"SKU: {sku_id}  |  ${price}" if price else f"SKU: {sku_id}  |  价格未知",
                     font=("Microsoft YaHei UI", 9), fg="#888888", bg="white", anchor='w').pack(fill='x')
            
            # 选择按钮
            def _select(sid=sku_id, pr=price):
                sku_entry.config(state='normal')
                sku_entry.delete(0, tk.END)
                sku_entry.insert(0, str(sid))
                input_mode_var.set("sku")
                on_mode_change("sku")
                if pr and pr > 0:
                    price_entry.delete(0, tk.END)
                    price_entry.insert(0, str(int(pr)) if pr == int(pr) else str(pr))
                dialog.destroy()
            
            tk.Button(row, text="选择", command=_select,
                      font=("Microsoft YaHei UI", 9, "bold"),
                      fg="white", bg="#6A8CBA", relief='flat',
                      padx=10, pady=2, cursor='hand2').pack(side='right', padx=3)
            
            # 删除按钮(带确认弹窗置顶)
            def _delete(sid=sku_id, r=row, bname=name):
                confirm = tk.Toplevel(dialog)
                confirm.title("确认删除")
                confirm.geometry("300x120")
                confirm.attributes('-topmost', True)
                confirm.transient(dialog)
                confirm.grab_set()
                tk.Label(confirm, text=f"确定删除 {bname} (SKU:{sid})？",
                         font=("Microsoft YaHei UI", 11), wraplength=260).pack(pady=15)
                btn_f = tk.Frame(confirm)
                btn_f.pack(pady=5)
                def _do_delete():
                    remove_bookmark(sid)
                    r.destroy()
                    if r in item_frames:
                        item_frames.remove(r)
                    confirm.destroy()
                    refresh_list()
                def _cancel_del():
                    confirm.destroy()
                tk.Button(btn_f, text="删除", command=_do_delete,
                          font=("Microsoft YaHei UI", 10), fg="white", bg="#9E6B7A",
                          relief='flat', padx=15, pady=3, cursor='hand2').pack(side='left', padx=10)
                tk.Button(btn_f, text="取消", command=_cancel_del,
                          font=("Microsoft YaHei UI", 10), fg="white", bg="#7B8FB7",
                          relief='flat', padx=15, pady=3, cursor='hand2').pack(side='left', padx=10)
            
            tk.Button(row, text="✕", command=_delete,
                      font=("Microsoft YaHei UI", 9),
                      fg="white", bg="#9E6B7A", relief='flat',
                      padx=5, pady=2, cursor='hand2').pack(side='right', padx=3)
            
            # 分隔线
            sep = tk.Frame(scrollable_frame, bg="#E0E0E0", height=1)
            sep.pack(fill='x', padx=10, pady=1)
            item_frames.append(sep)
        
        if not bookmarks:
            tk.Label(scrollable_frame, text="暂无收藏，拦截器获取SKU后自动保存",
                     font=("Microsoft YaHei UI", 11), fg="#999999", bg="white").pack(pady=20)
        
        # 搜索/刷新后更新canvas滚动区域
        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    # 搜索触发
    search_var.trace_add('write', refresh_list)
    
    # 初始加载
    refresh_list()
    
    # 手动添加区域
    add_frame = tk.Frame(dialog, bg=GUI_BG_COLOR)
    add_frame.pack(fill='x', padx=20, pady=(10, 5))
    
    tk.Label(add_frame, text="名称:", font=("Microsoft YaHei UI", 10),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack(side='left')
    add_name_entry = tk.Entry(add_frame, font=("Microsoft YaHei UI", 10), width=10,
                              bg="white", fg="black", insertbackground="black", relief='flat', bd=2)
    add_name_entry.pack(side='left', padx=3)
    
    tk.Label(add_frame, text="SKU:", font=("Microsoft YaHei UI", 10),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack(side='left')
    add_sku_entry = tk.Entry(add_frame, font=("Microsoft YaHei UI", 10), width=8,
                             bg="white", fg="black", insertbackground="black", relief='flat', bd=2)
    add_sku_entry.pack(side='left', padx=3)
    
    tk.Label(add_frame, text="价格$:", font=("Microsoft YaHei UI", 10),
             fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack(side='left')
    add_price_entry = tk.Entry(add_frame, font=("Microsoft YaHei UI", 10), width=6,
                               bg="white", fg="black", insertbackground="black", relief='flat', bd=2)
    add_price_entry.pack(side='left', padx=3)
    
    def _manual_add():
        name = add_name_entry.get().strip()
        sku = add_sku_entry.get().strip()
        price_str = add_price_entry.get().strip()
        if not name or not sku:
            return
        try:
            price = float(price_str) if price_str else 0
        except:
            price = 0
        add_bookmark(name, sku, price)
        add_name_entry.delete(0, tk.END)
        add_sku_entry.delete(0, tk.END)
        add_price_entry.delete(0, tk.END)
        refresh_list()
    
    tk.Button(add_frame, text="+添加", command=_manual_add,
              font=("Microsoft YaHei UI", 9, "bold"),
              fg="white", bg="#6A8CBA", relief='flat',
              padx=8, pady=2, cursor='hand2').pack(side='left', padx=5)
    
    # 关闭按钮
    def _on_close():
        try:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind("<Enter>")
            canvas.unbind("<Leave>")
        except:
            pass
        dialog.destroy()
    
    btn_row = tk.Frame(dialog, bg=GUI_BG_COLOR)
    btn_row.pack(pady=10)
    
    tk.Button(btn_row, text="关闭", command=_on_close,
              font=("Microsoft YaHei UI", 11, "bold"),
              fg="white", bg="#9E6B7A", relief='flat',
              padx=20, pady=5, cursor='hand2').pack(side='left', padx=5)
    
    dialog.protocol("WM_DELETE_WINDOW", _on_close)
    dialog.wait_window(dialog)


# ============================================================
# 配置对话框 (630x720)
# ============================================================

def _show_config_dialog():
    """显示配置窗口，返回是否继续"""
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
    
    # Tooltip/Help 函数已提取到模块级
    
    # 保存背景图引用，防止被GC回收
    bg_image_ref = [None]
    
    result = {"continue": False}
    
    # 加载保存的配置
    saved_config = _load_saved_config()
    current_dt = datetime.now()
    
    root = tk.Tk()
    root.title("咩咩蹄到好船来 V3.0.4 咩咩KICK！")
    root.geometry("630x780")
    root.resizable(False, False)
    
    # 尝试加载背景图
    try:
        bg_img_path = config.resource_path('gui_bg.png')
        if os.path.exists(bg_img_path):
            bg_img = Image.open(bg_img_path)
            bg_img = bg_img.resize((630, 780), Image.Resampling.LANCZOS)
            bg_photo = ImageTk.PhotoImage(bg_img, master=root)
            bg_image_ref[0] = bg_photo  # 保存引用
            bg_label = tk.Label(root, image=bg_photo)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
    except:
        root.configure(bg=GUI_BG_COLOR)
    
    CFG_BG_COLOR = GUI_BG_COLOR
    
    # ===== 标题 =====
    title_label = tk.Label(root, text="咩咩蹄到好船来 V3.0.4 咩咩KICK！",
                          font=("Microsoft YaHei UI", 20, "bold"),
                          fg=GUI_TITLE_COLOR, bg=CFG_BG_COLOR)
    title_label.place(relx=0.5, y=30, anchor='n')
    
    # ===== 滑动开关 =====
    # 伏击模式变量 (False=正面硬刚, True=伏击模式)
    ambush_mode_var = tk.BooleanVar(value=saved_config.get("ambush_mode", False) if saved_config else False)
    
    # 小toggle开关容器：左侧Label + 中间小开关 + 右侧Label
    switch_frame = tk.Frame(root, bg=CFG_BG_COLOR)
    switch_frame.place(relx=0.5, y=85, anchor='n')
    
    # 小toggle开关参数
    TOGGLE_WIDTH = 48
    TOGGLE_HEIGHT = 22
    TOGGLE_BG_OFF = "#6A8CBA"   # 正面硬刚 - 浅蓝色
    TOGGLE_BG_ON = "#E8A87C"    # 伏击模式 - 浅橙色
    TOGGLE_CIRCLE_R = 8         # 圆形滑块半径
    TOGGLE_PADDING = 3          # 滑块与边缘的距离
    
    # 左侧文字
    left_label = tk.Label(switch_frame, text="正面硬刚",
                          font=("Microsoft YaHei UI", 10),
                          fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR)
    left_label.pack(side='left', padx=(0, 8))
    
    # 小开关Canvas
    toggle_canvas = tk.Canvas(switch_frame, width=TOGGLE_WIDTH, height=TOGGLE_HEIGHT,
                              bg=CFG_BG_COLOR, highlightthickness=0, cursor='hand2')
    toggle_canvas.pack(side='left')
    
    # 滑动块位置变量 (0=左正面硬刚, 1=右伏击模式)
    slider_pos = [0.0 if not ambush_mode_var.get() else 1.0]
    
    def draw_toggle(pos):
        """绘制小toggle开关"""
        toggle_canvas.delete('all')
        
        # 计算滑块位置
        max_slide = TOGGLE_WIDTH - 2 * TOGGLE_PADDING - 2 * TOGGLE_CIRCLE_R
        circle_center_x = TOGGLE_PADDING + TOGGLE_CIRCLE_R + pos * max_slide
        circle_center_y = TOGGLE_HEIGHT // 2
        
        # 绘制圆角矩形底
        bg_color = TOGGLE_BG_OFF if pos < 0.5 else TOGGLE_BG_ON
        toggle_canvas.create_oval(0, 0, TOGGLE_HEIGHT, TOGGLE_HEIGHT, fill=bg_color, outline=bg_color)
        toggle_canvas.create_oval(TOGGLE_WIDTH - TOGGLE_HEIGHT, 0, TOGGLE_WIDTH, TOGGLE_HEIGHT, fill=bg_color, outline=bg_color)
        toggle_canvas.create_rectangle(TOGGLE_HEIGHT // 2, 0, TOGGLE_WIDTH - TOGGLE_HEIGHT // 2, TOGGLE_HEIGHT, fill=bg_color, outline=bg_color)
        
        # 绘制圆形滑块
        toggle_canvas.create_oval(circle_center_x - TOGGLE_CIRCLE_R, circle_center_y - TOGGLE_CIRCLE_R,
                                  circle_center_x + TOGGLE_CIRCLE_R, circle_center_y + TOGGLE_CIRCLE_R,
                                  fill="white", outline="white")
    
    def on_toggle_click(event):
        """切换开关（点击整个区域）"""
        new_pos = 1.0 if slider_pos[0] < 0.5 else 0.0
        if new_pos != slider_pos[0]:
            slider_pos[0] = new_pos
            ambush_mode_var.set(new_pos >= 0.5)
            draw_toggle(new_pos)
            update_hint_text()
            update_label_colors(new_pos)
    
    # 伏击模式相关widget的y坐标映射
    _ambush_widget_positions = {}
    
    def update_hint_text():
        """更新提示文字和输入区域可见性"""
        is_ambush = ambush_mode_var.get()
        if is_ambush:
            mode_hint.config(text="💡 请确认想要的船已加入购物车")
        else:
            mode_hint.config(text="💡 从0开始加船，开抢瞬间加购+结账")
        # 伏击模式隐藏输入方式/SKU/搜索/价格/排除行
        if _ambush_widget_positions:
            for widget, pos in _ambush_widget_positions.items():
                if is_ambush:
                    widget.place_forget()
                else:
                    widget.place(**pos)
    
    def update_label_colors(pos):
        """更新左右标签的样式"""
        if pos < 0.5:
            # 正面硬刚模式
            left_label.config(font=("Microsoft YaHei UI", 10, "bold"), fg="#6A8CBA")
            right_label.config(font=("Microsoft YaHei UI", 10), fg=GUI_TEXT_COLOR)
        else:
            # 伏击模式
            left_label.config(font=("Microsoft YaHei UI", 10), fg=GUI_TEXT_COLOR)
            right_label.config(font=("Microsoft YaHei UI", 10, "bold"), fg="#E8A87C")
    
    # 右侧文字
    right_label = tk.Label(switch_frame, text="伏击模式",
                           font=("Microsoft YaHei UI", 10),
                           fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR)
    right_label.pack(side='left', padx=(8, 0))
    
    # 绑定点击事件（点击整个frame区域）
    for widget in [left_label, toggle_canvas, right_label]:
        widget.bind('<Button-1>', on_toggle_click)
    # Canvas内部的点击也需要
    toggle_canvas.bind('<Button-1>', on_toggle_click)
    
    draw_toggle(slider_pos[0])
    update_label_colors(slider_pos[0])
    
    # 小问号帮助按钮
    switch_help_text = "【正面硬刚】\n从0开始加船（开抢瞬间加购+结账）\n\n【伏击模式】\n购物车直抢（已预加购，卡点只付款）\n提前30秒自动预装填"
    _create_help_button(switch_frame, switch_help_text).pack(side='left', padx=(10, 0))
    
    # ===== 提示文字 =====
    mode_hint = tk.Label(root, text="💡 从0开始加船，开抢瞬间加购+结账",
                         font=("Microsoft YaHei UI", 12),
                         fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR)
    mode_hint.place(relx=0.5, y=135, anchor='n')
    
    # 初始化提示文字
    root.after(50, update_hint_text)
    
    # ===== 抢购日期+时间（横排布局） =====
    # 日期行
    date_row = tk.Frame(root, bg=CFG_BG_COLOR)
    date_row.place(relx=0.5, y=175, anchor='n')
    
    tk.Label(date_row, text="抢购日期:", font=("Microsoft YaHei UI", 12),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left', padx=(0, 5))
    
    year_var = tk.StringVar(value=str(current_dt.year))
    year_combo = ttk.Combobox(date_row, textvariable=year_var, width=5, state='readonly',
                              font=("Microsoft YaHei UI", 11))
    year_combo['values'] = [str(y) for y in range(2025, 2028)]
    year_combo.pack(side='left')
    tk.Label(date_row, text="年", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    month_var = tk.StringVar(value=str(current_dt.month))
    month_combo = ttk.Combobox(date_row, textvariable=month_var, width=3, state='readonly',
                               font=("Microsoft YaHei UI", 11))
    month_combo['values'] = [str(m) for m in range(1, 13)]
    month_combo.pack(side='left')
    tk.Label(date_row, text="月", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    day_var = tk.StringVar(value=str(current_dt.day))
    day_combo = ttk.Combobox(date_row, textvariable=day_var, width=3, state='readonly',
                             font=("Microsoft YaHei UI", 11))
    day_combo['values'] = [str(d) for d in range(1, 32)]
    day_combo.pack(side='left')
    tk.Label(date_row, text="日", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    # 时间行
    time_row = tk.Frame(root, bg=CFG_BG_COLOR)
    time_row.place(relx=0.5, y=225, anchor='n')
    
    tk.Label(time_row, text="抢购时间:", font=("Microsoft YaHei UI", 12),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left', padx=(0, 5))
    
    hour_var = tk.StringVar(value=str(current_dt.hour))
    hour_combo = ttk.Combobox(time_row, textvariable=hour_var, width=3, state='readonly',
                              font=("Microsoft YaHei UI", 11))
    hour_combo['values'] = [str(h) for h in range(24)]
    hour_combo.pack(side='left')
    tk.Label(time_row, text="时", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    minute_var = tk.StringVar(value=str(current_dt.minute))
    minute_combo = ttk.Combobox(time_row, textvariable=minute_var, width=3, state='readonly',
                                font=("Microsoft YaHei UI", 11))
    minute_combo['values'] = [str(m) for m in range(60)]
    minute_combo.pack(side='left')
    tk.Label(time_row, text="分", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    second_var = tk.StringVar(value=str(current_dt.second))
    second_combo = ttk.Combobox(time_row, textvariable=second_var, width=3, state='readonly',
                                font=("Microsoft YaHei UI", 11))
    second_combo['values'] = [str(s) for s in range(60)]
    second_combo.pack(side='left')
    tk.Label(time_row, text="秒", fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR, padx=3).pack(side='left')
    
    # 警告文字
    warning_time = tk.Label(root, text="(早于现在可能出现未知BUG)",
                           font=("Microsoft YaHei UI", 9),
                           fg="#666666", bg=CFG_BG_COLOR)
    warning_time.place(relx=0.5, y=260, anchor='n')
    
    # ===== 偏移已合并进高级设置 =====
    manual_offset_var = tk.StringVar(value=saved_config.get("manual_time_offset", "-0.1") if saved_config else "-0.1")
    auto_calibrate_var = tk.BooleanVar(value=saved_config.get("auto_calibrate", False) if saved_config else False)
    
    # ===== 输入方式选择区域 =====
    input_mode_frame = tk.Frame(root, bg=CFG_BG_COLOR, padx=4, pady=2)
    input_mode_frame.place(relx=0.5, y=340, anchor='n')
    
    tk.Label(input_mode_frame, text="输入方式:", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left', padx=(0, 5))
    
    # 输入方式变量
    input_mode_var = tk.StringVar(value=saved_config.get("input_mode", "intercept") if saved_config and saved_config.get("input_mode") != "keyword" else "intercept")
    
    def on_input_mode_change(mode):
        """切换输入方式"""
        input_mode_var.set(mode)
        if mode == "sku":
            sku_entry.config(state='normal')
            search_entry.config(state='disabled')
            exclude_entry.config(state='disabled')
        else:  # intercept
            sku_entry.config(state='disabled')
            search_entry.config(state='normal')
            exclude_entry.config(state='normal')
    
    # SKU ID直购选项
    sku_radio = tk.Radiobutton(input_mode_frame, text="SKU ID直购",
                               variable=input_mode_var, value="sku",
                               font=("Microsoft YaHei UI", 10),
                               fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR,
                               selectcolor=GUI_BG_COLOR,
                               command=lambda: on_input_mode_change("sku"))
    sku_radio.pack(side='left', padx=5)
    
    # 刷新拦截选项
    intercept_radio = tk.Radiobutton(input_mode_frame, text="刷新拦截",
                                     variable=input_mode_var, value="intercept",
                                     font=("Microsoft YaHei UI", 10),
                                     fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR,
                                     selectcolor=GUI_BG_COLOR,
                                     command=lambda: on_input_mode_change("intercept"))
    intercept_radio.pack(side='left', padx=5)
    
    # ===== SKU ID输入行 =====
    sku_row = tk.Frame(root, bg=CFG_BG_COLOR)
    sku_row.place(relx=0.5, y=380, anchor='n')
    
    tk.Label(sku_row, text="📦SKU ID:", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left')
    
    _create_help_button(sku_row, "只需输入数字部分，如: 308456\n刷新拦截模式下此框自动填入").pack(side='left', padx=3)
    
    sku_entry = tk.Entry(sku_row, font=("Microsoft YaHei UI", 11), width=22,
                         bg="white", fg="black", insertbackground="black",
                         relief='flat', bd=2, state='disabled')
    saved_sku = saved_config.get("sku_id", "") if saved_config else ""
    sku_entry.insert(0, saved_sku)
    sku_entry.pack(side='left', padx=5)

    # 📦收藏夹按钮
    bookmark_btn = tk.Button(sku_row, text="📦", 
                              command=lambda: _show_bookmarks_dialog(root, sku_entry, price_entry, input_mode_var, on_input_mode_change),
                              font=("Microsoft YaHei UI", 10),
                              fg="white", bg="#7B8FB7", relief='flat',
                              padx=6, pady=2, cursor='hand2')
    bookmark_btn.pack(side='left', padx=3)

    # 搜索关键词行
    search_row = tk.Frame(root, bg=CFG_BG_COLOR)
    search_row.place(relx=0.5, y=420, anchor='n')
    
    tk.Label(search_row, text="🔍搜索关键词(可选过滤)", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left')
    
    _create_help_button(search_row, "搜索关键词：\n1. 输入目标商品名称\n2. 如 Kraken、Aurora MK II\n3. 多词用空格分隔\n4. URL前缀自动拼接").pack(side='left', padx=3)
    
    search_entry = tk.Entry(search_row, font=("Microsoft YaHei UI", 11), width=22,
                            bg="white", fg="black", insertbackground="black",
                            relief='flat', bd=2)
    search_entry.insert(0, saved_config.get("search_keywords", CFG["SEARCH_KEYWORDS"]) if saved_config else CFG["SEARCH_KEYWORDS"])
    search_entry.pack(side='left', padx=5)
    

    # ===== 商品价格(USD) =====
    price_row = tk.Frame(root, bg=CFG_BG_COLOR)
    price_row.place(relx=0.5, y=460, anchor='n')
    
    tk.Label(price_row, text="💰价格(USD):", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left')
    
    _create_help_button(price_row, "商品价格(美元)：\n1. API加购后结账需要此价格\n2. 如 PTV=15, 黑海妖=1500, 白海妖=2000\n3. 留空则从页面自动获取").pack(side='left', padx=3)
    
    price_entry = tk.Entry(price_row, font=("Microsoft YaHei UI", 11), width=22,
                           bg="white", fg="black", insertbackground="black",
                           relief='flat', bd=2)
    # 价格栏默认清空，只有从收藏夹选择才回填（避免信用点金额不匹配）
    price_entry.insert(0, "")
    price_entry.pack(side='left', padx=5)
    
    # 排除关键词行
    exclude_row = tk.Frame(root, bg=CFG_BG_COLOR)
    exclude_row.place(relx=0.5, y=500, anchor='n')
    
    tk.Label(exclude_row, text="🚫排除关键词(伏击无效)", font=("Microsoft YaHei UI", 11),
             fg=GUI_TEXT_COLOR, bg=CFG_BG_COLOR).pack(side='left')
    
    _create_help_button(exclude_row, "抢海妖须知：\n黑海妖锁定法：搜Kraken，排除Privateer\n白海妖锁定法：搜Kraken Privateer，不填排除\n通用排除法：多个结果时，用英文逗号分隔排除词，如\"DUR,MAX\"").pack(side='left', padx=3)
    
    exclude_entry = tk.Entry(exclude_row, font=("Microsoft YaHei UI", 11), width=22,
                             bg="white", fg="black", insertbackground="black",
                             relief='flat', bd=2)
    exclude_entry.insert(0, saved_config.get("exclude_keywords", CFG["EXCLUDE_KEYWORDS"]) if saved_config else CFG["EXCLUDE_KEYWORDS"])
    exclude_entry.pack(side='left', padx=5)
    
    # 注册伏击模式控制的widget及其位置
    _ambush_widget_positions.update({
        input_mode_frame: {"relx": 0.5, "y": 340, "anchor": "n"},
        sku_row: {"relx": 0.5, "y": 380, "anchor": "n"},
        search_row: {"relx": 0.5, "y": 420, "anchor": "n"},
        price_row: {"relx": 0.5, "y": 460, "anchor": "n"},
        exclude_row: {"relx": 0.5, "y": 500, "anchor": "n"},
    })
    # 首次应用伏击模式UI状态
    update_hint_text()
    
    # ===== 高级设置 =====
    
    # 高级设置变量
    advanced_proxy = tk.StringVar(value=saved_config.get("proxy", CFG["PROXY"]) if saved_config else (CFG["PROXY"] or ""))
    
    def _open_advanced_settings():
        result = _show_advanced_settings_dialog(root, manual_offset_var.get(), auto_calibrate_var.get(), advanced_proxy.get())
        manual_offset_var.set(result["manual_offset"])
        auto_calibrate_var.set(result["auto_calibrate"])
        advanced_proxy.set(result["proxy"])
    
    advanced_btn = tk.Button(root, text="高级设置", command=_open_advanced_settings,
                              font=("Microsoft YaHei UI", 11),
                              fg="white", bg="#7B8FB7", relief='flat',
                              padx=18, pady=5, cursor='hand2')
    advanced_btn.place(relx=0.38, y=565, anchor='n')
    

    
    # ===== 按钮行 =====
    start_btn = tk.Button(root, text="开始抢购", command=lambda: None,
                          font=("Microsoft YaHei UI", 13, "bold"),
                          fg="white", bg="#6A8CBA", relief='flat',
                          padx=25, pady=10, cursor='hand2')
    start_btn.place(relx=0.38, y=625, anchor='n')
    
    cancel_btn = tk.Button(root, text="取消", command=lambda: None,
                           font=("Microsoft YaHei UI", 13, "bold"),
                           fg="white", bg="#9E6B7A", relief='flat',
                           padx=25, pady=10, cursor='hand2')
    cancel_btn.place(relx=0.62, y=625, anchor='n')
    
    # ===== 警告提示 =====
    warning_label = tk.Label(root, text="⚠️ 请提前清空购物车，登录好账号",
                            font=("Microsoft YaHei UI", 10),
                            fg="black", bg=CFG_BG_COLOR)
    warning_label.place(relx=0.5, y=700, anchor='n')
    

    
    # ===== 作者署名 =====
    author_label = tk.Label(root, text="by 咩咩莉娅 V3.0.4",
                            font=("Microsoft YaHei UI", 8),
                            fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR)
    author_label.place(relx=1.0, rely=1.0, x=-5, y=-5, anchor='se')
    
    # 提交/取消逻辑
    def on_submit():
        year = year_var.get()
        month = month_var.get().zfill(2)
        day = day_var.get().zfill(2)
        hour = hour_var.get().zfill(2)
        minute = minute_var.get().zfill(2)
        second = second_var.get().zfill(2)
        target_time = f"{year}-{month}-{day} {hour}:{minute}:{second}"
        
        # 保存配置
        config_data = {
            "target_time": target_time,
            "search_keywords": search_entry.get().strip(),
            "exclude_keywords": exclude_entry.get(),
                "item_price": price_entry.get().strip(),
            "proxy": advanced_proxy.get(),
            "sku_id": sku_entry.get().strip(),
            "input_mode": input_mode_var.get(),
            "ambush_mode": ambush_mode_var.get(),
            "manual_time_offset": manual_offset_var.get(),
            "auto_calibrate": auto_calibrate_var.get(),
        }
        _save_config(config_data)
        
        # 更新CFG
        CFG["TARGET_TIME"] = target_time
        CFG["SEARCH_KEYWORDS"] = search_entry.get().strip()
        CFG["EXCLUDE_KEYWORDS"] = exclude_entry.get().strip()
        try:
            CFG["ITEM_PRICE"] = float(price_entry.get())
        except:
            CFG["ITEM_PRICE"] = 0
        CFG["AMBUSH_MODE"] = ambush_mode_var.get()
        CFG["SKU_ID"] = sku_entry.get().strip()
        CFG["INPUT_MODE"] = input_mode_var.get()
        
        # SKU直购模式必须填写价格（伏击模式跳过）
        if not CFG["AMBUSH_MODE"] and input_mode_var.get() == "sku" and CFG["ITEM_PRICE"] <= 0:
            from tkinter import messagebox
            messagebox.showwarning("⚠️ 价格未填写", "SKU ID模式必须准确填写对应信用点价格才可正常使用！\n价格错误造成的一切后果自负")
            return
        
        if advanced_proxy.get():
            CFG["PROXY"] = advanced_proxy.get()
        CFG["MANUAL_TIME_OFFSET"] = manual_offset_var.get()
        
        CFG["AUTO_CALIBRATE"] = bool(auto_calibrate_var.get())
        
        result["continue"] = True
        root.destroy()
    
    def on_cancel():
        result["continue"] = False
        root.destroy()
    
    start_btn.config(command=on_submit)
    cancel_btn.config(command=on_cancel)
    
    # 绑定回车键
    root.bind('<Return>', lambda e: on_submit())
    root.bind('<Escape>', lambda e: on_cancel())
    
    # 模态窗口
    root.grab_set()
    root.wait_window(root)
    
    return result["continue"]
