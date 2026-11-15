import sys
sys.path.insert(0, r'D:\项目\app\NR地图种子编辑器\src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir(r'D:\项目\app\NR地图种子编辑器\work\reg\params'))
print(f"{'id':>3}  {'name':<28} iconId")
for k in sorted(m.wm_icons):
    v = m.wm_icons[k]
    print(f"{k:>3}  {str(v.get('_name')):<28} {v.get('iconId')}")
