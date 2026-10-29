#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双色球开奖后复盘脚本
- 更新历史开奖数据
- 读取最新一期开奖结果
- 对比当期发号结果
- 优先按 compound_7x2（7+2复式）复盘
- 输出命中情况与简短规则复盘建议
"""

import csv
import math
import json
import subprocess
from itertools import combinations
from pathlib import Path

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
    # 优先使用 picks-review-map.json 中记录的"用户实际购买"选号文件，
    # 避免同一天存在多份选号文件时默认取最新（19:30）而拿错目标。
    map_path = ROOT / 'memory' / 'picks-review-map.json'
    if map_path.exists():
        try:
            m = json.load(map_path.open(encoding='utf-8'))
            # 找到该日期对应的期号记录
            ymd = draw_date.replace('-', '')
            for draw_id, rec in m.items():
                rid = str(draw_id)
                rec_date = str(rec.get('draw_date', '')).replace('-', '')
                hit = bool(ymd and (
                    rec_date.endswith(ymd[-6:]) or  # draw_date 日期匹配
                    rid.endswith(ymd[-3:])          # 期号尾三位匹配
                ))
                if not hit and len(m) == 1:
                    hit = True  # 兜底：唯一记录直接采用
                if hit:
                    rel = rec.get('picks_file')
                    if rel:
                        p = ROOT / rel
                        if p.exists():
                            with open(p, 'r', encoding='utf-8') as f:
                                return json.load(f), p
        except Exception as e:
            print(f"⚠️ 读取 picks-review-map.json 失败({e})，回退默认逻辑")

    files = sorted(OUTPUTS_DIR.glob('ssq-picks-*.json'))
    if not files:
        return None, None

    target = None
    if draw_date:
        ymd = draw_date.replace('-', '')
        same_day = [p for p in files if ymd in p.name]
        if same_day:
            # 优先读取当天最新的（包含完整compound_7x2数据）
            # 按时间戳排序，取最新的
            same_day.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            target = same_day[0]

    with open(target, 'r', encoding='utf-8') as f:
        return json.load(f), target


def compare_ticket(ticket, actual_reds, actual_blue):
    red_hits = sorted(set(ticket['reds']) & set(actual_reds))
    blue_hit = ticket.get('blue') == actual_blue
    red_count = len(red_hits)

    prize_amount = 0
    prize_level = None

    if red_count == 6 and blue_hit:
        prize_level = '一等奖'
        prize_amount = 5000000
    elif red_count == 6 and not blue_hit:
        prize_level = '二等奖'
        prize_amount = 100000
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
        if reds[i] == reds[i - 1] + 1:
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


def summarize_compound_7x2(compound, draw):
    reds = set(compound['reds'])
    blues = set(compound['blues'])
    red_hits = sorted(reds & set(draw['reds']))
    blue_hits = sorted(blues & {draw['blue']})
    red_count = len(red_hits)
    blue_count = len(blue_hits)

    bonus = 0
    per_note = []
    for rcombo in combinations(sorted(reds), 6):
        rc = len(set(rcombo) & set(draw['reds']))
        for blue in sorted(blues):
            bh = (blue == draw['blue'])
            if rc == 6 and bh:
                bonus += 5000000; per_note.append(('一等奖', 5000000))
            elif rc == 5 and bh:
                bonus += 3000; per_note.append(('三等奖', 3000))
            elif rc == 4:
                bonus += 200; per_note.append(('四等奖', 200))
            elif rc == 3 and bh:
                bonus += 10; per_note.append(('五等奖', 10))
            elif bh:
                bonus += 5; per_note.append(('六等奖', 5))
    from collections import Counter
    level_counts = Counter(k for k, _ in per_note)
    winning_notes = len(per_note)
    cost = int(compound.get('cost', 28))
    return {
        'reds': sorted(reds),
        'blues': sorted(blues),
        'red_hits': red_hits,
        'blue_hits': blue_hits,
        'red_count': red_count,
        'blue_count': blue_count,
        'bonus': bonus,
        'winning_notes': winning_notes,
        'level_counts': dict(level_counts),
        'cost': cost,
        'net': bonus - cost,
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

    compound = picks.get('compound_7x2')

    if compound:
        compound_summary = summarize_compound_7x2(compound, draw)
        actual_cost = compound_summary['cost']
        actual_prize = compound_summary['bonus']
        actual_net = compound_summary['net']
        primary_lines = [
            "🎯 7+2复式命中情况：",
            f"  红球：{' '.join(f'{n:02d}' for n in compound_summary['reds'])}",
            f"  蓝球：{' '.join(f'{n:02d}' for n in compound_summary['blues'])}",
            f"• 命中：{compound_summary['red_count']}红{('（' + '、'.join(f'{n:02d}' for n in compound_summary['red_hits']) + '）') if compound_summary['red_hits'] else ''} | 蓝{'全中' if compound_summary['blue_count'] == 2 else ('1中' if compound_summary['blue_count'] == 1 else '0中')}",
            f"• 中奖注数：{compound_summary['winning_notes']} 注",
            f"• 奖金：¥{compound_summary['bonus']:,}",
            f"• 成本：¥{compound_summary['cost']}｜净{'盈' if compound_summary['net'] >= 0 else '亏'} ¥{abs(compound_summary['net']):,}",
        ]
        best_line = f"🏅 本期最佳：7+2复式，{compound_summary['red_count']}红 + {'2蓝' if compound_summary['blue_count'] == 2 else ('1蓝' if compound_summary['blue_count'] == 1 else '无蓝')}"
        actual_cost = compound_summary['cost']
        actual_prize = compound_summary['bonus']
        actual_net = compound_summary['net']
    else:
        actual_cost = 0
        actual_prize = 0
        actual_net = 0
        primary_lines = ["🎯 未找到可用复盘目标。"]
        best_line = None

    lines.extend(primary_lines)
    lines.append("")
    lines.append(f"💰 本期汇总：实付 ¥{actual_cost}｜奖金 ¥{actual_prize:,}｜净{'盈' if actual_net >= 0 else '亏'} ¥{abs(actual_net):,}")
    if best_line:
        lines.append(best_line)

    prize_info = get_prize_info(draw['draw_id'])
    if not prize_info and picks:
        manual_bonus = picks.get('bonus_manual', {})
        if manual_bonus:
            prize_info = {}
            for key in ('prize_1', 'prize_2'):
                if key in manual_bonus:
                    prize_info[key] = {
                        'count': int(manual_bonus[key].get('count', 0)),
                        'amount': float(manual_bonus[key].get('amount', 0)),
                    }

    if prize_info:
        lines.append("")
        lines.append("💰 本期奖金：")
        for key in ('prize_1', 'prize_2', 'prize_3'):
            if key in prize_info:
                p = prize_info[key]
                lines.append(f"- {key.replace('_', ' ')}：{p['count']} 注，单注 {int(p['amount']):,} 元")

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
    lines.extend(f"- {x}" for x in review)
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
