# 一个种子的完整链路调研（patternId 0）

> 基准：SOT\\regulation.bin（2,615,008 B / MD5 A435F1649373B780C4149762D49A2A00）
> 由 tools/seed_report.py 生成，只读，不改任何文件。

## 结论先看

- patternId 0 → 种子组 set 0 → Boss 0 / rareMap 0，属于基础段 0..19 区间
- 事件由 12 套变体决定（eventFlag + modifierSet），开局抽中哪套就用哪套
- 缩圈 1001 → 1011，夜晚 BOSS 4929 / 4860（+ bossModifier 444 / 402）
- 95 个地点全部对得上 attach / define / variation
- 全库体检 30 条：2 个 error（set 1096 声明 5 个 pid 实际 1 个）+ 28 个 warn（2xxx tile 缺变体/定义）

## 全量报告

\==============================================================================
种子 patternId = 0
==============================================================================
归属种子组 set 0   Boss 0   rareMap 0   区间 (0, 19)   weight=0 chaos=600
Boss 名 id=131060  图标 id=41800（NightBossMenuParam）

事件变体（12 套，由开局抽中的那套决定 eventFlag）
   row=    0  eventFlag=  7600  modifierSet=     0  modifier=    10
   row=    1  eventFlag=     0  modifierSet=     0  modifier=   180
   row=    2  eventFlag=     0  modifierSet=   190  modifier=   705
   row=    3  eventFlag=     0  modifierSet=   300  modifier=  1102
   row=    4  eventFlag=     0  modifierSet=   310  modifier=  1105
   row=    5  eventFlag=     0  modifierSet=   350  modifier=     0
   row=    6  eventFlag=     0  modifierSet=   360  modifier=  1304
   row=    7  eventFlag=  8005  modifierSet=   800  modifier=     0
   row=    8  eventFlag=  7724  modifierSet=  3030  modifier=   801
   row=    9  eventFlag=     0  modifierSet=  3600  modifier=  1150
   row=   10  eventFlag=     0  modifierSet=  3700  modifier=     0
   row=   11  eventFlag=  7535  modifierSet= 99999  modifier=     0

缩圈 / 夜晚 BOSS（LotResultPlayAreaParam）
   playArea1=1001  playArea2=1011
   bossId1=4929  bossId2=4860  extra=-1/-1
   bossModifier1=444  bossModifier2=402

地点（LotResultSmallBaseAndSpot）：95 个
   tile  3030  ×2   图标iconId=42006  ['Encounter Setup: Ruins', 'Encounter Setup: Fort', '', '']
       attach  110  grid=(44, 38)  pos=(2,85,-13)  mapIndex=0 variation=1  Tile: Castle (Cataclysm)
       attach  103  grid=(42, 39)  pos=(-30,192,-45)  mapIndex=1 variation=0  Tile: Castle (Cataclysm)
   tile  3210  ×2   图标iconId=42009  ['Encounter Setup: Ruins', '']
       attach  112  grid=(44, 39)  pos=(73,110,-64)  mapIndex=0 variation=2  Tile: Large Encampment with Siege Tower
       attach  116  grid=(45, 38)  pos=(44,12,97)  mapIndex=1 variation=1  Tile: Large Encampment with Siege Tower
   tile  3220  ×1   图标iconId=42009  ['Encounter Setup: Ruins', '']
       attach  120  grid=(42, 38)  pos=(53,143,-44)  mapIndex=0 variation=1  Tile: Large Encampment (Cataclysm)
   tile  3410  ×7   图标iconId=42002  ['Encounter Setup: Ruins', '']
       attach  101  grid=(42, 37)  pos=(45,98,-107)  mapIndex=0 variation=1  Tile: Major Ruins B (Cataclysm)
       attach  106  grid=(43, 39)  pos=(0,176,-77)  mapIndex=1 variation=3  Tile: Major Ruins B (Cataclysm)
       attach  104  grid=(43, 36)  pos=(-29,65,-49)  mapIndex=2 variation=1  Tile: Major Ruins B (Cataclysm)
       attach  109  grid=(44, 37)  pos=(75,30,-9)  mapIndex=3 variation=1  Tile: Major Ruins B (Cataclysm)
       attach  113  grid=(45, 36)  pos=(-5,16,20)  mapIndex=4 variation=3  Tile: Major Ruins B (Cataclysm)
       attach  100  grid=(42, 37)  pos=(108,89,50)  mapIndex=5 variation=3  Tile: Major Ruins B (Cataclysm)
       attach  114  grid=(45, 37)  pos=(4,22,-68)  mapIndex=6 variation=1  Tile: Major Ruins B (Cataclysm)
   tile  3430  ×1   图标iconId=42002  ['Encounter Setup: Ruins', '']
       attach  111  grid=(44, 38)  pos=(126,32,-70)  mapIndex=0 variation=0  Tile: Major Ruins D (Cataclysm)
   tile  3810  ×3   图标iconId=42023  ['Encounter Setup: Great Church', 'Encounter Setup: Great Church', '', '']
       attach  126  grid=(44, 36)  pos=(45,87,98)  mapIndex=0 variation=0  Tile: Cathedral B (Cataclysm)
       attach  107  grid=(43, 39)  pos=(-24,198,111)  mapIndex=1 variation=1  Tile: Cathedral B (Cataclysm)
       attach  117  grid=(45, 39)  pos=(-56,95,54)  mapIndex=2 variation=1  Tile: Cathedral B (Cataclysm)
   tile  4000  ×2   图标iconId=42005  ["Encounter Setup: Sorcerer's Rise", '']
       attach  305  grid=(43, 36)  pos=(57,64,85)  mapIndex=0 variation=8  Tile: Sorcerer's Rise A
       attach  310  grid=(44, 39)  pos=(-72,153,44)  mapIndex=1 variation=6  Tile: Sorcerer's Rise A
   tile  4100  ×3   图标iconId=42001  ['Encounter Setup: Church', '']
       attach  302  grid=(42, 38)  pos=(-48,192,98)  mapIndex=0 variation=0  Tile: Church A
       attach  313  grid=(45, 38)  pos=(39,35,-9)  mapIndex=1 variation=0  Tile: Church A
       attach  300  grid=(42, 36)  pos=(-74,92,62)  mapIndex=2 variation=0  Tile: Church A
   tile  4300  ×2   图标iconId=42009  ['Encounter Setup: Small Camp', '']
       attach  301  grid=(42, 37)  pos=(-66,159,44)  mapIndex=0 variation=0  Tile: Encampment A
       attach  307  grid=(44, 36)  pos=(45,87,98)  mapIndex=1 variation=0  Tile: Encampment A
   tile  4340  ×1   图标iconId=42009  ['Encounter Setup: Small Camp', '']
       attach  314  grid=(45, 38)  pos=(-86,58,81)  mapIndex=0 variation=0  Tile: Encampment D
   tile  4341  ×1   图标iconId=42009  ['Encounter Setup: Small Camp', '']
       attach  358  grid=(44, 37)  pos=(-52,87,-76)  mapIndex=0 variation=0  Tile: Encampment E
   tile  4500  ×2   图标iconId=42009  ['Encounter Setup: Small Camp Caravans', '']
       attach  312  grid=(45, 37)  pos=(86,24,4)  mapIndex=0 variation=0  Tile: Caravans A
       attach  306  grid=(43, 38)  pos=(-86,188,32)  mapIndex=1 variation=0  Tile: Caravans A
   tile  4600  ×7   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  655  grid=(45, 37)  pos=(-54,13,47)  mapIndex=0 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  645  grid=(44, 38)  pos=(-101,65,-15)  mapIndex=1 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  653  grid=(45, 36)  pos=(-107,29,40)  mapIndex=2 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  619  grid=(42, 37)  pos=(21,106,47)  mapIndex=3 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  647  grid=(44, 38)  pos=(13,121,107)  mapIndex=4 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  618  grid=(42, 37)  pos=(-107,168,108)  mapIndex=5 variation=0  Encounter: Trolls, Knights and Soldiers
       attach  634  grid=(43, 38)  pos=(55,97,-95)  mapIndex=6 variation=0  Encounter: Trolls, Knights and Soldiers
   tile  4601  ×7   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  633  grid=(43, 38)  pos=(101,99,13)  mapIndex=0 variation=0  Encounter: Large Dogs and Crows
       attach  651  grid=(45, 36)  pos=(90,32,113)  mapIndex=1 variation=0  Encounter: Large Dogs and Crows
       attach  662  grid=(45, 39)  pos=(-105,118,108)  mapIndex=2 variation=0  Encounter: Large Dogs and Crows
       attach  622  grid=(42, 38)  pos=(-103,194,49)  mapIndex=3 variation=0  Encounter: Large Dogs and Crows
       attach  648  grid=(44, 39)  pos=(-85,141,-98)  mapIndex=4 variation=0  Encounter: Large Dogs and Crows
       attach  638  grid=(43, 39)  pos=(87,101,3)  mapIndex=5 variation=0  Encounter: Large Dogs and Crows
       attach  623  grid=(42, 38)  pos=(34,156,37)  mapIndex=6 variation=0  Encounter: Large Dogs and Crows
   tile  4602  ×5   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  658  grid=(45, 38)  pos=(113,14,49)  mapIndex=0 variation=0  Encounter: Ants
       attach  641  grid=(44, 36)  pos=(-101,65,-51)  mapIndex=1 variation=0  Encounter: Ants
       attach  661  grid=(45, 39)  pos=(1,90,-42)  mapIndex=2 variation=0  Encounter: Ants
       attach  640  grid=(44, 36)  pos=(-58,86,88)  mapIndex=3 variation=0  Encounter: Ants
       attach  649  grid=(44, 39)  pos=(-71,150,4)  mapIndex=4 variation=0  Encounter: Ants
   tile  4603  ×7   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  637  grid=(43, 39)  pos=(-72,202,-51)  mapIndex=0 variation=0  Encounter: Fingercreepers
       attach  659  grid=(45, 38)  pos=(-7,22,-101)  mapIndex=1 variation=0  Encounter: Fingercreepers
       attach  644  grid=(44, 37)  pos=(87,33,104)  mapIndex=2 variation=0  Encounter: Fingercreepers
       attach  617  grid=(42, 36)  pos=(72,77,-115)  mapIndex=3 variation=0  Encounter: Fingercreepers
       attach  654  grid=(45, 37)  pos=(-82,21,-50)  mapIndex=4 variation=0  Encounter: Fingercreepers
       attach  627  grid=(43, 36)  pos=(1,65,73)  mapIndex=5 variation=0  Encounter: Fingercreepers
       attach  632  grid=(43, 37)  pos=(-88,100,105)  mapIndex=6 variation=0  Encounter: Fingercreepers
   tile  4604  ×7   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  660  grid=(45, 39)  pos=(-89,106,-22)  mapIndex=0 variation=0  Encounter: Dragons
       attach  616  grid=(42, 36)  pos=(-44,78,-18)  mapIndex=1 variation=0  Encounter: Dragons
       attach  621  grid=(42, 38)  pos=(-64,179,-45)  mapIndex=2 variation=0  Encounter: Dragons
       attach  650  grid=(44, 39)  pos=(31,141,82)  mapIndex=3 variation=0  Encounter: Dragons
       attach  642  grid=(44, 37)  pos=(-83,81,-14)  mapIndex=4 variation=0  Encounter: Dragons
       attach  624  grid=(42, 39)  pos=(-50,206,78)  mapIndex=5 variation=0  Encounter: Dragons
       attach  636  grid=(43, 39)  pos=(-111,220,110)  mapIndex=6 variation=0  Encounter: Dragons
   tile  4605  ×7   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  620  grid=(42, 37)  pos=(-22,108,-38)  mapIndex=0 variation=0  Encounter: Guardian Golems
       attach  643  grid=(44, 37)  pos=(12,55,39)  mapIndex=1 variation=0  Encounter: Guardian Golems
       attach  646  grid=(44, 38)  pos=(-59,82,-109)  mapIndex=2 variation=0  Encounter: Guardian Golems
       attach  657  grid=(45, 38)  pos=(-46,60,99)  mapIndex=3 variation=0  Encounter: Guardian Golems
       attach  629  grid=(43, 36)  pos=(59,66,-110)  mapIndex=4 variation=0  Encounter: Guardian Golems
       attach  626  grid=(42, 39)  pos=(120,189,-84)  mapIndex=5 variation=0  Encounter: Guardian Golems
       attach  615  grid=(42, 36)  pos=(111,65,-14)  mapIndex=6 variation=0  Encounter: Guardian Golems
   tile  4606  ×8   图标iconId=None  ['Encounter Setup: Night Horde', '']
       attach  628  grid=(43, 36)  pos=(113,65,58)  mapIndex=0 variation=0  Encounter: Royal Riders
       attach  652  grid=(45, 36)  pos=(-2,1,-68)  mapIndex=1 variation=0  Encounter: Royal Riders
       attach  630  grid=(43, 37)  pos=(119,89,-94)  mapIndex=2 variation=0  Encounter: Royal Riders
       attach  639  grid=(44, 36)  pos=(15,98,4)  mapIndex=3 variation=0  Encounter: Royal Riders
       attach  656  grid=(45, 37)  pos=(42,20,17)  mapIndex=4 variation=0  Encounter: Royal Riders
       attach  631  grid=(43, 37)  pos=(-42,85,-7)  mapIndex=5 variation=0  Encounter: Royal Riders
       attach  625  grid=(42, 39)  pos=(57,207,16)  mapIndex=6 variation=0  Encounter: Royal Riders
       attach  635  grid=(43, 38)  pos=(-82,190,89)  mapIndex=7 variation=0  Encounter: Royal Riders
   tile  4650  ×2   图标iconId=42004  ['Encounter Setup: Evergaol', '']
       attach  604  grid=(43, 39)  pos=(100,101,82)  mapIndex=0 variation=3  Tile: Evergaol A
       attach  601  grid=(42, 39)  pos=(-125,222,-103)  mapIndex=1 variation=4  Tile: Evergaol A
   tile  4651  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  753  grid=(42, 38)  pos=(94,184,66)  mapIndex=0 variation=0  Encounter: Red Wolf of Radagon
   tile  4654  ×1   图标iconId=42027  ['Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', '', '', '', '', '']
       attach  758  grid=(43, 39)  pos=(-125,220,19)  mapIndex=0 variation=0  Encounter: Draconic Sentinel
   tile  4655  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  750  grid=(42, 36)  pos=(93,75,-111)  mapIndex=0 variation=0  Encounter: Leonine Misbegotten
   tile  4656  ×1   图标iconId=42027  ['Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', '', '', '', '', '']
       attach  755  grid=(43, 36)  pos=(57,64,85)  mapIndex=0 variation=0  Encounter: Royal Revenant
   tile  4657  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  759  grid=(43, 39)  pos=(85,106,-167)  mapIndex=0 variation=0  Encounter: Lion Guardian
   tile  4659  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  760  grid=(44, 38)  pos=(-50,95,56)  mapIndex=0 variation=0  Encounter: Dragon
   tile  4660  ×3   图标iconId=42004  ['Encounter Setup: Evergaol', '']
       attach  602  grid=(43, 37)  pos=(-107,64,-74)  mapIndex=0 variation=5  Tile: Evergaol B
       attach  605  grid=(44, 36)  pos=(57,90,-27)  mapIndex=1 variation=4  Tile: Evergaol B
       attach  603  grid=(43, 38)  pos=(44,137,53)  mapIndex=2 variation=6  Tile: Evergaol B
   tile  4662  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  754  grid=(42, 39)  pos=(17,207,59)  mapIndex=0 variation=0  Encounter: Wormface and Night's Cavalry
   tile  4663  ×1   图标iconId=42027  ['Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', '', '', '', '', '']
       attach  763  grid=(45, 37)  pos=(22,19,118)  mapIndex=0 variation=0  Encounter: Ulcerated Tree Spirit
   tile  4664  ×1   图标iconId=42027  ['Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', '', '', '', '', '']
       attach  756  grid=(43, 37)  pos=(38,125,63)  mapIndex=0 variation=0  Encounter: Ancestor Spirit
   tile  4670  ×2   图标iconId=42004  ['Encounter Setup: Evergaol', '']
       attach  606  grid=(44, 38)  pos=(73,85,82)  mapIndex=0 variation=3  Tile: Evergaol C
       attach  607  grid=(45, 38)  pos=(62,18,-110)  mapIndex=1 variation=1  Tile: Evergaol C
   tile  4672  ×1   图标iconId=42015  ['Encounter Setup: Field Boss', '', '']
       attach  762  grid=(45, 36)  pos=(-103,35,-46)  mapIndex=0 variation=0  Encounter: Golden Hippopotamus
   tile  4674  ×1   图标iconId=42027  ['Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', 'Encounter Setup: Field Boss', '', '', '', '', '']
       attach  761  grid=(44, 39)  pos=(79,125,51)  mapIndex=0 variation=0  Encounter: Death Rite Bird
   tile  4691  ×1   图标iconId=42015  ['Encounter Setup: Basement', '']
       attach  757  grid=(43, 37)  pos=(38,125,63)  mapIndex=0 variation=0  Encounter: Grafted Scion
   tile  4942  ×1   图标iconId=42010  ['Encounter Setup: Castle', '']
       attach  190  grid=(43, 37)  pos=(90,79,63)  mapIndex=0 variation=0  Encounter: Castle Layout B

本种子链路完整：pattern → playArea → spots → attach/define 全部对得上。
\\n