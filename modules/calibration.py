#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
时间校准模块 - 多级密度窗口校准
"""

import time
from datetime import datetime

from . import config

CFG = config.CFG
log = config.log


class CalibrationScheduler:
    """多级时间校准调度器
    
    校准方案：
    - 启动时：10次采样（粗校准）
    - 距T-0>60s：每30秒校准一次（修正漂移）
    - T-60s：10次采样（中校准）
    - T-30s：10次采样（精校准）
    - T-10s：10次采样0.3s间隔（最终精校准）
    
    降级策略：
    - ≥30s：启动+T-10s两次
    - 10-30s：启动10采样+T-10s 10采样
    - <10s：只做一次10采样
    """
    
    def __init__(self, client, target_ts: float, server_offset: float = 0.0):
        """
        Args:
            client: RSIClient实例
            target_ts: 目标时间戳（UTC）
            server_offset: 初始服务器偏移
        """
        self.client = client
        self.target = target_ts
        self.server_offset = server_offset
        self.calib_points = []  # [(时间戳, id), ...]
        self.calib_done = set()
        self._build_schedule()
    
    def _build_schedule(self):
        """根据剩余时间构建校准时间表"""
        now_ts = time.time()
        total_remaining = self.target - (now_ts - self.server_offset)
        calib_id = 0
        
        # 远距离：每30秒一次（修正长期漂移）
        if total_remaining > 90:
            t = self.target - 60  # 从T-60s开始往前
            while t > now_ts - self.server_offset + 15:
                calib_id += 1
                self.calib_points.append((t, calib_id))
                t -= 30
            self.calib_points.reverse()
        
        # 固定校准时间点：T-60, T-40, T-20, T-5
        for fixed_t in [60, 40, 20]:
            if total_remaining >= fixed_t:
                calib_id += 1
                self.calib_points.append((self.target - fixed_t, calib_id))
        
        # 去重（远距离可能和T-60重合）
        seen = set()
        unique_points = []
        for t, cid in self.calib_points:
            t_rounded = round(t, 1)
            if t_rounded not in seen:
                seen.add(t_rounded)
                unique_points.append((t, cid))
        self.calib_points = unique_points
        
        labels = [f"T-{int(self.target-t):.0f}s" for t, _ in self.calib_points]
        log.info(f"   计划{len(self.calib_points)}次校准: {labels}")
    
    def get_remaining(self) -> float:
        """获取距T-0的剩余时间（考虑服务器偏移）"""
        return self.target - (time.time() - self.server_offset)
    
    def check_and_calibrate(self) -> float:
        """检查是否到达校准时间点，执行校准
        
        Returns:
            当前服务器偏移值
        """
        for calib_target, calib_id in self.calib_points:
            if calib_id not in self.calib_done and time.time() - self.server_offset >= calib_target:
                self.calib_done.add(calib_id)
                t_label = f"T-{int(self.target - calib_target):.0f}s"
                
                # T-20s及以内用0.3s间隔，其他0.5s间隔，统一10次采样
                dist = self.target - calib_target
                samples = 10
                interval = 0.3 if dist <= 25 else 0.5
                
                # T-5s加deadline保护：校准最晚在T-2s结束，避免影响开抢
                deadline = self.target - 2 if dist <= 10 else 0
                
                # 最多重试3次
                for attempt in range(3):
                    try:
                        new_offset = self.client.calibrate_time(samples=samples, interval=interval, deadline=deadline)
                        if new_offset != 0.0:
                            self.server_offset = new_offset
                            CFG["SERVER_TIME_OFFSET"] = self.server_offset
                            log.info(f"🕐 校准({len(self.calib_done)}/{len(self.calib_points)}) {t_label}: 偏移{self.server_offset:+.3f}秒")
                            break
                    except Exception as e:
                        log.warning(f"   校准尝试{attempt+1}失败: {e}")
                        time.sleep(0.05)
                else:
                    log.warning(f"⚠️ {t_label}校准失败，继续使用当前偏移{self.server_offset:+.3f}秒")
        
        return self.server_offset
    
    def do_initial_calibration(self, manual_offset: float = 0.0) -> float:
        """执行启动时的初始校准
        
        Args:
            manual_offset: 手动偏移（非0时跳过自动校准）
        
        Returns:
            服务器偏移值
        """
        log.info("\n📍 [时间校准]")
        gui = config.get_gui()
        if gui: gui.update_status("校准时间...", "calibrate")
        
        if manual_offset != 0.0:
            self.server_offset = manual_offset
            CFG["SERVER_TIME_OFFSET"] = manual_offset
            log.info(f"   使用手动偏移: {manual_offset:+.3f}秒")
        else:
            remaining = self.get_remaining()
            if remaining < 20:
                log.info(f"   ⏰ 距T-0仅{remaining:.0f}秒，跳过校准(偏移=0)")
                self.server_offset = 0.0
            elif remaining < 40:
                log.info(f"   ⏰ 距T-0仅{remaining:.0f}秒，快速校准5次")
                self.server_offset = self.client.calibrate_time(samples=5, interval=0.3)
            else:
                self.server_offset = self.client.calibrate_time(samples=10, interval=0.5)
            CFG["SERVER_TIME_OFFSET"] = self.server_offset
            log.info(f"   初始校准偏移: {self.server_offset:+.3f}秒")
        
        if gui: gui.update_step("calibrate", True)
        if gui: gui.update_calibration(self.server_offset, is_manual=(manual_offset != 0.0))
        
        return self.server_offset
