# eventFlag 测试记录

> 目的：搞清 `LotResultMapPatternFlag` 到底怎么写才是「游戏里能生效」的。
> 测试专用 bin：`C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin`
> 工具：本编辑器（写好 → 自动记一条进 `work/flag_tests.json`）

## 现在的理解（半成品，待验）

| 概念 | 位置 | 说明 |
|---|---|---|
| `modifierSet` | 结果表 / base 表都有 | 槽位族（同一族里选一个） |
| `modifier` | 同上 | 族内选项 |
| `eventFlag` | 同上 | 事件旗标；**可以重复用**，不要求全局唯一 |
| `weight` | base 表 | 族内抽取概率 |
| `_id` | 每张表 | **不能重复**（写回用 max+1） |

- 结果行的三元组必须能在 `LotBaseMapPatternFlag` 里找到（1649 条里 1595 条完全对得上）。
- 每个 patternId 每个 `modifierSet` 只出现一次（set 0 例外，两行）。
- `7535 / 99999` = 首次胜利记录，新种子不写。
- DLC 少数行那一列放的是 float32（0.04~0.65），只读不碰。

## 测试记录

写入工具自动记录在 `work/flag_tests.json`，界面上有「eventFlag 测试记录」卡片。
本文件用来写**人话结论**（每次测试：改了什么 → 游戏里看到什么）。

| # | 时间 | patternId | 改动 | 游戏内现象 | 结论 |
|---|------|-----------|------|-----------|------|
| 1 | | | 原样照抄模板 | | |
| 2 | | | | | |

## 待验证的问题

1. 新种子能不能被抽到（`patternCount` / `weight`）？
2. 换一个 `modifier`（同族）游戏里会不会变？
3. 同一个 `eventFlag` 被两个种子共用，会不会互相影响？
4. `modifierSet` 到底对应什么（缩圈？地形？事件组？）
