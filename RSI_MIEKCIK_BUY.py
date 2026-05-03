#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""咩咩Kick! V3.0.0 - 入口"""
from modules.main import run, test, help
from modules.config import get_args

def _show_disclaimer():
    """显示免责声明弹窗，用户必须同意才能继续"""
    import tkinter as tk
    from tkinter import font as tkfont
    
    root = tk.Tk()
    root.withdraw()  # 先隐藏主窗口
    
    disclaimer_text = (
        "【免责声明】\n\n"
        "本工具仅供个人学习交流使用，严禁用于任何商业用途。\n\n"
        "包括但不限于：\n"
        "  - 付费代抢服务\n"
        "  - 二次售卖或分销\n"
        "  - 任何形式的商业获利行为\n\n"
        "使用本工具即表示您同意：\n"
        "  1. 仅用于个人学习目的\n"
        "  2. 不将本工具用于任何商业用途\n"
        "  3. 遵守 RSI 服务条款\n"
        "  4. 作者不对使用后果承担任何责任\n\n"
        "如不同意以上条款，请点击【退出】。"
    )
    
    dialog = tk.Toplevel(root)
    dialog.title("免责声明")
    dialog.geometry("460x500")
    dialog.resizable(False, False)
    dialog.configure(bg="#f5f5f5")
    dialog.grab_set()
    dialog.focus_force()
    
    # 居中
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - 460) // 2
    y = (dialog.winfo_screenheight() - 500) // 2
    dialog.geometry(f"+{x}+{y}")
    
    # 标题
    title_font = tkfont.Font(family="Microsoft YaHei UI", size=14, weight="bold")
    tk.Label(dialog, text="⚠ 请阅读并同意以下声明", font=title_font,
             fg="#c0392b", bg="#f5f5f5").pack(pady=(15, 10))
    
    # 内容
    text_font = tkfont.Font(family="Microsoft YaHei UI", size=10)
    tk.Label(dialog, text=disclaimer_text, font=text_font, fg="#2d2d2d",
             bg="#f5f5f5", justify="left", anchor="w",
             wraplength=420).pack(padx=20, pady=5)
    
    # 按钮
    btn_frame = tk.Frame(dialog, bg="#f5f5f5")
    btn_frame.pack(pady=15)
    
    agreed = [False]
    
    def on_agree():
        agreed[0] = True
        dialog.destroy()
        root.destroy()
    
    def on_disagree():
        dialog.destroy()
        root.destroy()
    
    btn_font = tkfont.Font(family="Microsoft YaHei UI", size=11, weight="bold")
    tk.Button(btn_frame, text="我已阅读并同意", command=on_agree,
              font=btn_font, fg="white", bg="#27ae60", relief="flat",
              padx=25, pady=8, cursor="hand2").pack(side="left", padx=15)
    tk.Button(btn_frame, text="退出", command=on_disagree,
              font=btn_font, fg="white", bg="#95a5a6", relief="flat",
              padx=25, pady=8, cursor="hand2").pack(side="left", padx=15)
    
    dialog.protocol("WM_DELETE_WINDOW", on_disagree)
    root.mainloop()
    
    return agreed[0]


if __name__ == "__main__":
    # 显示免责声明
    if not _show_disclaimer():
        import sys
        sys.exit(0)
    
    args = get_args()
    if args.test:
        test()
    else:
        run()
