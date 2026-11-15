# 更新日志

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号用 [语义化](https://semver.org/lang/zh-CN/)。

## [未发布]

### 计划中

- 主城楼顶 / 楼底（attach 756 / 757）的完整规则
- 「无血条占位 BOSS」黑名单
- 腐败森林（Rotted Woods）的建筑位池子
- 事件 / flag 行的逐行编辑（`modifierSet` 语义还没研究透）
- 导出 JSON 的「导入复现」入口

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
