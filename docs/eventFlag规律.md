# eventFlag / modifier / modifierSet 规律（自查笔记）

> m05915 给的方向：`LotResultMapPatternFlag.eventFlag` 与 `LotBaseMapPatternFlag.eventFlag` 对应；同一 patternId 里有这个 flag 就等于调用了它；modifier / modifierSet 也要填对。
> 下面是把 regulation.bin（`D:\nrtest\base.bin`）里两表全量比对后的结果。

## 一、两表的职责

| 表 | 行数 | 作用 |
|---|---|---|
| `LotBaseMapPatternFlag` | 257 | **可调用清单**：一条 = 一种可被调用的「事件 / 地图变体 / 宝箱组 / 难度档」，带 `weight` 和名字 |
| `LotResultMapPatternFlag` | 5752 | **实际调用**：每个 patternId 一行一个调用，写明调的是哪条 |

两表字段（关键三列两边同名同义）：

```
LotBaseMapPatternFlag : unknown_0, modifierSet, requireModifier1/2, excludeModifier1/2, modifier, eventFlag, weight
LotResultMapPatternFlag: unknown_0, patternId, modifierSet, modifier, eventFlag, patternSetId, targetBoss, rareMap
```

**判等用的是三元组 `(eventFlag, modifier, modifierSet)`**，不是只看 eventFlag。

## 二、对得上的比例

- 结果表里带 flag（`eventFlag != 0`）的行：**1649** 条
- 其中三元组能在 base 表里找到**完全相同**的一条：**1595** 条（96.7%）
- 只按 eventFlag 找得到（modifier/modifierSet 不同）：+14 条
- 完全找不到：**54** 条

### 那 54 条是什么

| 三元组 | 条数 | 判断 |
|---|---|---|
| `(7535, 0, 99999)` | 40 | 7535 在 base 里**根本没有**；`99999` 只出现在这里 → 哨兵值，特殊含义 |
| `(7720, 801, 530)` `(7700, 800, 530)` `(7727, 801, 530)` `(7705, 801, 3140)` | 10 | base 里这些 flag 的对应 set 是 505/3000/3080/3040…；530/3140 是**别的 flag** 的槽 → 跨族借用，或表本身有小矛盾 |
| `(1046400230, 140, 0)` `(1038400230, 140, 0)` | 3 | `0x3E5…`，正常 flag 只有 7xxx/8xxx → 疑似脏数据 |
| 合计 | 54 | |

## 三、结构规律（这是重点）

把某个 patternId 的行按 `modifierSet` 分组：

- **每个 patternId、每个 `modifierSet` 只出现一次**（唯一例外是 `modifierSet = 0`，出现两次，见下）
- 因此每个 pid 的行数 = 它涉及的槽位数，实测 **9 ~ 13 行**，中位数 11

`modifierSet = 0` 的两行：
1. 一行带「地图类型」flag（`7600` Cataclysm / `7601` Mountaintops / `7602` Crater / `7603` Rotted Woods / `7605` Noklateo）
2. 一行是普通 modifier（如 `180`），`eventFlag = 0`

### 举例：patternId 0 的 12 行

| eventFlag | modifier | modifierSet | 含义（查 base 名字） |
|---|---|---|---|
| 7600 | 10 | 0 | 地图类型 = Cataclysm |
| 0 | 180 | 0 | 普通难度档 |
| 0 | 705 | 190 | 难度族 190 的一档 |
| 0 | 1102 | 300 | 难度族 300（1101/1102 各 50%） |
| 0 | 1105 | 310 | 难度族 310（1105 87.5% / 1106 12.5%） |
| 0 | 0 | 350 | 难度族 350（0 = 80%，1104 = 20%） |
| 0 | 1304 | 360 | 难度族 360 |
| 8005 | 0 | 800 | 宝箱组 05 |
| 7724 | 801 | 3030 | Day 2 Event: Mass Enemy Spawn |
| 0 | 1150 | 3600 | 难度族 3600 |
| 0 | 0 | 3700 | 难度族 3700（0 = 80%，1100 = 20%） |
| 7535 | 0 | 99999 | 哨兵（见上） |

**一句话**：一个 patternId = 「地图类型 1 个 + 若干槽位各抽 1 档」。`modifierSet` 是槽位族，`modifier` 是族内选项，`weight` 是族内概率。

### weight 只在族内比较

| 族 | 选项（modifier: weight） | 概率 |
|---|---|---|
| 300 | 1101:50 / 1102:50 | 50% / 50% |
| 310 | 1105:875 / 1106:125 | 87.5% / 12.5% |
| 350 | 0:80 / 1104:20 | 80% / 20% |
| 800 | 8000–8005 各 100 | 均匀 |

## 四、base 里从没被任何种子用过的组合（8 条）

```
(0, 9002, 0)  (7707, 800, 500)  (7705, 800, 520)  (7705, 800, 530)
(7725, 801, 530)  (7725, 801, 3130)  (7705, 800, 3140)  (7725, 801, 3140)
```

→ 像是「留了位置但没用」的选项，可以作为将来换事件时的备选池。

## 五、对编辑器的结论

1. **新建种子最稳的做法**：照抄模板 pid 的那 9–13 行，只改 `patternId / patternSetId / targetBoss / rareMap` —— 天然合法，不用懂每条什么意思。
2. **想换事件**：在 base 里找**同 `modifierSet`** 的另一条，整条三元组替换，等于「重新抽一次」。不能只改 eventFlag 不改 modifier/modifierSet。
3. **校验规则**：新种子的每行三元组必须在 base 里存在；例外白名单 = `7535/99999`（哨兵）、`0x3E5…`（脏数据）。
4. `modifierSet = 0` 的双行结构要保留：一行地图类型 flag、一行普通 modifier。

## 待确认

- `7535` + `modifierSet 99999` 到底是什么（只出现在 boss 0 的 40 个 pid 里）？
- `0x3E5…` 两条大数 flag 是脏数据还是位域？
- 跨族借用的 10 条（530 / 3140）是「合法特例」还是表里的错？
