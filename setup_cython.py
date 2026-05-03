#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cython编译脚本 - 将核心模块编译为.pyd二进制文件"""

from Cython.Build import cythonize
from setuptools import setup, Extension
import os
import sys

# 需要编译的核心模块（编译后无法反编译回源码）
COMPILE_MODULES = [
    "modules/api_client.py",
    "modules/main.py",
    "modules/sku_interceptor.py",
    "modules/calibration.py",
    "modules/browser.py",
    "modules/config.py",
]

# GUI模块保留.py（tkinter回调需要函数名，Cython编译后可能有兼容问题）
# modules/gui_config.py - 保留（GUI回调签名敏感）
# modules/gui_progress.py - 保留（同上）
# modules/sku_bookmarks.py - 保留（简单数据CRUD）
# modules/__init__.py - 保留

extensions = []
for mod in COMPILE_MODULES:
    if os.path.exists(mod):
        module_name = mod.replace("/", ".").replace("\\", ".").replace(".py", "")
        extensions.append(
            Extension(module_name, [mod])
        )

setup(
    name="RSI_MIEKCIK_BUY_Cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "annotation_typing": False,
        },
    ),
)
