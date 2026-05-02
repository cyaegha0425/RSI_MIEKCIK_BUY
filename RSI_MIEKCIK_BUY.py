#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""咩咩Kick! V3.0.0 - 入口"""
from modules.main import run, test, help
from modules.config import get_args

if __name__ == "__main__":
    args = get_args()
    if args.test:
        test()
    else:
        run()
