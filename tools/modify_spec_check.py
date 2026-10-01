import sys, re, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
out = Path("work/captures/pages/수정팝업")
h = (out / "popupModify_982.html").read_text(encoding="utf-8")
a = h.index("selectModifyInputOnlineDepstRecetData.do"); load = h[a:h.index("function fnCommonCodeCall", a)]
gp = h[h.index("function getParam()"):]; gp = gp[:gp.index("return param;")]
res = dict(re.findall(r"(result\w+)\s*=\s*resultData\.(\w+)\s*;", load))
res.update({"licAlwStartDay": "lic_alw_start_day", "licRemark": "lic_remark"})
form = {}
for fid, v in re.findall(r"""\$\(["']#(\w+)["']\)\s*\.val\(\s*([\w']*)\s*\)""", load):
    if v: form.setdefault(fid, v)
let = {}
for v, fid, opt, fn in re.findall(r"""var (let\w+)\s*=\s*(?:frm\.find|\$)\(["']#(\w+)( option:selected)?["']\)\.(val|text)\(\)""", gp):
    let[v] = (fid, fn)
obj = gp[gp.index("var param = {"):]
table, special = {}, []
for key, expr in re.findall(r"^\s*,?\s*(\w+)\s*:\s*([^\n]+?),?\s*(?://.*)?$", obj, re.M):
    m = re.match(r"(let\w+)\s*==\s*\"\"\s*\?\s*null\s*:\s*(let\w+)$", expr.strip().rstrip(","))
    if m and m.group(2) in let:
        fid, fn = let[m.group(2)]
        src = form.get(fid)
        if fn == "val" and src in res: table[key] = res[src]; continue
        if fn == "val" and src == "''": table[key] = None; continue
        special.append((key, expr.strip()[:60], fid, fn, src)); continue
    special.append((key, expr.strip()[:70], "", "", ""))
print("표", len(table), "| 따로 처리", len(special))
for s in special: print("  ", s)
(out / "param_table.json").write_text(json.dumps(table, ensure_ascii=False, indent=0), encoding="utf-8")
d = json.loads((out / "data_982_1.json").read_text(encoding="utf-8"))["data"][0]
truth = json.loads((out / "truth_param_1.json").read_text(encoding="utf-8"))
bad = [(k, truth.get(k), d.get(src) if src else None) for k, src in table.items() if (truth.get(k) or "") != (str(d.get(src)) if src and d.get(src) is not None else "")]
print("표와 실제 본문이 다른 항목:", bad)
print("실제 본문에만 있는 항목:", [k for k in truth if k not in table and k not in [s[0] for s in special]])
