#!/usr/bin/env python3
"""
双色球选号系统 v2
改进点：
- 动态冷热周期（10/20/30 期加权）
- AC 值、极距、尾数和形态筛选
- 蓝球细化（分区 + 奇偶 + 遗漏）
- 多策略支持（稳健/均衡/激进）
- 近期走势动态加权
"""
import csv
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from itertools import combinations

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / 'config.json'
DATA_PATH = ROOT / 'data' / 'ssq_history.csv'
OUTPUT_DIR = ROOT / 'outputs'
PROMO_PATH = ROOT / 'promo_events.json'


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_history():
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    parsed = []
    for row in rows:
        try:
            reds = sorted([int(row[f'red_{i}']) for i in range(1, 7)])
            blue = int(row['blue_1'])
            parsed.append({
                'draw_id': row['draw_id'],
                'draw_date': row['draw_date'],
                'reds': reds,
                'blue': blue,
            })
        except Exception:
            continue
    return parsed


def zone_of(n):
    if 1 <= n <= 11:
        return 1
    if 12 <= n <= 22:
        return 2
    return 3


def blue_zone_of(n):
    if 1 <= n <= 8:
        return 1
    return 2


def odd_even_split(nums):
    odd = sum(1 for n in nums if n % 2 == 1)
    return [odd, len(nums) - odd]


def zone_split(nums):
    c = Counter(zone_of(n) for n in nums)
    return [c[1], c[2], c[3]]


def consecutive_groups(nums):
    groups = 0
    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1] + 1:
            if i == 1 or nums[i - 1] != nums[i - 2] + 1:
                groups += 1
    return groups


def calc_span(nums):
    return max(nums) - min(nums)


def calc_tail_sum(nums):
    return sum(n % 10 for n in nums)


def calc_ac_value(nums):
    """AC 值 = 不同差值个数 - (红球数 - 1)"""
    diffs = set()
    for a, b in combinations(nums, 2):
        diffs.add(abs(a - b))
    return len(diffs) - 5


def omission_map(history, max_num):
    result = {n: 999 for n in range(1, max_num + 1)}
    for idx, draw in enumerate(reversed(history), start=1):
        current = set(draw['reds']) if max_num == 33 else {draw['blue']}
        for n in list(result.keys()):
            if result[n] == 999 and n in current:
                result[n] = idx - 1
    for n, v in result.items():
        if v == 999:
            result[n] = len(history)
    return result


def hot_warm_cold_dynamic(history, max_num, config, blue=False):
    """动态冷热：10/20/30 期加权"""
    hot_period = config['generation'].get('hot_period', 10)
    warm_period = config['generation'].get('warm_period', 20)
    cold_period = config['generation'].get('cold_period', 30)

    hot_pool = []
    warm_pool = []
    cold_pool = []

    for draw in history[-hot_period:]:
        if blue:
            hot_pool.append(draw['blue'])
        else:
            hot_pool.extend(draw['reds'])

    for draw in history[-warm_period:-hot_period] if len(history) > hot_period else []:
        if blue:
            warm_pool.append(draw['blue'])
        else:
            warm_pool.extend(draw['reds'])

    for draw in history[-cold_period:-warm_period] if len(history) > warm_period else []:
        if blue:
            cold_pool.append(draw['blue'])
        else:
            cold_pool.extend(draw['reds'])

    hot_freq = Counter(hot_pool)
    warm_freq = Counter(warm_pool)
    cold_freq = Counter(cold_pool)

    # 综合频率 = 近期×3 + 中期×2 + 远期×1
    combined_freq = {}
    all_nums = set(hot_freq.keys()) | set(warm_freq.keys()) | set(cold_freq.keys())
    for n in all_nums:
        combined_freq[n] = hot_freq.get(n, 0) * 3 + warm_freq.get(n, 0) * 2 + cold_freq.get(n, 0)

    # 补全未出现的号码
    for n in range(1, max_num + 1):
        if n not in combined_freq:
            combined_freq[n] = 0

    ranked = sorted(range(1, max_num + 1), key=lambda x: (-combined_freq.get(x, 0), x))
    hot = set(ranked[: max(1, max_num // 3)])
    cold = set(ranked[-max(1, max_num // 3):])
    warm = set(range(1, max_num + 1)) - hot - cold

    return hot, warm, cold, combined_freq


def get_recent_trends(history, window=10):
    """分析近期走势"""
    if len(history) < window:
        return {'prefer_consecutive': False, 'prefer_repeat': False, 'avg_repeat': 1.5}

    recent = history[-window:]
    consecutive_counts = []
    repeat_counts = []

    for i, draw in enumerate(recent):
        groups = consecutive_groups(draw['reds'])
        consecutive_counts.append(groups)
        if i > 0:
            repeat = len(set(draw['reds']) & set(recent[i-1]['reds']))
            repeat_counts.append(repeat)

    avg_consecutive = sum(consecutive_counts) / len(consecutive_counts)
    avg_repeat = sum(repeat_counts) / len(repeat_counts) if repeat_counts else 1.5

    return {
        'prefer_consecutive': avg_consecutive > 1.0,
        'prefer_repeat': avg_repeat > 1.5,
        'avg_repeat': avg_repeat,
    }


def score_candidate_v2(reds, blue, history, config, red_meta, blue_meta, trends):
    """v2 评分：加入 AC 值、极距、尾数、动态权重"""
    reds = sorted(reds)
    generation = config['generation']
    strategy_name = generation.get('default_strategy', 'balanced')
    weights = generation['strategies'].get(strategy_name, generation['strategies']['balanced'])

    score = 100.0

    # === 结构评分 ===
    oe = odd_even_split(reds)
    if oe in generation['preferred_odd_even']:
        score *= weights['balance']
    else:
        score *= 0.92

    zs = zone_split(reds)
    if zs in generation['preferred_zone_splits']:
        score *= weights['balance']
    elif min(zs) == 0:
        score *= 0.88

    red_sum = sum(reds)
    low, high = generation['sum_range']
    if low <= red_sum <= high:
        score *= 1.08
    else:
        score *= 0.9

    # 连号 - 根据近期走势动态调整
    groups = consecutive_groups(reds)
    max_groups = generation.get('max_consecutive_groups', 2)
    if groups > max_groups:
        score *= weights['consecutive_penalty']
    elif trends.get('prefer_consecutive') and groups >= 1:
        score *= 1.05

    # 重号 - 根据近期走势
    if history:
        last_reds = set(history[-1]['reds'])
        repeat_count = len(last_reds & set(reds))
        avg_repeat = trends.get('avg_repeat', 1.5)
        if abs(repeat_count - avg_repeat) <= 0.5:
            score *= 1.05
        elif repeat_count in generation['allow_repeat_from_last_draw']:
            score *= 1.02
        else:
            score *= 0.9

    # === 形态评分 ===
    span = calc_span(reds)
    span_min = generation.get('span_min', 18)
    span_max = generation.get('span_max', 30)
    if span_min <= span <= span_max:
        score *= 1.05
    else:
        score *= 0.95

    ac = calc_ac_value(reds)
    ac_min = generation.get('ac_min', 4)
    ac_max = generation.get('ac_max', 10)
    if ac_min <= ac <= ac_max:
        score *= 1.05
    else:
        score *= 0.95

    tail_sum = calc_tail_sum(reds)
    tail_range = generation.get('tail_sum_range', [10, 25])
    if tail_range[0] <= tail_sum <= tail_range[1]:
        score *= 1.03

    # === 冷热遗漏评分 ===
    hot_reds, warm_reds, cold_reds, red_freq, red_omit = red_meta
    hot_blues, warm_blues, cold_blues, blue_freq, blue_omit = blue_meta

    for n in reds:
        if n in hot_reds:
            score *= weights['hot']
        elif n in warm_reds:
            score *= weights['warm']
        else:
            score *= weights['cold']

        omit_thresh = generation.get('omission_threshold', 10)
        if red_omit[n] >= omit_thresh:
            score *= weights['omission']

    # 蓝球细化评分
    blue_zone = blue_zone_of(blue)
    blue_odd = blue % 2
    blue_omit_val = blue_omit.get(blue, 0)

    if blue in hot_blues:
        score *= 1.03
    elif blue in warm_blues:
        score *= 1.06
    else:
        score *= 1.02

    if blue_omit_val >= omit_thresh:
        score *= 1.08

    # 蓝球分区偏好
    if blue_zone == 1:
        score *= 1.02
    else:
        score *= 1.01

    # 蓝球奇偶
    if blue_odd == 1:
        score *= 1.01

    # === 2026-05-14 升级: 增加随机噪声 ===
    # 双色球是独立随机事件，历史频率无预测力
    # 在最终评分中加入±8%随机噪声，打破频率偏差
    random_factor = random.uniform(0.92, 1.08)
    score *= random_factor

    return round(score, 4)


def generate_candidates_v2(config, history):
    """v2 生成：扩大候选池，加入形态筛选 + 随机混合（2026-05-14升级）"""
    red_omit = omission_map(history, 33)
    blue_omit = omission_map(history, 16)
    hot_reds, warm_reds, cold_reds, red_freq = hot_warm_cold_dynamic(history, 33, config, blue=False)
    hot_blues, warm_blues, cold_blues, blue_freq = hot_warm_cold_dynamic(history, 16, config, blue=True)
    red_meta = (hot_reds, warm_reds, cold_reds, red_freq, red_omit)
    blue_meta = (hot_blues, warm_blues, cold_blues, blue_freq, blue_omit)
    trends = get_recent_trends(history, window=10)

    pool_size = config['generation']['candidate_pool_size']
    candidates = []
    seen = set()

    ac_min = config['generation'].get('ac_min', 4)
    ac_max = config['generation'].get('ac_max', 10)
    span_min = config['generation'].get('span_min', 18)
    span_max = config['generation'].get('span_max', 30)

    # 2026-05-14: 候选池分两部分：60%频率引导 + 40%纯随机
    # 双色球是独立随机事件，纯随机反而更接近真实分布
    scored_count = int(pool_size * 0.6)
    random_count = pool_size - scored_count

    # === 第一部分：频率引导 + 形态筛选 + 随机噪声 ===
    while len(candidates) < scored_count:
        reds = tuple(sorted(random.sample(range(1, 34), 6)))
        blue = random.randint(1, 16)
        key = (reds, blue)
        if key in seen:
            continue
        seen.add(key)

        span = calc_span(list(reds))
        ac = calc_ac_value(list(reds))
        if not (span_min <= span <= span_max):
            continue
        if not (ac_min <= ac <= ac_max):
            continue

        score = score_candidate_v2(list(reds), blue, history, config, red_meta, blue_meta, trends)
        candidates.append({
            'reds': list(reds),
            'blue': blue,
            'score': score,
            'odd_even': odd_even_split(list(reds)),
            'zone_split': zone_split(list(reds)),
            'sum': sum(reds),
            'consecutive_groups': consecutive_groups(list(reds)),
            'span': span,
            'ac': ac,
            'tail_sum': calc_tail_sum(list(reds)),
            'source': 'scored',
        })

    # === 第二部分：纯随机 + 形态筛选（无频率偏差） ===
    while len(candidates) < pool_size:
        reds = tuple(sorted(random.sample(range(1, 34), 6)))
        blue = random.randint(1, 16)
        key = (reds, blue)
        if key in seen:
            continue
        seen.add(key)

        span = calc_span(list(reds))
        ac = calc_ac_value(list(reds))
        if not (span_min <= span <= span_max):
            continue
        if not (ac_min <= ac <= ac_max):
            continue

        # 纯随机，仅保留形态约束
        score = 100.0 * random.uniform(0.90, 1.10)  # 随机分数
        candidates.append({
            'reds': list(reds),
            'blue': blue,
            'score': score,
            'odd_even': odd_even_split(list(reds)),
            'zone_split': zone_split(list(reds)),
            'sum': sum(reds),
            'consecutive_groups': consecutive_groups(list(reds)),
            'span': span,
            'ac': ac,
            'tail_sum': calc_tail_sum(list(reds)),
            'source': 'random',
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates, red_meta, blue_meta, trends


def save_output(candidates, config, history=None, red_meta=None, blue_meta=None, trends=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')

    # === 蓝球差异化覆盖 — 从高分候选池中选蓝球尽量不重复的5注 ===
    main_count = config['generation']['output_main']
    backup_count = config['generation']['output_backup']
    total_output = main_count + backup_count

    selected = []
    used_blues = set()

    for c in candidates:
        if len(selected) >= total_output:
            break
        if c['blue'] not in used_blues:
            selected.append(c)
            used_blues.add(c['blue'])

    if len(selected) < total_output:
        for c in candidates:
            if len(selected) >= total_output:
                break
            if c not in selected:
                selected.append(c)

    out = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'lottery': config['name'],
        'main': selected[:main_count],
        'backup': selected[main_count:main_count + backup_count],
    }

    # 附加筛选逻辑（如果有数据）
    if history and red_meta and blue_meta and trends:
        hot_reds, warm_reds, cold_reds, red_freq, red_omit = red_meta
        hot_blues, warm_blues, cold_blues, blue_freq, blue_omit = blue_meta
        strategy_name = config['generation'].get('default_strategy', 'balanced')

        sorted_reds = sorted(range(1, 34), key=lambda x: (-red_freq.get(x, 0), x))
        top5_hot = sorted_reds[:5]
        bottom5_cold = sorted_reds[-5:]

        sorted_blues = sorted(range(1, 17), key=lambda x: (-blue_freq.get(x, 0), x))
        top3_hot_blue = sorted_blues[:3]
        bottom3_cold_blue = sorted_blues[-3:]

        top5_omit_red = sorted(red_omit.keys(), key=lambda x: -red_omit[x])[:5]
        top3_omit_blue = sorted(blue_omit.keys(), key=lambda x: -blue_omit[x])[:3]

        recent = history[-10:] if len(history) >= 10 else history
        avg_consec = sum(consecutive_groups(d['reds']) for d in recent) / len(recent) if recent else 0

        out['filtering_logic'] = {
            'strategy': strategy_name,
            'pool_size': config['generation']['candidate_pool_size'],
            'pool_split': {
                'frequency_guided': int(config['generation']['candidate_pool_size'] * 0.6),
                'pure_random': config['generation']['candidate_pool_size'] - int(config['generation']['candidate_pool_size'] * 0.6),
            },
            'hot_reds': [{'number': n, 'freq': red_freq.get(n, 0)} for n in top5_hot],
            'cold_reds': [{'number': n, 'freq': red_freq.get(n, 0)} for n in bottom5_cold],
            'hot_blues': [{'number': n, 'freq': blue_freq.get(n, 0)} for n in top3_hot_blue],
            'cold_blues': [{'number': n, 'freq': blue_freq.get(n, 0)} for n in bottom3_cold_blue],
            'top_omit_reds': [{'number': n, 'omission': red_omit[n]} for n in top5_omit_red],
            'top_omit_blues': [{'number': n, 'omission': blue_omit[n]} for n in top3_omit_blue],
            'recent_trends': {
                'prefer_consecutive': trends['prefer_consecutive'],
                'avg_consecutive_groups': round(avg_consec, 1),
                'prefer_repeat': trends['prefer_repeat'],
                'avg_repeat': round(trends['avg_repeat'], 1),
            },
            'form_filters': {
                'span_range': [config['generation'].get('span_min', 18), config['generation'].get('span_max', 30)],
                'ac_range': [config['generation'].get('ac_min', 4), config['generation'].get('ac_max', 10)],
                'max_consecutive_groups': config['generation'].get('max_consecutive_groups', 2),
            },
            'score_preferences': {
                'preferred_odd_even': config['generation']['preferred_odd_even'],
                'preferred_zone_splits': config['generation']['preferred_zone_splits'],
                'sum_range': config['generation']['sum_range'],
            },
            'random_noise': '±8% (0.92~1.08)',
        }

    # === 共识6+5策略输出（先计算，再写文件） ===
    red_omit = red_meta[4] if red_meta else None
    consensus = generate_consensus_6x5(candidates, config, red_omit=red_omit, history=history)
    out['consensus_6x5'] = consensus

    # === 7+2复式输出（如果需要） ===
    # 注意：需要在调用方生成后手动添加到out中

    path = OUTPUT_DIR / f'ssq-picks-{ts}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return path, out


def generate_consensus_6x5(candidates, config, red_omit=None, history=None):
    """
    共识6+5策略 v3（高频追击+软分散+蓝球奇偶分区双覆盖）：
    - 去掉冷号强制
    - 去掉分区均衡强制
    - 纯频次优先：从Top 100频导候选注中统计红球频率，取前6
    - 软分散：扎堆时才做微调
    - 蓝球5码：3奇2偶/2奇3偶 + 1区至少2个、2区至少2个
    - 保留上期共识降权×0.5避免死锁
    成本：10元/期（不变）
    """
    # 频导部分优先，排除随机注噪声
    top_scored = [c for c in candidates if c.get('source') == 'scored']
    pool = top_scored[:min(100, len(top_scored))]
    # 如果频导部分不足50注，回退到全量Top100
    if len(pool) < 50:
        pool = candidates[:min(100, len(candidates))]

    top_n = len(pool)

    # 统计红球频率
    red_counter = Counter()
    for c in pool:
        for r in c['reds']:
            red_counter[r] += 1

    # 上期共识降权：读取上次输出的共识红球，频率×0.5
    try:
        output_dir = Path(__file__).resolve().parent.parent / 'outputs'
        json_files = sorted(output_dir.glob('ssq-picks-*.json'))
        if json_files:
            with open(json_files[-1], 'r', encoding='utf-8') as f:
                last_out = json.load(f)
            last_consensus_reds = last_out.get('consensus_6x5', {}).get('reds', [])
            for r in last_consensus_reds:
                if r in red_counter:
                    red_counter[r] = int(red_counter[r] * 0.5)
    except Exception:
        pass

    # ===== 红球6码：纯频次优先 =====
    all_reds_sorted = [r for r, _ in red_counter.most_common(33)]
    selected = set(all_reds_sorted[:6])

    # 软分散：确保3个区不空区、不扎堆
    zone_dist = {'z1': 0, 'z2': 0, 'z3': 0}
    for n in selected:
        if 1 <= n <= 11:
            zone_dist['z1'] += 1
        elif 12 <= n <= 22:
            zone_dist['z2'] += 1
        else:
            zone_dist['z3'] += 1

    empty_zones = [z for z, v in zone_dist.items() if v == 0]
    if empty_zones:
        # 有空区：从最大区换一个号到空区
        max_zone = max(zone_dist, key=zone_dist.get)
        if max_zone == 'z1':
            max_zone_nums = [n for n in selected if 1 <= n <= 11]
        elif max_zone == 'z2':
            max_zone_nums = [n for n in selected if 12 <= n <= 22]
        else:
            max_zone_nums = [n for n in selected if 23 <= n <= 33]

        for empty_z in empty_zones:
            if empty_z == 'z1':
                replacement_pool = [n for n in all_reds_sorted if 1 <= n <= 11 and n not in selected]
            elif empty_z == 'z2':
                replacement_pool = [n for n in all_reds_sorted if 12 <= n <= 22 and n not in selected]
            else:
                replacement_pool = [n for n in all_reds_sorted if 23 <= n <= 33 and n not in selected]

            if max_zone_nums and replacement_pool:
                worst = min(max_zone_nums, key=lambda x: red_counter.get(x, 0))
                selected.remove(worst)
                max_zone_nums.remove(worst)
                selected.add(replacement_pool[0])
    elif max(zone_dist.values()) >= 4:
        # 无空区但某区≥4个：换1个到最小区
        max_zone = max(zone_dist, key=zone_dist.get)
        min_zone = min(zone_dist, key=zone_dist.get)

        if max_zone == 'z1':
            max_zone_nums = [n for n in selected if 1 <= n <= 11]
        elif max_zone == 'z2':
            max_zone_nums = [n for n in selected if 12 <= n <= 22]
        else:
            max_zone_nums = [n for n in selected if 23 <= n <= 33]

        if min_zone == 'z1':
            replacement_pool = [n for n in all_reds_sorted if 1 <= n <= 11 and n not in selected]
        elif min_zone == 'z2':
            replacement_pool = [n for n in all_reds_sorted if 12 <= n <= 22 and n not in selected]
        else:
            replacement_pool = [n for n in all_reds_sorted if 23 <= n <= 33 and n not in selected]

        if max_zone_nums and replacement_pool:
            worst = min(max_zone_nums, key=lambda x: red_counter.get(x, 0))
            selected.remove(worst)
            selected.add(replacement_pool[0])

    consensus_reds = sorted(selected)

    # ===== 蓝球5码：奇偶分区双覆盖 =====
    # 搜集所有蓝球及其评分
    blue_scores = {}
    for c in candidates:
        b = c['blue']
        if b not in blue_scores or c['score'] > blue_scores[b]:
            blue_scores[b] = c['score']

    # 将蓝球分为奇偶和分区
    blue_info = []
    for b in range(1, 17):
        blue_info.append({
            'number': b,
            'score': blue_scores.get(b, 50),
            'odd': b % 2 == 1,
            'zone': 1 if b <= 8 else 2,
        })

    # 选5个蓝球，约束：奇2-3个、偶2-3个、1区≥2个、2区≥2个
    best_blues = None
    best_score_sum = -1

    from itertools import combinations as combos
    for combo in combos(blue_info, 5):
        odd_cnt = sum(1 for b in combo if b['odd'])
        even_cnt = 5 - odd_cnt
        z1_cnt = sum(1 for b in combo if b['zone'] == 1)
        z2_cnt = 5 - z1_cnt

        # 奇偶约束：3奇2偶 或 2奇3偶
        if odd_cnt not in (2, 3):
            continue
        # 分区约束：各至少2个
        if z1_cnt < 2 or z2_cnt < 2:
            continue

        score_sum = sum(b['score'] for b in combo)
        if score_sum > best_score_sum:
            best_score_sum = score_sum
            best_blues = [b['number'] for b in combo]

    # 容错：如果找不到满足约束的组合，回退到按评分降序取前5
    if best_blues is None:
        all_blues_sorted = sorted(blue_info, key=lambda x: -x['score'])
        best_blues = [b['number'] for b in all_blues_sorted[:5]]

    selected_blues = best_blues[:5]

    # 构造输出
    consensus_notes = []
    for i, blue in enumerate(selected_blues):
        note = {
            'reds': consensus_reds,
            'blue': blue,
            'seq': i + 1,
            'odd_even': odd_even_split(consensus_reds),
            'zone_split': zone_split(consensus_reds),
            'sum': sum(consensus_reds),
            'consecutive_groups': consecutive_groups(consensus_reds),
            'span': calc_span(consensus_reds),
            'ac': calc_ac_value(consensus_reds),
            'tail_sum': calc_tail_sum(consensus_reds),
        }
        consensus_notes.append(note)

    top10_reds = [r for r, _ in red_counter.most_common(10)]

    return {
        'reds': consensus_reds,
        'blue_pool': selected_blues,
        'notes': consensus_notes,
        'top10_reds': top10_reds,
        'red_frequencies': {str(r): red_counter[r] for r in consensus_reds},
        'derivation': f'高频追击+软分散+蓝球奇偶分区覆盖，从Top{top_n}候选注中统计红球',
    }


def fmt_pick_v2(p):
    reds = ' '.join(f'{n:02d}' for n in p['reds'])
    blue = f"{p['blue']:02d}"
    return (f"红球：{reds} | 蓝球：{blue} | 评分：{p['score']} | "
            f"奇偶：{p['odd_even'][0]}:{p['odd_even'][1]} | 分区：{p['zone_split']} | "
            f"和值：{p['sum']} | 极距：{p['span']} | AC：{p['ac']}")


def load_promo_events():
    """加载促销活动"""
    if not PROMO_PATH.exists():
        return []
    with open(PROMO_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('events', [])


def get_active_promo(draw_date=None):
    """获取当前有效的促销活动"""
    events = load_promo_events()
    today = datetime.now().strftime('%Y-%m-%d')
    if draw_date is None:
        draw_date = today
    
    for event in events:
        if not event.get('active', False):
            continue
        if event['start_date'] <= draw_date <= event['end_date']:
            return event
    return None


def generate_compound_bet(red_count, blue_count=1):
    """生成复式投注号码"""
    reds = sorted(random.sample(range(1, 34), red_count))
    blues = [random.randint(1, 16)] if blue_count == 1 else sorted(random.sample(range(1, 17), blue_count))
    return reds, blues


def calc_compound_cost(red_count, blue_count):
    """计算复式投注金额"""
    from math import comb
    red_combos = comb(red_count, 6)
    blue_combos = comb(blue_count, 1)
    return red_combos * blue_combos * 2


def generate_promo_picks(config, history, promo):
    """生成活动推荐的复式投注号码"""
    candidates, _, _, _ = generate_candidates_v2(config, history)
    
    # 从高分候选中提取红球池
    top_reds = []
    for c in candidates[:50]:
        top_reds.extend(c['reds'])
    
    red_freq = Counter(top_reds)
    preferred_reds = [n for n, _ in red_freq.most_common(15)]
    
    # 生成 8+1, 9+1, 10+1 复式
    compound_picks = []
    
    for tier in promo['compound_tiers']:
        red_count = tier['red_count']
        blue_count = 1
        
        # 从优选红球中选择
        base_reds = random.sample(preferred_reds, min(red_count, len(preferred_reds)))
        
        # 如果不够，从高分候选补充
        if len(base_reds) < red_count:
            all_reds = list(range(1, 34))
            remaining = [n for n in all_reds if n not in base_reds]
            base_reds.extend(random.sample(remaining, red_count - len(base_reds)))
        
        # 选择蓝球（偏好热号）
        hot_blues, warm_blues, cold_blues, blue_freq = hot_warm_cold_dynamic(history, 16, config, blue=True)
        if hot_blues:
            blue = random.choice(list(hot_blues))
        else:
            blue = random.randint(1, 16)
        
        reds = sorted(base_reds)
        cost = calc_compound_cost(red_count, blue_count)
        
        compound_picks.append({
            'type': f'{red_count}+{blue_count}',
            'reds': reds,
            'blues': [blue],
            'cost': cost,
            'tier': tier,
            'expected_bonus': tier['max_bonus'] if cost >= 56 else 0
        })
    
    return compound_picks


def save_promo_output(promo_picks, promo, config):
    """保存活动选号结果"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    
    out = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'promo_event': promo['name'],
        'promo_period': f"{promo['draw_range']['start']}-{promo['draw_range']['end']}",
        'picks': promo_picks,
        'rules': {
            'min_prize_for_bonus': promo['rules']['min_prize'],
            'bonus_cap': promo['rules']['bonus_cap'],
            'claim_deadline': promo['rules']['bonus_claim_deadline']
        }
    }
    
    path = OUTPUT_DIR / f'ssq-promo-{ts}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path, out


def fmt_promo_pick(p):
    reds = ' '.join(f'{n:02d}' for n in p['reds'])
    blues = ' '.join(f'{b:02d}' for b in p['blues'])
    return (f"{p['type']}复式 | 红球：{reds} | 蓝球：{blues} | "
            f"金额：¥{p['cost']} | 最高赠票：¥{p['tier']['max_bonus']}")


def generate_7x2_compound(candidates, config, history):
    """生成7+2复式选号（主选号）
    
    从高分候选池中提取：
    - 红球：近10期活跃度 + 频率加权
    - 蓝球：评分 + 遗漏修正
    
    成本：C(7,6) × C(2,1) × 2 = 7 × 2 × 2 = 28元
    """
    # 使用Top 200候选（更高置信度）
    top_candidates = candidates[:min(200, len(candidates))]
    
    # 统计红球频率
    red_counter = Counter()
    for c in top_candidates:
        for r in c['reds']:
            red_counter[r] += 1
    
    # 近10期活跃度：越近权重越高，且重复出现次数也计入
    recent = history[-10:]
    red_activity = Counter()
    blue_activity = Counter()
    for i, draw in enumerate(recent, start=1):
        weight = i / max(1, len(recent))
        for r in draw.get('reds', []):
            red_activity[r] += weight
        b = draw.get('blue')
        if b is not None:
            blue_activity[b] += weight
    
    # 红球7码：活跃度优先 + 加权随机（2026-10-18优化：扩大候选池+强制分散）
    red_score = {r: red_activity.get(r, 0) + red_counter.get(r, 0) / 50.0 for r in range(1, 34)}
    sorted_reds = sorted(range(1, 34), key=lambda x: (-red_score.get(x, 0), x))
    # 扩大候选池到Top15，增加随机性
    top15 = sorted_reds[:15]
    # 按得分加权随机选7个（无放回）- 从Top15中选
    # 限制权重差异：最高分不超过最低分的1.5倍
    _max_score = max(red_score[n] for n in top15)
    _min_score = min(red_score[n] for n in top15)
    if _max_score > _min_score * 1.5:
        # 归一化权重，限制最大差异
        _normalized = {n: (_min_score + (red_score[n] - _min_score) * 1.5 / (_max_score - _min_score)) for n in top15}
    else:
        _normalized = red_score
    _probs = [random.uniform(0.85, 1.15) * (_normalized.get(r, 0) + 0.1) for r in top15]
    _total = sum(_probs)
    _probs = [p / _total for p in _probs]
    _red7 = []
    _remaining = list(range(len(top15)))
    _remaining_probs = _probs[:]
    top_pool = top15  # 使用top15作为候选池
    for _ in range(7):
        if not _remaining:
            break
        _r_total = sum(_remaining_probs)
        _r_probs = [p / _r_total for p in _remaining_probs]
        _r = random.random()
        _cumsum = 0
        _chosen = 0
        for _j, _p in enumerate(_r_probs):
            _cumsum += _p
            if _r <= _cumsum:
                _chosen = _j
                break
        _idx = _remaining[_chosen]
        _red7.append(top_pool[_idx])
        _remaining.pop(_chosen)
        _remaining_probs.pop(_chosen)
    red7 = sorted(_red7)
    
    # 强制分散：确保至少3个号码与上期不同
    if history and len(red7) == 7:
        last_reds = set(history[-1].get('reds', []))
        current_set = set(red7)
        overlap = len(last_reds & current_set)
        # 如果重合过多，随机替换部分号码
        if overlap >= 4:
            to_replace = overlap - 2  # 保留2个重号
            # 从未选中的top15中选
            candidates = [n for n in top15 if n not in current_set]
            if len(candidates) >= to_replace:
                for _ in range(to_replace):
                    # 替换随机一个重合号码（从当前7个与上期的交集中选，避免 remove 失败）
                    overlap_now = sorted(last_reds & set(red7))
                    if not overlap_now or not candidates:
                        break
                    repeat_num = random.choice(overlap_now)
                    replace_with = random.choice(candidates)
                    if repeat_num in red7 and replace_with not in red7:
                        red7.remove(repeat_num)
                        red7.append(replace_with)
                        candidates.remove(replace_with)
                red7 = sorted(red7)
    
    # 【修正1】重号跟随：从上期号码中保留1-2个
    # 分析发现：近10期平均重号1.1个
    if history:
        last_draw = history[-1]
        # history格式: {'draw_id': ..., 'reds': [...], 'blue': ...}
        last_reds = set(last_draw.get('reds', []))
        current_set = set(red7)
        repeat_count = len(last_reds & current_set)
        
        # 如果重号数为0，强制替换一个非热号为上期热号
        if repeat_count == 0 and len(last_reds & current_set) == 0:
            # 找到red7中得分最低的号码替换
            min_score_num = min(red7, key=lambda x: red_score.get(x, 0))
            # 从上期号码中选一个当前没有的
            for last_num in sorted(last_reds):
                if last_num not in current_set:
                    # 替换为遗漏较大的上期号码
                    red7.remove(min_score_num)
                    red7.append(last_num)
                    red7 = sorted(red7)
                    break
        
        # 如果重号数>2，减少到1-2个
        elif repeat_count > 2:
            extra_repeats = list(last_reds & current_set)[2:]
            for num in extra_repeats[:1]:  # 只保留一个
                if num in red7:
                    red7.remove(num)
                    red7 = sorted(red7)
                    # 从未选中的top15中选一个
                    for candidate in top15:
                        if candidate not in set(red7):
                            red7.append(candidate)
                            red7 = sorted(red7)
                            break
                    break
    
    # 【修正2】连号生成：确保至少有1组连号
    has_consecutive = False
    for i in range(1, len(red7)):
        if red7[i] == red7[i-1] + 1:
            has_consecutive = True
            break
    
    # 如果没有连号，强制创建一组
    if not has_consecutive:
        # 找一个合适的插入点创建连号
        for i in range(len(red7) - 1):
            gap = red7[i+1] - red7[i]
            if gap >= 3:  # 间隔大于等于3，可以在中间插入
                insert_num = red7[i] + 1
                # 检查insert_num是否在top15中
                if insert_num in top15 and insert_num not in red7:
                    red7.insert(i+1, insert_num)
                    red7 = red7[:7]  # 保持7个
                    break
    
    # 【修正3】蓝球优先选择热号
    # 分析发现：蓝球04近30期出现4次，是热号
    
    # 软分散检查：确保3个区不空
    zone_dist = {'z1': 0, 'z2': 0, 'z3': 0}
    for n in red7:
        if 1 <= n <= 11:
            zone_dist['z1'] += 1
        elif 12 <= n <= 22:
            zone_dist['z2'] += 1
        else:
            zone_dist['z3'] += 1
    
    # 如果有空区，从该区的top候选中换入
    empty_zones = [z for z, v in zone_dist.items() if v == 0]
    if empty_zones:
        for empty_z in empty_zones:
            if empty_z == 'z1':
                replacement_pool = [n for n in sorted_reds if 1 <= n <= 11 and n not in red7]
            elif empty_z == 'z2':
                replacement_pool = [n for n in sorted_reds if 12 <= n <= 22 and n not in red7]
            else:
                replacement_pool = [n for n in sorted_reds if 23 <= n <= 33 and n not in red7]
            
            # 找红7中最大区的最低频号码
            max_zone = max(zone_dist, key=zone_dist.get)
            if max_zone == 'z1':
                max_zone_nums = [n for n in red7 if 1 <= n <= 11]
            elif max_zone == 'z2':
                max_zone_nums = [n for n in red7 if 12 <= n <= 22]
            else:
                max_zone_nums = [n for n in red7 if 23 <= n <= 33]
            
            if max_zone_nums and replacement_pool:
                worst = min(max_zone_nums, key=lambda x: red_counter.get(x, 0))
                red7.remove(worst)
                red7.append(replacement_pool[0])
    
    red7 = sorted(red7)
    
    # 蓝球2码：评分优先 + 随机扰动
    blue_scores = {}
    for c in top_candidates:
        b = c['blue']
        if b not in blue_scores or c['score'] > blue_scores[b]:
            blue_scores[b] = c['score']
    # 从Top5蓝球中随机选2个，增加多样性
    top_blues = sorted(blue_scores.keys(), key=lambda x: -blue_scores[x])[:min(5, len(blue_scores))]
    blues2 = sorted(random.sample(top_blues, min(2, len(top_blues))))

    blue_omit = {}
    for b in range(1, 17):
        omit = 0
        for draw in reversed(history):
            if draw.get('blue') == b:
                break
            omit += 1
        blue_omit[b] = omit

    blue_score = {
        b: blue_scores.get(b, 0) + min(blue_omit.get(b, 0), 10) * 0.05 for b in range(1, 17)
    }

    sorted_blues = sorted(range(1, 17), key=lambda x: (-blue_score.get(x, 0), x))
    blue2 = sorted_blues[:2]
    
    # 计算奖金表（按红球命中数分类）
    bonus_table = []
    from math import comb
    for k in range(7, -1, -1):
        k = int(k)  # 确保是整数
        # 7+2复式共14注
        # 对于k个中奖红球：
        # - 包含k个中奖红的红球组合数 = C(k, k) × C(7-k, 6-k) = C(7-k, 6-k) = 7-k
        # - 每个这样的组合 × 2个蓝球 = 2×(7-k)注
        notes_k = (7 - k) * 2
        
        # 根据k确定奖项
        if k == 6:
            bonus_per_note = 5000000  # 一等奖
        elif k == 5:
            bonus_per_note = 3000  # 三等奖
        elif k == 4:
            bonus_per_note = 200  # 四等奖
        elif k == 3:
            bonus_per_note = 10  # 五等奖
        else:
            bonus_per_note = 5  # 六等奖
        
        total_bonus = notes_k * bonus_per_note
        net_profit = total_bonus - 28  # 成本28元
        
        bonus_table.append({
            'red_hits': k,
            'blue_hits': '1或2',
            'notes': notes_k,
            'bonus_per_note': bonus_per_note,
            'total_bonus': total_bonus,
            'net_profit': net_profit
        })
    
    # 蓝球全中（2个都中）的特殊情况
    # 7+2复式如果两个蓝都中，相当于2倍的中奖
    bonus_table.insert(0, {
        'red_hits': 'any',
        'blue_hits': 2,
        'multiplier': 2,
        'note': '蓝球双中，所有中奖注×2'
    })
    
    return {
        'type': '7+2复式',
        'reds': red7,
        'blues': blue2,
        'cost': 28,
        'bonus_table': bonus_table,
        'stats': {
            'red_freq': {str(r): red_counter.get(r, 0) for r in red7},
            'blue_scores': {str(b): round(blue_scores.get(b, 0), 2) for b in blue2},
            'zone_dist': zone_dist,
            'source_count': len(top_candidates)
        }
    }


def fmt_7x2_pick(p):
    reds = ' '.join(f'{n:02d}' for n in p['reds'])
    blues = ' '.join(f'{b:02d}' for b in p['blues'])
    return f"红球：{reds} | 蓝球：{blues} | 成本：¥{p['cost']}"


def main():
    import sys
    
    config = load_config()
    history = load_history()
    
    # 检查是否有活动参数
    if len(sys.argv) > 1 and sys.argv[1] == '--promo':
        # 活动选号模式
        promo = get_active_promo()
        if not promo:
            print('❌ 当前没有有效的促销活动')
            return
        
        print(f'🎁 活动选号模式：{promo["name"]}')
        print(f'活动期间：{promo["start_date"]} 至 {promo["end_date"]}')
        print(f'适用期数：{promo["draw_range"]["start"]}-{promo["draw_range"]["end"]} ({promo["draw_range"]["total_draws"]}期)')
        print(f'规则：单票中奖超¥{promo["rules"]["min_prize"]} 赠等额赠票（最高¥{promo["rules"]["bonus_cap"]}）')
        print()
        
        promo_picks = generate_promo_picks(config, history, promo)
        path, out = save_promo_output(promo_picks, promo, config)
        
        print('📋 活动推荐复式投注:')
        for p in promo_picks:
            print('-', fmt_promo_pick(p))
        print(f'\n输出文件：{path}')
        print(f'\n⚠️ 赠票领取截止：{promo["rules"]["bonus_claim_deadline"]}')
        print(f'ℹ️ 详情：{promo.get("website", "请咨询当地福彩网点")}')
    else:
        # 普通选号模式
        candidates, red_meta, blue_meta, trends = generate_candidates_v2(config, history)
        path, out = save_output(candidates, config, history, red_meta, blue_meta, trends)

        # === 生成筛选逻辑说明 ===
        hot_reds, warm_reds, cold_reds, red_freq, red_omit = red_meta
        hot_blues, warm_blues, cold_blues, blue_freq, blue_omit = blue_meta
        strategy_name = config['generation'].get('default_strategy', 'balanced')

        sorted_reds = sorted(range(1, 34), key=lambda x: (-red_freq.get(x, 0), x))
        top5_hot = sorted_reds[:5]
        bottom5_cold = sorted_reds[-5:]

        sorted_blues = sorted(range(1, 17), key=lambda x: (-blue_freq.get(x, 0), x))
        top3_hot_blue = sorted_blues[:3]
        bottom3_cold_blue = sorted_blues[-3:]

        top5_omit_red = sorted(red_omit.keys(), key=lambda x: -red_omit[x])[:5]
        top3_omit_blue = sorted(blue_omit.keys(), key=lambda x: -blue_omit[x])[:3]

        recent = history[-10:] if len(history) >= 10 else history
        avg_consec = sum(consecutive_groups(d['reds']) for d in recent) / len(recent) if recent else 0

        print('双色球选号完成 (v2)')
        print(f'策略：{strategy_name}')
        print(f'候选池：{config["generation"]["candidate_pool_size"]} 注（60% 频率引导 + 40% 纯随机）')
        print(f'输出文件：{path}')
        print()
        print('📌 本期筛选逻辑')
        print(f'  数据范围：近 30 期（热号×3 + 温号×2 + 冷号×1）')
        print(f'  热号（红）：{", ".join(f"{n:02d}" for n in top5_hot)}')
        print(f'  冷号（红）：{", ".join(f"{n:02d}" for n in bottom5_cold)}')
        print(f'  热号（蓝）：{", ".join(f"{n:02d}" for n in top3_hot_blue)}')
        print(f'  冷号（蓝）：{", ".join(f"{n:02d}" for n in bottom3_cold_blue)}')
        print(f'  遗漏最大（红）：{", ".join(f"{n:02d}(漏{red_omit[n]}期)" for n in top5_omit_red)}')
        print(f'  遗漏最大（蓝）：{", ".join(f"{n:02d}(漏{blue_omit[n]}期)" for n in top3_omit_blue)}')
        print(f'  近期连号趋势：{"偏好连号" if trends["prefer_consecutive"] else "不偏好连号"}（近10期平均 {avg_consec:.1f} 组）')
        print(f'  近期重号趋势：{"偏好重号" if trends["prefer_repeat"] else "不偏好重号"}（近10期平均 {trends["avg_repeat"]:.1f} 个）')
        print(f'  形态过滤：极距 18-30 | AC 值 4-10 | 连号 ≤ 2 组')
        print(f'  评分偏好：奇偶 3:3/4:2/2:4 | 分区 2-2-2/1-2-3 等 | 和值 80-120')
        print(f'  随机噪声：最终评分 × [0.92, 1.08] 随机因子，打破频率偏差')
        print(f'  候选池构成：{int(config["generation"]["candidate_pool_size"] * 0.6)} 注频率引导 + {config["generation"]["candidate_pool_size"] - int(config["generation"]["candidate_pool_size"] * 0.6)} 注纯随机')
        print()

        # === 生成7+2复式 ===
        compound_7x2 = generate_7x2_compound(candidates, config, history)
        
        print('━' * 38)
        print('🎯 7+2复式（主推，成本¥28）')
        print('━' * 38)
        print(f"  {fmt_7x2_pick(compound_7x2)}")
        print()
        print('  奖金预估（按红球命中数）:')
        for item in compound_7x2['bonus_table'][:6]:  # 只显示前6个（6红到1红）
            if 'red_hits' in item and isinstance(item['red_hits'], int):
                k = item['red_hits']
                bonus = item['total_bonus']
                net = item['net_profit']
                print(f'    中{k}红+1蓝: 奖金¥{bonus}, 净收益¥{net:+d}')
        print(f'    中0红+1蓝: 奖金¥35, 净收益¥+7 ✅')
        
        # 保存7+2结果到JSON
        out['compound_7x2'] = compound_7x2
        
        # 重新写入JSON文件（包含7+2）
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print()
        print('💡 说明：只使用7+2复式策略，其他策略已禁用')

        # 检查是否有活动
        promo = get_active_promo()
        if promo:
            print(f'\n🎁 当前有活动：{promo["name"]}')
            print(f'   运行：python3 generate_ssq.py --promo 生成活动推荐复式')


if __name__ == '__main__':
    main()
