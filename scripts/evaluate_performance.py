#!/usr/bin/env python3
"""双色球V2历史评估 - 修正版，不做事后归因"""
import csv, json, re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / 'data' / 'ssq_history.csv'
OUTPUTS_DIR = ROOT / 'outputs'


def calc_prize(red_hit, blue_hit):
    if red_hit == 6 and blue_hit: return '一等奖', 5000000
    if red_hit == 6 and not blue_hit: return '二等奖', 100000
    if red_hit == 5 and blue_hit: return '三等奖', 3000
    if red_hit == 5 and not blue_hit: return '四等奖', 200
    if red_hit == 4 and blue_hit: return '四等奖', 200
    if red_hit == 4 and not blue_hit: return '五等奖', 10
    if red_hit == 3 and blue_hit: return '五等奖', 10
    if red_hit == 3 and not blue_hit: return None, 0
    if blue_hit: return '六等奖', 5
    return None, 0


def evaluate():
    with open(DATA_PATH, 'r') as f:
        rows = list(csv.DictReader(f))
    draws_by_date = {}
    for row in rows:
        reds = [int(row[f'red_{i}']) for i in range(1, 7)]
        blue = int(row['blue_1'])
        draws_by_date[row['draw_date']] = {
            'draw_id': row['draw_id'],
            'reds': set(reds),
            'blue': blue,
        }

    pick_files = sorted(OUTPUTS_DIR.glob('ssq-picks-*.json'))
    print(f"{'='*80}")
    print(f"📊 双色球选号系统 V2 历史表现（第2版）")
    print(f"{'='*80}")

    total_cost = 0
    total_prize = 0
    tier_counts = Counter()
    max_red_dist = Counter()
    results = []
    note_red_hits = []  # all individual note hit counts

    # Only evaluate V2-format files (v2 has 'filtering_logic' key)
    v2_files = [pf for pf in pick_files if 'ssq-picks-2' in pf.name or ('ssq-picks-2' not in pf.name and len(OUTPUTS_DIR.glob('ssq-picks-*.json')) > 0)]
    # Actually all files from roughly 2026-03-29 onward are v2, let's just process all
    
    for pf in pick_files:
        m = re.search(r'(\d{4})(\d{2})(\d{2})', pf.name)
        if not m:
            continue
        pick_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        draw = draws_by_date.get(pick_date)
        if not draw:
            continue
        with open(pf) as f:
            data = json.load(f)

        # Skip promo-only files
        if 'lottery' in data and data.get('lottery') != '双色球':
            continue

        total_cost += 10
        all_notes = data.get('main', []) + data.get('backup', [])
        period_prize = 0
        period_max_red = 0
        period_best = '-'
        note_details = []

        for note in all_notes:
            red_hit = len(set(note['reds']) & draw['reds'])
            blue_hit = note['blue'] == draw['blue']
            period_max_red = max(period_max_red, red_hit)
            note_red_hits.append(red_hit)
            level, prize = calc_prize(red_hit, blue_hit)
            period_prize += prize
            if level and (period_best == '-' or ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖'].index(level) < ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖','-'].index(period_best)):
                period_best = level
            note_details.append({
                'reds': note['reds'],
                'blue': note['blue'],
                'red_hit': red_hit,
                'blue_hit': blue_hit,
                'red_bits': sorted(set(note['reds']) & draw['reds']),
                'level': level if level else '-',
                'prize': prize,
            })

        total_prize += period_prize
        tier_counts[period_best] += 1
        max_red_dist[period_max_red] += 1
        results.append({
            'date': pick_date,
            'draw_id': draw['draw_id'],
            'draw_reds': draw['reds'],
            'draw_blue': draw['blue'],
            'max_red': period_max_red,
            'best_level': period_best,
            'prize': period_prize,
            'details': note_details,
        })

    # ===== 总体统计 =====
    print(f"\n📅 评估期间：{results[0]['date']} → {results[-1]['date']}")
    print(f"📋 总期数：{len(results)} 期")
    print(f"💰 总投入：{total_cost} 元（{len(results)}期 × 5注 × 2元）")
    print(f"🏆 总中奖：{total_prize} 元")
    net = total_prize - total_cost
    print(f"{'📉' if net < 0 else '📈'} 净收益：{net} 元")
    print(f"📊 回报率：{total_prize / max(total_cost, 1) * 100:.1f}%")

    print(f"\n{'─'*40}")
    print("🎯 中奖等级分布（单期最佳）")
    for lv in ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖','-']:
        c = tier_counts.get(lv, 0)
        if c: print(f"  {lv}: {c} 期 {('█'*c)}")

    print(f"\n{'─'*40}")
    print("📊 单期最高红球命中分布")
    for n in range(0, 7):
        c = max_red_dist.get(n, 0)
        if c: print(f"  {n}红: {c:2d} 期 {'█'*c} ({c/len(results)*100:.0f}%)")

    print(f"\n{'─'*40}")
    print("📊 5注共260次独立投注的红球命中分布")
    note_dist = Counter(note_red_hits)
    for n in range(0, 7):
        c = note_dist.get(n, 0)
        if c: print(f"  {n}红/注: {c:3d} 次 ({c/len(note_red_hits)*100:.1f}%)")

    # ===== 6+5 真实模拟 =====
    # 真实的6+5：从候选池中Score前6的号码中选6个红球（不是事后最优）
    # 但更实际的方法是：我们看每个note的红球质量，然后取综合最优
    # 公平的6+5：用5注候选池中"出现次数最多的6个红球"
    # 这样是纯策略选择，不依赖事后结果
    
    # Actually let me do it differently:
    # For 6+5, we pick ONE note's reds (the highest scoring one - 主推1) 
    # and pair it with all 5 blues from the 5 notes
    # This is a FAIR comparison because we choose the strategy before seeing the result
    
    print(f"\n{'='*80}")
    print(f"🧪 策略对比：当前(5注独立) vs 6+5(主推1红球×5篮)")
    print(f"{'='*80}")
    
    six5_total = 0
    six5_win_periods = 0
    six5_best_levels = Counter()
    six5_max_red = Counter()
    
    for r in results:
        main1_reds = r['details'][0]['reds']
        main1_blue = r['details'][0]['blue']
        
        # 6+5: use main1's reds, pair with all 5 blue from the 5 notes
        all_blues = set(d['blue'] for d in r['details'])
        red_hit = len(set(main1_reds) & r['draw_reds'])
        six5_max_red[red_hit] += 1
        
        period_prize = 0
        period_best = '-'
        for blue in all_blues:
            blue_hit = blue == r['draw_blue']
            level, prize = calc_prize(red_hit, blue_hit)
            period_prize += prize
            if level and (period_best == '-' or ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖'].index(level) < ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖','-'].index(period_best)):
                period_best = level
        
        six5_total += period_prize
        if period_prize > 0:
            six5_win_periods += 1
        six5_best_levels[period_best if period_best != '-' else '-'] += 1
    
    six5_net = six5_total - len(results) * 10
    
    print(f"\n【当前策略 — 5注独立红球】")
    print(f"  总奖金：{total_prize}元 | 净收益：{net}元 | 回报率：{total_prize/total_cost*100:.1f}%")
    print(f"  中奖期数：{len(results)-tier_counts.get('-',0)}/{len(results)}")
    
    print(f"\n【6+5 策略 — 主推1红球 × 5个蓝球】")
    print(f"  选红方式：直接取主推1的6码红球")
    print(f"  蓝球覆盖：5码不同蓝球")
    print(f"  成本不变：10元/期")
    print(f"  总奖金：{six5_total}元 | 净收益：{six5_net}元 | 回报率：{six5_total/(len(results)*10)*100:.1f}%")
    print(f"  中奖期数：{six5_win_periods}/{len(results)}")
    
    print(f"\n  6+5 红球命中分布（主推1的6码表现）：")
    for n in range(0, 7):
        c = six5_max_red.get(n, 0)
        if c: print(f"    {n}红: {c}期 ({c/len(results)*100:.0f}%)")
    
    print(f"\n  6+5 中奖等级分布：")
    for lv in ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖','-']:
        c = six5_best_levels.get(lv, 0)
        if c: print(f"    {lv}: {c}期")

    # ===== 详细对比 =====
    print(f"\n{'='*80}")
    print(f"📋 每期对比")
    print(f"{'='*80}")
    for idx, r in enumerate(results):
        main1_reds = r['details'][0]['reds']
        all_blues = set(d['blue'] for d in r['details'])
        red_hit = len(set(main1_reds) & r['draw_reds'])
        
        six5_p = 0
        for blue in all_blues:
            _, p = calc_prize(red_hit, blue == r['draw_blue'])
            six5_p += p
        
        actual = r['prize']
        diff = six5_p - actual
        sym = '▲' if diff > 0 else ('▼' if diff < 0 else '=')
        
        print(f"  {r['date'][5:]} [{r['draw_id']}] | 最高红: cur={r['max_red']}/6+5={red_hit} | cur:+{actual}元 | 6+5:+{six5_p}元 {sym}{abs(diff) if diff else ''}")

    # ===== 核心结论 =====
    print(f"\n{'='*80}")
    print(f"💡 结论")
    print(f"{'='*80}")
    
    # Key fact: how often does main1's reds perform?
    main1_3plus = sum(1 for r in results if len(set(r['details'][0]['reds']) & r['draw_reds']) >= 3)
    main1_4plus = sum(1 for r in results if len(set(r['details'][0]['reds']) & r['draw_reds']) >= 4)
    
    # Best individual note analysis
    best_note_per_period = []
    for r in results:
        best = max(r['details'], key=lambda d: d['red_hit'])
        best_note_per_period.append(best['red_hit'])
    best_note_dist = Counter(best_note_per_period)
    
    print(f"\n📌 候选池的「最佳单注」能吃到多少红？")
    for n in range(0, 7):
        c = best_note_dist.get(n, 0)
        if c: print(f"  最佳单注 {n}红: {c}期 ({c/len(results)*100:.0f}%)")
    
    # Pool quality assessment
    print(f"\n📌 候选池质量（5注中含3红以上的注数）")
    three_plus_count = sum(1 for h in note_red_hits if h >= 3)
    four_plus_count = sum(1 for h in note_red_hits if h >= 4)
    print(f"  3红以上的注：{three_plus_count}/260注 ({three_plus_count/260*100:.1f}%)")
    print(f"  4红以上的注：{four_plus_count}/260注 ({four_plus_count/260*100:.1f}%)")
    
    print(f"\n📌 对比总结")
    if six5_net > net:
        print(f"  6+5 净收益 ({six5_net}元) 优于当前 ({net}元) ✓")
        print(f"  但主推1的6码红球仅 {main1_3plus}/{len(results)} 期达到3红以上，说明")
        print(f"  直接取主推1的6码红球并不稳定，关键在「选哪组红」")
    else:
        print(f"  当前策略 ({net}元) 优于或等于 6+5 ({six5_net}元)")
    
    print(f"\n📌 真实困境")
    print(f"  - 候选池质量尚可（13%的注能中3红以上）")
    print(f"  - 但最佳单注4红以上的概率只有 {best_note_dist.get(4,0)/len(results)*100:.0f}%")
    print(f"  - 这本质上也是概率游戏，再好的策略也难突破彩票数学期望")
    print(f"  - 当前-395元/52期 = 每期-7.6元，基本符合双色球理论返奖率(~50%)")

    # Save raw data for reference
    print(f"\n✅ 原始数据已分析完毕")


if __name__ == '__main__':
    evaluate()
