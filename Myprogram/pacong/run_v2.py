#!/usr/bin/env python3
"""v2爬虫运行脚本"""
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(line_buffering=True)
from crawl_v2_engine import run_all
run_all()
