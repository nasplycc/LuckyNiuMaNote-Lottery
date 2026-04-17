# 双色球选号系统

[![GitHub](https://img.shields.io/github/v/tag/nasplycc/LuckyNiuMaNote-Lottery?label=version)](https://github.com/nasplycc/LuckyNiuMaNote-Lottery)
[![License](https://img.shields.io/github/license/nasplycc/LuckyNiuMaNote-Lottery)](LICENSE)

中国福利彩票双色球（SSQ）智能选号与复盘系统，基于历史数据的概率分析生成选号推荐。

## 📊 系统特点

- **历史数据库**：已收录 2003-2026 年共 3400+ 期开奖数据
- **概率分析**：热号/冷号统计、动态冷热周期、遗漏值计算
- **高级指标**：AC 值、极距、尾数和、形态筛选
- **蓝球策略**：分区 + 奇偶 + 遗漏多维度分析
- **多策略支持**：稳健/均衡/激进三种选号风格
- **开奖复盘**：命中对比、奖金计算、回测统计

## 🎯 开奖信息

| 项目 | 详情 |
|------|------|
| **彩票类型** | 中国福利彩票 - 双色球 |
| **开奖日期** | 每周二、四、日 |
| **开奖时间** | 21:15 |
| **玩法规则** | 从 01-33 选 6 个红球 + 从 01-16 选 1 个蓝球 |
| **单注成本** | 2 元 |
| **奖级数量** | 6 个奖级 |

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 依赖库：`requests`, `beautifulsoup4`

```bash
pip install requests beautifulsoup4
```

### 生成选号

```bash
cd lottery-ssq
python3 scripts/generate_ssq.py
```

**输出示例**：
```
🎰 双色球选号生成器 v2
========================================
📊 加载历史数据：3426 期

📋 选号摘要:
  主推1: 03 09 15 21 27 30 + 蓝 08
  主推2: 07 12 18 23 28 32 + 蓝 11
  备选1: 05 11 16 22 26 31 + 蓝 05
  备选2: 02 14 19 24 29 33 + 蓝 14
  备选3: 08 13 20 25 30 32 + 蓝 03

  总成本：10 元
```

### 开奖复盘

```bash
python3 scripts/review_ssq.py
```

功能：
- 自动获取最新开奖结果
- 对比上期选号命中情况
- 计算奖金总额
- 提供规则优化建议

### 更新历史数据

```bash
python3 scripts/update_ssq_history.py
```

自动从 500 彩票网抓取最新开奖数据，更新本地数据库。

### 回测分析

```bash
python3 scripts/backtest_ssq.py
```

测试选号策略在历史数据上的表现。

## 📁 目录结构

```
lottery-ssq/
├── config.json              # 配置参数（号码范围、规则约束等）
├── scripts/
│   ├── generate_ssq.py      # 选号生成器（主程序，v2）
│   ├── review_ssq.py        # 开奖复盘工具
│   ├── update_ssq_history.py # 历史数据更新脚本
│   └── backtest_ssq.py      # 回测分析工具
├── data/
│   └── ssq_history.csv      # 历史开奖数据（3400+ 期）
├── outputs/                  # 选号输出（JSON + Markdown）
├── docs/
│   ├── strategy.md          # 选号策略详解
│   └── PROMO_IMPLEMENTATION.md # 促销活动规则
├── README.md                # 本文档
└── SKILL.md                 # OpenClaw 技能说明
```

## 🏆 中奖规则

| 奖级 | 中奖条件 | 奖金 |
|------|----------|------|
| 一等奖 | 6 红 +1 蓝 | 浮动（约 500 万） |
| 二等奖 | 6 红 +0 蓝 | 浮动（约 10 万） |
| 三等奖 | 5 红 +1 蓝 | 3,000 元 |
| 四等奖 | 5 红 +0 蓝 或 4 红 +1 蓝 | 200 元 |
| 五等奖 | 4 红 +0 蓝 或 3 红 +1 蓝 | 10 元 |
| 六等奖 | 2 红 +1 蓝 或 1 红 +1 蓝 或 0 红 +1 蓝 | 5 元 |

## 📈 选号策略

### 核心规则（详见 `docs/strategy.md`）

1. **和值约束**：80-140（理论和值约 102）
2. **奇偶比**：优先 3:3、4:2、2:4
3. **分区比**：三区均衡（2:2:2、3:2:1、2:3:1 等）
4. **连号处理**：允许 0-2 组连号
5. **热冷搭配**：热号 2-3 个 + 冷号 1-2 个 + 温号补足
6. **蓝球策略**：分区 + 奇偶 + 遗漏综合判断

### 高级指标

- **AC 值**：号码复杂度指标，推荐 6-10
- **极距**：最大号 - 最小号，推荐 20-30
- **尾数和**：推荐 15-35
- **形态筛选**：排除极端形态（全奇、全偶、全大、全小）

### 策略有效性

基于 3400+ 期历史数据回测（滑动窗口 50 期）：
- 红球≥3 匹配：**21.9%**
- 红球≥4 匹配：**2.2%**
- 红球≥5 匹配：**0.09%**
- 蓝球命中：**11.8%**

## 🔧 配置说明

编辑 `config.json` 可调整选号参数：

```json
{
  "selection_rules": {
    "min_sum": 80,
    "max_sum": 140,
    "odd_even_ratios": ["3:3", "4:2", "2:4"],
    "zone_ratios": ["2:2:2", "3:2:1", "2:3:1"],
    "consecutive_max": 2,
    "ac_min": 6,
    "ac_max": 10,
    "span_min": 20,
    "span_max": 30
  },
  "strategies": ["balanced", "conservative", "aggressive"]
}
```

## 📝 输出格式

选号结果同时生成 JSON 和 Markdown 格式：

- `outputs/ssq-picks-YYYYMMDD-HHMMSS.json` - 机器可读格式
- `outputs/ssq-picks-YYYYMMDD-HHMMSS.md` - 人类可读格式

## 🎁 促销活动

系统支持促销活动期间的特殊选号规则，详见 `docs/PROMO_IMPLEMENTATION.md`。

当前活动：**为爱奔跑·双色球幸运加速**
- 活动期数：2026042-2026046
- 奖励规则：单注奖金≥1000 元时，额外奖励 10000 元（封顶）

## 📊 与七乐彩系统对比

| 特性 | 双色球 | 七乐彩 |
|------|--------|--------|
| 红球范围 | 01-33 选 6 | 01-30 选 7 |
| 蓝球/特号 | 01-16 选 1 | 01-30 选 1 |
| 开奖日期 | 二、四、日 | 一、三、五 |
| 单注成本 | 2 元 | 2 元 |
| 奖级数量 | 6 级 | 7 级 |
| 头奖概率 | 1/17,721,088 | 1/2,035,800 |
| 头奖奖金 | 约 500 万 | 约 100 万 |

> 💡 双色球奖金更高，但中奖概率也更低；七乐彩中奖概率约为双色球的 8.7 倍。

## ⚠️ 免责声明

- 本系统仅供娱乐参考，不保证中奖
- 彩票是概率游戏，不存在必中策略
- 请理性购彩，量力而行
- 建议单期投入不超过 50 元，月度预算不超过 200 元

## 📄 许可证

MIT License

## 🙏 致谢

- 数据来源：500 彩票网
- 关联项目：[lottery-qlc](https://github.com/nasplycc/lottery-qlc)（七乐彩选号系统）

---

*理性购彩，享受过程，不做"必中"幻想。*

**GitHub**: [nasplycc/LuckyNiuMaNote-Lottery](https://github.com/nasplycc/LuckyNiuMaNote-Lottery)
