# 更新日志

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号用 [语义化](https://semver.org/lang/zh-CN/)。

## [3.1.0] - 2026-11-16

### 新增

- **大空洞（Great Hollow）**：补齐上下两层底图（`great_hollow.png` / `great_hollow_b1.png`），
  种子点位按层显示，顶栏可切换「上层 L0 / 下层 B1」；
  缩圈候选接上 `[Great Hollow]` 的 11000/11001/11002 + 12000/12001
- **点位校准器**（`calib\启动点位校准.bat`，8780）：单击切层、拖动挪位、右键删点、Ctrl+Z 撤销，
  悬停显示该点被哪些建筑用到；产物 `src/data/great_hollow_layers.json`
- **成组点联动**：上城属性 / 上城地下 / 下城属性 / 下城地下 4 组（实测 80/80 整组出现、tile 固定配套）
  在编辑器里各只显示代表点，改一个会按配套表补齐同组
- **腐败森林（Rotted Woods）**：校准出 52 个建筑位（47 基准 − 10 删除 + 15 个专属点
  `Rotted Woods - *` / `Event - Gnoster/Morgott/Libra`）
- **夜晚 BOSS 下拉**：`bossId` 从数字框改成「下拉 + 手输」，已收录的 35 个自动带出 `bossModifier`
- **名称表**（顶栏）：建筑 tile 的英文/中文名 + **属性变体自定义名**；夜晚 BOSS 名。
  改完立即生效，存 `src/data/tile_names.json` / `night_boss_names.json`
- **随机种子**：
  - 「＋ 添加随机种子」支持**数量**（1~50 批量），每张重新随机挑模板
  - **随机表**（双表）：表1 = 点位勾选（已校准/未校准）+ 建筑权重（默认 10，`0`=不参与）+ 变体权重（每建筑独立一套）；
    表2 = 夜晚 BOSS / 缩圈勾选
  - 随机流程：同地图类型的模板 → 模板点位里**勾选的**才随机（建筑/变体按权重），没勾的保持原样，
    模板没有的点位不出现
  - 夜晚 BOSS **分晚随机**（第一晚 18 个 / 第二晚 17 个，交集为空）；缩圈只在该地图自己的候选里选
  - **开发者日志**：`work\random_log.jsonl` 实时记录 + 随机表右下角「导出随机日志」生成带时间戳的 JSON

### 修复

- **监牢随机去重**：同一种子里两个监牢刷到同一个「建筑 + 变体」= 同一个怪，游戏里第二个监牢打不开。
  现在对监牢点位（候选 `4650/4660/4670/4680`）枚举 `(建筑, 变体)` 组合、排掉本种子已用过的，
  按 `建筑权重 × 变体权重` 抽；组合用完则该点位保持模板。随机表 → 表2 底部新增开关「监牢不刷同一个怪」，默认开。
  顺带修变体权重未配置时默认 `0` 导致监牢全抽成变体 0 的 bug（改用该 tile 真实变体槽、权重 10）。
- 保存时 `flag` / `area` / `spot` 三张表的**行 id 被整体重编号**（`renumber=True` 从 1 重发号，
  官方 `LotResultPlayAreaParam` 是 0~522）→ 改成 `renumber=False`，官方行 id 一个不动，新行取 `max+1`
- 改组合不更新名字 → 名字里的 `[夜王]` 前缀同步替换（已错配的也能修回来）
- 空 set 身份丢失：新建 set 后插种子会被源种子的夜王/地图类型冲掉 → 记进 `work\custom_sets.json`
- 锻造村 / 毒池随机不到：它们挂在 **21xx 孪生号**上（101 ↔ 2101 坐标完全相同）→ `official_tiles` 合并 ±2000
- 随机越界建筑（野外 BOSS 点长出建筑）→ 建筑候选限定为该点位自己的（含孪生），全局权重只负责概率
- limveld 随机表点位为空（它既没有 `calibrated` 也没有 `attachPool`）→ 三级回退到自动算的锚点
- 随机表从没配置过时「什么都不随机」→ 默认三类全开
- 756/757（主城楼顶/楼底 BOSS 位）被随机建筑污染 → 排除
- 白圈显示的点曾被写回 `layers.surface`，导致删过的点（1175/1176 等）进随机池 → 已清

### 修复

- `src/vendor/paramtool.py` 找 NR paramdef 时只认本机 Smithbox 目录，**不认随包的 `vendor/NRDefs`** ——
  换台机器 / 别人 clone 下来会直接报「找不到 NR paramdef 目录」。现在优先用 `vendor/NRDefs`，
  其次 `NR_DEFS` / `SMITHBOX_DIR` 环境变量，最后才扫本机 Smithbox。
- 点位校准器：重新加载后保存会把「已挪过的点」的 `moved` 丢掉（基线算错）
- 点位校准器：面板不是正方形时纵向拖动位移换算错误
- 大空洞堡垒（上下城）没有图标；修的时候夜王塔图标被误伤
- 游戏原始 bin（`moremap`）的 `PlayAreaCreateParam` 行名为空 → 所有地形缩圈候选变 0
- `maps.json` 只在启动时读一次 → 校准保存后要重启编辑器才生效
- **加种子会把新建 Set 的夜王/地图类型冲掉**：`plan_insert_pattern` 的组合优先级是
  `传入 > set 的 combo > 源 pid 的 combo`，而**空 set 没有 flag 行、`combo` 是 None**
  → 直接退到源 pid 的组合，把刚建好的 set 身份改成源种子的。
  现在创建 set 时把身份记进 `work\custom_sets.json`（按 bin 路径区分），插入时优先用它；
  改组合会更新、删 set 会清理。
- **改组合不改名字**：留下「名字是 Harmonia、组合是 Straghess」的错配 set。
  现在改组合会按名字里的 `[夜王]` 前缀同步替换（已经错配过的也能修回来）。
- `PatternModel` 只从 bin 的 `NightBossMenuParam` 读夜王名（原始 bin 里是空的）→ 补了
  `boss_names.json` 兜底
- **保存时三张结果表的行 id 被整体重编号**：`flag` / `area` / `spot` 原来是
  `renumber=True`，flush 时按 pid 排序后**从 1 重新发号**，官方 id 全被顶掉
  （`LotResultPlayAreaParam` 官方是从 **0** 起、`0~522`，保存后变成 `1~523`）。
  现在改成 `renumber=False`：官方行 id 一个不动，新行取 `max+1` 从末尾加，
  并加了一道 u32 上限检查（真到顶就报错）

### 计划中

- 主城楼顶 / 楼底（attach 756 / 757）的完整规则
- 事件 / flag 行的逐行编辑（`modifierSet` 语义还没研究透）
- 导出 JSON 的「导入复现」入口

> 「无血条占位 BOSS」不做黑名单 —— 改成白名单：夜晚 BOSS 只列官方真实出现过的 35 个组合。

## [3.0.0] - 2026-11-15

首个公开版本。

### 新增

- **三栏界面**：左侧 set 树（夜王筛选 / 新建 set / 撤销），中间地形图，右侧 set 参数与种子详情
- **地点编辑**：点空建筑位加地点、点地点选中定位、双击换建筑、删地点、拖动排序；
  同一 `smallBaseMapId` 出现多次时自动累加 `mapIndex`（否则游戏里那处没 BGM）
- **属性变体**：`variationId` 直接在表里改，右下角属性小图标跟着变
- **缩圈与夜晚 BOSS**：1缩 / 2缩 悬停在地图上预演位置，点一下生效；bossId / bossModifier 四块可改
- **五张地形底图**：宁姆韦德 / 山顶 / 火山口 / 腐败森林 / 隐城，切换时底图与建筑位池子一起换
- **撤销一步**：加点、删点、排序、换缩圈、换事件都算一步，最多回退 60 步
- **新建 set / 插入种子**：按夜王 + 地图类型建空 set（池子可照抄官方），插入时克隆源 pid
- **安全写回**：改动只落在副本；保存 = 封包 → 再解包 → 逐表字节对账 → 备份 `.prev_<时间戳>` → 覆盖

### 修复

- `patternSetId = 0` 时点建筑位加不了地点（`selPid` 被当成假值）
- 底部建筑选择条选完关不掉（`[hidden]` 被 `display:flex` 覆盖）
- set 列表太长时把左侧「撤销一步」挤出屏幕（改为侧栏内部滚动）

### 仓库 / 文档

- 补 `docs/项目总结.md`、`docs/待修清单.md` 等调研记录
- 移除专有二进制（Oodle `oo2core`）与游戏解包素材，`assets/` 只保留目录结构
- 加入 CI（语法 / 数据表 / 服务冒烟）与 Issue、PR 模板

[未发布]: https://github.com/RedDd771212/nr-seed-editor/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/RedDd771212/nr-seed-editor/releases/tag/v3.0.0
