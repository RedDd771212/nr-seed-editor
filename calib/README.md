# attach 点校准工具（手动校准 + 自动核对）

和编辑器**分开**的第二个小工具：把 bin 里所有 attach 点摊在 Limveld 手绘图上，
手动拖动 / 删掉 / 标位置，保存成 `calib/corrections.json`；
再用 `tools/check_calib.py` 逐条核对，**不直接采信**。

## 启动

双击 `calib\启动校准.bat`（或 `python calib\server.py 8778 <regulation.bin>`），
浏览器打开 <http://127.0.0.1:8778/>。

默认读 `work\last_bin.json` 里最近打开的 bin；也可以在命令行第二个参数指定。

## 怎么用

| 操作 | 效果 |
|---|---|
| 拖 | 改这个点的世界坐标（等价于改 posX / posZ） |
| 点一下 | 选中，右栏出完整信息 + 可手输 posX / posZ |
| Delete 键 / 右键 | 标记删除（不会真删，只是记下来） |
| 再按 Delete / 「恢复这个点」 | 撤销 |
| 「重置本次改动」 | 清空这次所有改动 |
| 「保存校对」 | 写到 `calib/corrections.json`，同时留一份 `calib/history/` |

- 顶栏「含特殊地形」默认**关**：只看 `pad=0` 且 `attachId < 1000` 的 205 个普通点。
- 颜色：蓝=大据点、绿=小据点、灰=地下（id≥1000）、橙=特殊地形（pad≠0）。

## 自动核对

```
python tools/check_calib.py calib/corrections.json <regulation.bin>
```

会逐条判 OK / 注意 / 危险：

1. id 是否存在、名字对不对
2. 移动距离（>80 提示、>200 报警）
3. 是否跑出自己那一格（pos 应在 ±128 内）
4. 是否和别的点撞在一起（<16 单位；原本就同位置的孪生点不算）
5. 删掉的点是否被官方种子用过（用过 → 危险）
6. 特殊地形点（pad≠0）删掉是安全的

**危险项一条都不会自动采用**，会先报出来。
