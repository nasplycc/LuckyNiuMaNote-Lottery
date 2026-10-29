# 彩票选号系统总览

本目录汇总 Jaben 使用的两个彩票选号系统。

## 📊 系统列表

| 系统 | 仓库 | 彩票类型 | 开奖日期 | 历史数据 |
|------|------|----------|----------|----------|
| **双色球** | [LuckyNiuMaNote-Lottery](https://github.com/nasplycc/LuckyNiuMaNote-Lottery) | 双色球 (SSQ) | 二、四、日 21:15 | 3400+ 期 (2003-2026) |
| **七乐彩** | [lottery-qlc](https://github.com/nasplycc/lottery-qlc) | 七乐彩 (QLC) | 一、三、五 21:15 | 2921 期 (2007-2026) |

## 🎯 快速链接

### 双色球系统
- **GitHub**: https://github.com/nasplycc/LuckyNiuMaNote-Lottery
- **README**: [查看文档](https://github.com/nasplycc/LuckyNiuMaNote-Lottery/blob/master/README.md)
- **策略文档**: [docs/strategy.md](https://github.com/nasplycc/LuckyNiuMaNote-Lottery/blob/master/docs/strategy.md)

### 七乐彩系统
- **GitHub**: https://github.com/nasplycc/lottery-qlc
- **README**: [查看文档](https://github.com/nasplycc/lottery-qlc/blob/main/README.md)
- **策略文档**: [docs/strategy.md](https://github.com/nasplycc/lottery-qlc/blob/main/docs/strategy.md)

## 📅 开奖日程

| 星期 | 彩票类型 | 时间 |
|------|----------|------|
| 周一 | 七乐彩 | 21:15 |
| 周二 | 双色球 | 21:15 |
| 周三 | 七乐彩 | 21:15 |
| 周四 | 双色球 | 21:15 |
| 周五 | 七乐彩 | 21:15 |
| 周六 | - | - |
| 周日 | 双色球 | 21:15 |

## 🔧 本地使用

### 双色球
```bash
cd /home/Jaben/.openclaw/workspace-finnace-bot/lottery-ssq
python3 scripts/generate_ssq.py      # 生成选号
python3 scripts/review_ssq.py        # 开奖复盘
python3 scripts/update_ssq_history.py # 更新数据
python3 scripts/backtest_ssq.py      # 回测分析
```

### 七乐彩
```bash
cd /home/Jaben/.openclaw/workspace-finnace-bot/lottery-qlc
python3 scripts/generate_qlc.py      # 生成选号
python3 scripts/review_qlc.py        # 开奖复盘
python3 scripts/update_qlc_history.py # 更新数据
```

## 📊 系统对比

| 特性 | 双色球 | 七乐彩 |
|------|--------|--------|
| 红球范围 | 01-33 选 6 | 01-30 选 7 |
| 蓝球/特号 | 01-16 选 1 | 01-30 选 1 |
| 单注成本 | 2 元 | 2 元 |
| 奖级数量 | 6 级 | 7 级 |
| 头奖概率 | 1/17,721,088 | 1/2,035,800 |
| 头奖奖金 | 约 500 万 | 约 100 万 |
| 系统版本 | v2 | v1 |

## 💡 使用建议

1. **理性购彩**：单期不超过 50 元，月度不超过 200 元
2. **纪律执行**：坚持既定策略，不盲目追号
3. **定期复盘**：每期开奖后查看复盘报告
4. **心态管理**：彩票是概率游戏，无必中策略

## ⚠️ 免责声明

- 本系统仅供娱乐参考，不保证中奖
- 彩票是概率游戏，不存在必中策略
- 请理性购彩，量力而行

---

*理性购彩，享受过程，不做"必中"幻想。*
