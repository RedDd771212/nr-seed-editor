# NR 地图种子编辑器 v3

黑夜君临（Nightreign）的 **地图种子编辑器**：直接读写 `regulation.bin` 里的地图种子 param，
可以新建 / 修改 `MapPatternSet`，在 set 里增删种子，改地点、缩圈、夜晚 BOSS。

> 只动 param（`MapPatternSet` / `LotResultMapPatternFlag` / `LotResultPlayAreaParam` / `LotResultSmallBaseAndSpot`），
> 不碰 msb / emevd / onav。

介绍视频和完整发布包只在本地，不随仓库公开；素材（地图底图 / 图标）说明见[第八节](#八仓库说明github-版)。

---

## 一、运行要求

| 需要 | 说明 |
|---|---|
| Windows 10/11 | — |
| **.NET 运行时 6 或 8** | 解包/封包 `regulation.bin` 用的 regtool 需要它（一般装过游戏/开发环境的机器都有） |
| **Python 3.10+** | 安装时勾选 “Add Python to PATH” |
| **Pillow** | 生成地图预览用：`python -m pip install pillow` |

不确认的话，先双击 **`检查环境.bat`**，它会逐项告诉你缺什么。

---

## 二、开箱使用

1. 双击 **`检查环境.bat`** —— 全 OK 再往下
2. 双击 **`启动.bat`** —— 浏览器会自动打开 http://127.0.0.1:8779/
3. 顶栏填 `regulation.bin` 的路径（也可以直接填它所在的文件夹）→ 点「打开」
4. 改完点右上角「保存」——**只有点保存才会写 bin**

关掉服务：双击 **`停止.bat`**（只结束 8779 端口上的进程）。

---

## 三、界面（三栏）

```
┌──────────────────────────────────────────────────────────────┐
│ [bin 路径] 打开   保存●    ┃ 当前：夜王 · 地形 · set · pid     │
├──────────────┬────────────────────────────┬──────────────────┤
│ Set 面板      │           地  图            │      详情         │
│ 夜王筛选      │  跟着选中 set 换地形底图    │  set 参数 /       │
│ ＋新建 set    │  点建筑位 → 加地点          │  种子内容 /       │
│ set 树        │  点地点 → 高亮              │  事件行（只读）    │
│   └ pid 列表  │  1缩/2缩 位置标记           │                  │
│ 撤销一步      │                            │                  │
└──────────────┴────────────────────────────┴──────────────────┘
```

**圆圈规则**
- **小圈** = 校准过的建筑位（蓝=大据点 / 绿=小据点 / 灰=未知）
- **大圈** = 这个种子的地点，颜色跟着它所在的建筑位；贴不到建筑位的用白色
- 同一个位置有地点时只显示一个圈；点击按**圆心最近**判定，选中的圈会更亮

**常用操作**

| 想做什么 | 怎么做 |
|---|---|
| 新建一个种子组 | 左下「＋新建 set」→ 选夜王 + 地图类型（其余字段照抄官方，可勾「池子照抄官方」） |
| 在 set 里加种子 | 选中 set → 右边「插入一个种子」（克隆你指定的源 pid） |
| 删种子 / 删 set | 选中后点「删除这个种子」/「删整个 set」 |
| 换建筑 | 地点表里点蓝色 `tile` 编号，或双击地图上的大圈 → 底部选建筑（也能直接输 tile 号） |
| 改属性变体 | 地点表 `变体` 那格直接改数字，回车生效 |
| 换缩圈 | 右栏 1缩/2缩 下拉，**悬停看位置**、点一下生效 |
| 换夜晚 BOSS | 填 bossId / bossModifier 四个数，点「保存夜王」 |
| 改权重 | set 面板里 `weight` / `chaosMatchWeight` → 「保存这两个值」 |
| 改错了一步 | 左下「↶ 撤销一步」（结构操作会写快照，可回退） |

---

## 四、安全设计

- 打开 bin 后，所有改动都发生在 **副本** 上（`work\edit\<bin>_<时间>\`），
  **不点保存不会动你的 bin**；
- 保存流程：封包 → 再解包 → **逐表字节对账** → 把原 bin 备份成
  `regulation.bin.prev_<时间戳>` → 才覆盖；
- 每一步操作都会存快照（最多 8 份），状态栏「撤销一步」可回退；
- 想彻底恢复：把游戏目录里的 `regulation.bin.prev_<时间戳>` 改名回 `regulation.bin` 即可。

> ⚠️ 改的是**游戏目录里的 bin**，请先自己另外备份一份 `regulation.bin` 再玩大的。
> 联机/官方环境里不要用改过的 bin。

---

## 五、原理与限制（重要）

- **种子编号（patternId）是算出来的**：
  `patternId = ⌊setId / 1000⌋ × 1000 + 组内前缀和`（组内按 set id 升序累加 `patternCount`）。
  所以往一个 set 里加/删种子，**同组**里它后面的种子编号会整体平移；不同千位组互不影响。
- **`patternCount` 不用手填**：等于这个 set 里实际有几个种子。
- **新建 set 放表尾**（id = 当前最大 +1），落 1000 组，pid 接着往后排。
- **set 级「池子」字段**（`eventModifier*_Count`、`night1/2BossModifier*_Count`）按「个数」自动维护。
- **事件 / flag 行**目前只读展示（后续版本会开放逐行编辑）。
- DLC 地形的种子用的是 `21xx` 这一族 attachId，界面上按孪生号（`−2000` 等）自动对应到校准过的建筑位。

**已知限制**
- 主城楼顶 / 楼底（attach 756 / 757）的完整规则还没定；
- 「无血条占位 BOSS」还没做黑名单；
- 腐败森林（Rotted Woods）的建筑位池子尚未校准，先用默认池；
- 手绘底图是示意图，个别点位有 1~2 像素偏差（已用监牢圆心标定）。

---

## 六、目录

```
启动.bat / 停止.bat / 检查环境.bat
app\
  server_v3.py      当前界面用的后端（127.0.0.1:8779）
  web3\             三栏界面（html/js/css）
  core\
    project.py      打开 bin、解包、模型
    patternset.py   set/pattern 模型 + dry-run 规划 + 校验
    pswriter.py     字段级写入、增删行、封包对账、会话快照
    render.py       地图预览（PIL）
    paths.py        随包依赖路径解析
src\
  nrseed\           param 读取（paramdir / model）
  vendor\           paramtool.py / paramdump.py（读写 .param 字节）
  data\             分类表、地图档案、图标映射
vendor\
  regtool\          解包/封包 regulation.bin
  NRDefs\           NR 的 235 个 paramdef（Smithbox 资产）
assets\
  map\              5 张地形底图
  icon\pin\         地图图标
docs\               调研记录与重构方案
calib\              点位校准工具（可选，开发用）
tools\              开发脚本（可选）
work\               运行时中间产物（可随时清空）
```

---

## 七、致谢 / 依赖来源

- **regtool**：DeepSeek Harness 技能 `fs-bin-modding` 自带的 regtool.dll（解包/封包）
- **paramtool.py / paramdump.py**：同技能的 .param 字节读写脚本
- **NR paramdef**：Smithbox 的 `Assets\PARAM\NR\Defs`
- 地图底图：从游戏图块拼接；图标从游戏 UI 图集切出

> 上面这些第三方组件各自遵循其原始许可，本仓库只是把运行需要的东西放在一起。

---

## 八、仓库说明（GitHub 版）

本仓库是**代码仓库**，下面这些**故意没有提交**（体积大 / 有版权 / 是运行时产物）：

| 没进仓库 | 说明 | 怎么补 |
|---|---|---|
| `assets/map/*.png` | 5 张地形底图，共 21 MB，由游戏里的 256×256 图块拼成 | 跑 `tools/stitch_tiles.py` |
| `assets/icon/` | 430 张地图图标 / pin，共 21 MB，从游戏 UI 图集里切出 | 跑 `tools/cut_pin_all.py`、`tools/cut_menuicon42.py` |
| `work/` | 解包中间产物、快照、截图（本机 1.7 GB） | 不用管，第一次打开 bin 自动生成，可随时清空 |
| `tools/*/oo2core_9_win64.dll` | Oodle 解压库（Radiant 专有二进制），`tools/fsx`、`tools/menuextract` 要用 | 从游戏目录或本机工具里复制一份放回去 |
| `dist/*.zip`、介绍视频 | 发布包 / 宣传片，只在本机保留 | — |

缺素材时界面能开，但**地图是空的**（`检查环境.bat` 会提示 `assets\map\` 缺失）。
素材涉及游戏美术资源，不便随代码公开分发；自己解包生成，或在 Issues 里问一声。

> `assets/` 下面的目录结构已经用 `.gitkeep` 保留了（`map/`、`icon/pin/`、`icon/attr/`、`icon/map/`、`icon/misc/`），
> 把生成的 png 丢进对应目录即可，不用自己建文件夹。

---

## 九、许可

代码部分 **MIT**，见 [LICENSE](LICENSE)。第三方组件（regtool / paramtool / NRDefs 等）遵循各自原始许可。

---

## 十、开发说明

这个项目是**人机协作**做出来的：在 **DeepSeek Harness** 里，由一个 AI 助手（代号「蓝鲸」）承担了绝大部分编码、调试、写文档和剪介绍视频的活；
需求提出、方向拍板、游戏内实测和「哪些数据能采信」的把关由作者负责。

所以看代码时可能会注意到：注释里常带调查编号（`m05xxx`）、文档写得比较细、提交信息偏长 —— 这些都是 AI 协作留下的痕迹。
如果发现哪里写得不好、或者逻辑有坑，欢迎直接提 Issue / PR。

---

版本：v3.0（2026-11-15）
