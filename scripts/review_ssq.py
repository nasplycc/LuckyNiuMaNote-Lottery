#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双色球开奖后复盘脚本
- 更新历史开奖数据
- 读取最新一期开奖结果
- 对比当期发号结果
- 输出命中情况与简短规则复盘建议
"""

import csv
import json
from pathlib import Path
from datetime import datetime
import subprocess
import re

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / 'data' / 'ssq_history.csv'
OUTPUTS_DIR = ROOT / 'outputs'


def run_update_history():
    result = subprocess.run(
        ['python3', str(ROOT / 'scripts' / 'update_ssq_history.py')],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    return result.returncode == 0, result.stdout, result.stderr


def load_latest_draw():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    row = rows[-1]
    reds = [int(row[f'red_{i}']) for i in range(1, 7)]
    blue = int(row['blue_1'])
    return {
        'draw_id': row['draw_id'],
        'draw_date': row['draw_date'],
        'reds': reds,
        'blue': blue,
    }


def load_latest_pick_for_draw(draw_date=None):
    files = sorted(OUTPUTS_DIR.glob('ssq-picks-*.json'))
    if not files:
        return None, None

    # 优先取今天最新一期；否则取最新文件
    target = None
    if draw_date:
        ymd = draw_date.replace('-', '')
        same_day = [p for p in files if ymd in p.name]
        if same_day:
            target = same_day[-1]
    if target is None:
        target = files[-1]

    with open(target, 'r', encoding='utf-8') as f:
        return json.load(f), target


def compare_ticket(ticket, actual_reds, actual_blue):
    red_hits = sorted(set(ticket['reds']) & set(actual_reds))
    blue_hit = ticket.get('blue') == actual_blue
    red_count = len(red_hits)
    
    # 计算中奖等级和奖金（2026-04-09 固化）
    # 双色球中奖规则：
    # 一等奖：6 红 +1 蓝 → 浮动（默认按 500 万估算）
    # 二等奖：6 红 +0 蓝 → 浮动（默认按 10 万估算）
    # 三等奖：5 红 +1 蓝 → 3000 元
    # 四等奖：5 红 +0 蓝 或 4 红 +1 蓝 → 200 元
    # 五等奖：4 红 +0 蓝 或 3 红 +1 蓝 → 10 元
    # 六等奖：2 红 +1 蓝 或 1 红 +1 蓝 或 0 红 +1 蓝 → 5 元
    prize_amount = 0
    prize_level = None
    
    if red_count == 6 and blue_hit:
        prize_level = '一等奖'
        prize_amount = 5000000  # 估算
    elif red_count == 6 and not blue_hit:
        prize_level = '二等奖'
        prize_amount = 100000  # 估算
    elif red_count == 5 and blue_hit:
        prize_level = '三等奖'
        prize_amount = 3000
    elif red_count == 5 and not blue_hit:
        prize_level = '四等奖'
        prize_amount = 200
    elif red_count == 4 and blue_hit:
        prize_level = '四等奖'
        prize_amount = 200
    elif red_count == 4 and not blue_hit:
        prize_level = '五等奖'
        prize_amount = 10
    elif red_count == 3 and blue_hit:
        prize_level = '五等奖'
        prize_amount = 10
    elif red_count == 2 and blue_hit:
        prize_level = '六等奖'
        prize_amount = 5
    elif red_count == 1 and blue_hit:
        prize_level = '六等奖'
        prize_amount = 5
    elif red_count == 0 and blue_hit:
        prize_level = '六等奖'
        prize_amount = 5
    
    return {
        'red_count': red_count,
        'red_hits': red_hits,
        'blue_hit': blue_hit,
        'prize_level': prize_level,
        'prize_amount': prize_amount,
    }


def get_prize_info(draw_id):
    """
    获取双色球当期奖金信息。
    优先从历史数据文件读取，若没有则返回 None（后续可扩展从其他渠道获取）。
    返回：dict { 'prize_1': {'count': int, 'amount': float}, 'prize_2': {...}, ... }
    如果找不到奖金信息，返回 None。
    """
    # 先尝试从历史文件读取
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        target_row = None
        for row in rows:
            if row['draw_id'] == draw_id:
                target_row = row
                break
        if target_row:
            prize_info = {}
            for i in range(1, 3):
                count_key = f'prize_{i}_count'
                amount_key = f'prize_{i}_amount'
                if count_key in target_row and amount_key in target_row:
                    count_val = target_row[count_key]
                    amount_val = target_row[amount_key]
                    if count_val and amount_val:
                        prize_info[f'prize_{i}'] = {
                            'count': int(count_val),
                            'amount': float(amount_val)
                        }
            if prize_info:
                return prize_info
    except Exception:
        pass

    # 2026-04-09 固化：如果历史文件没有奖金信息，返回 None
    # 后续可通过手动更新或其他方式补充
    return None


def summarize_shape(draw):
    reds = draw['reds']
    odd = sum(1 for n in reds if n % 2 == 1)
    even = 6 - odd
    zones = [0, 0, 0]
    for n in reds:
        if 1 <= n <= 11:
            zones[0] += 1
        elif 12 <= n <= 22:
            zones[1] += 1
        else:
            zones[2] += 1
    total = sum(reds)
    consecutive = []
    group = [reds[0]]
    for i in range(1, len(reds)):
        if reds[i] == reds[i-1] + 1:
            group.append(reds[i])
        else:
            if len(group) >= 2:
                consecutive.append(group)
            group = [reds[i]]
    if len(group) >= 2:
        consecutive.append(group)
    return {
        'odd_even': (odd, even),
        'zones': tuple(zones),
        'sum': total,
        'consecutive': consecutive,
    }


def build_review(draw, picks):
    shape = summarize_shape(draw)
    lines = []
    lines.append(f"📌 开奖号码：{' '.join(f'{n:02d}' for n in draw['reds'])} + 蓝 {draw['blue']:02d}")
    lines.append(f"形态：奇偶 {shape['odd_even'][0]}:{shape['odd_even'][1]}｜分区 {shape['zones'][0]}:{shape['zones'][1]}:{shape['zones'][2]}｜和值 {shape['sum']}")
    if shape['consecutive']:
        groups = ['-'.join(f'{x:02d}' for x in g) for g in shape['consecutive']]
        lines.append(f"连号：{'，'.join(groups)}")
    else:
        lines.append("连号：无")

    main = picks.get('main', [])
    backup = picks.get('backup', [])
    all_tickets = [('主推', i + 1, t) for i, t in enumerate(main)] + [('备选', i + 1, t) for i, t in enumerate(backup)]

    best = None
    hit_lines = []
    total_prize = 0
    for kind, idx, ticket in all_tickets:
        cmp = compare_ticket(ticket, draw['reds'], draw['blue'])
        score_tuple = (cmp['red_count'], 1 if cmp['blue_hit'] else 0)
        if best is None or score_tuple > best[0]:
            best = (score_tuple, kind, idx, ticket, cmp)
        
        hit_text = f"{kind}{idx}：{cmp['red_count']}红"
        if cmp['red_hits']:
            hit_text += f"（命中 {','.join(f'{n:02d}' for n in cmp['red_hits'])}）"
        if cmp['blue_hit']:
            hit_text += " + 蓝"
        if cmp['prize_level']:
            hit_text += f" → {cmp['prize_level']} {cmp['prize_amount']:,}元"
        else:
            hit_text += " → 未中奖 0 元"
        
        total_prize += cmp['prize_amount']
        hit_lines.append(hit_text)

    lines.append("")
    lines.append("🎯 本期命中情况：")
    lines.extend([f"- {x}" for x in hit_lines])

    lines.append("")
    lines.append(f"本期合计奖金：{total_prize:,}元")
    lines.append("")
    best_cmp = best[4]
    lines.append(f"本期最好表现：{best[1]}{best[2]}，{best_cmp['red_count']}红{' + 蓝' if best_cmp['blue_hit'] else ''}")

    # 奖金信息（2026-04-09 固化）
    # 优先从历史文件/API 获取，如果没有则检查手动录入
    prize_info = get_prize_info(draw['draw_id'])
    
    # 手动录入入口（可选）：在 picks 文件里找 bonus_manual 字段
    if not prize_info and picks:
        manual_bonus = picks.get('bonus_manual', {})
        if manual_bonus:
            prize_info = {}
            if 'prize_1' in manual_bonus:
                prize_info['prize_1'] = {
                    'count': int(manual_bonus['prize_1'].get('count', 0)),
                    'amount': float(manual_bonus['prize_1'].get('amount', 0))
                }
            if 'prize_2' in manual_bonus:
                prize_info['prize_2'] = {
                    'count': int(manual_bonus['prize_2'].get('count', 0)),
                    'amount': float(manual_bonus['prize_2'].get('amount', 0))
                }
    
    if prize_info:
        lines.append("")
        lines.append("💰 本期奖金：")
        if 'prize_1' in prize_info:
            p1 = prize_info['prize_1']
            lines.append(f"- 一等奖：{p1['count']} 注，单注 {int(p1['amount']):,} 元")
        if 'prize_2' in prize_info:
            p2 = prize_info['prize_2']
            lines.append(f"- 二等奖：{p2['count']} 注，单注 {int(p2['amount']):,} 元")
        if 'prize_3' in prize_info:
            p3 = prize_info['prize_3']
            lines.append(f"- 三等奖：{p3['count']} 注，单注 {int(p3['amount']):,} 元")

    # 简短规则复盘
    review = []
    if shape['sum'] < 90:
        review.append("和值偏低，后续可略提高低和值组合权重。")
    elif shape['sum'] > 125:
        review.append("和值偏高，后续可适度放宽高和值过滤。")
    else:
        review.append("和值处于常见区间，现有和值约束可继续保留。")

    if shape['consecutive']:
        review.append("本期出现连号，后续不要把连号压得太死。")
    else:
        review.append("本期无连号，连号规则维持中性即可。")

    if shape['zones'] in [(2, 2, 2), (1, 2, 3), (2, 1, 3), (3, 2, 1)]:
        review.append("分区形态正常，主流分区规则有效。")
    else:
        review.append("分区略偏，后续可适度增加非常规分区样本占比。")

    lines.append("")
    lines.append("🧪 规则净化建议：")
    lines.extend([f"- {x}" for x in review])
    lines.append("")
    lines.append("结论：继续做纪律化复盘，优化规则，但不做'必中'幻想。")
    return '\n'.join(lines)


def main():
    ok, out, err = run_update_history()
    if not ok:
        print("❌ 开奖复盘失败：历史数据更新失败")
        if err:
            print(err.strip())
        return

    draw = load_latest_draw()
    picks, pick_path = load_latest_pick_for_draw(draw['draw_date'])
    if not picks:
        print(f"⚠️ 已更新到 {draw['draw_id']} 期开奖号码，但没找到对应选号文件。")
        print(f"开奖号码：{' '.join(f'{n:02d}' for n in draw['reds'])} + 蓝 {draw['blue']:02d}")
        return

    print(f"📣 双色球 {draw['draw_id']} 期开奖复盘")
    print(f"选号文件：{pick_path.name}")
    print(build_review(draw, picks))


if __name__ == '__main__':
    main()
