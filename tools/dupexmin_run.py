"""5.1-② 복본조사 실행(유저 승인 뒤에만). KEY 팝업을 닫고 '복본조사' 버튼을 누른 뒤 표를 읽는다."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
main = next(pg for pg in b.ctx.pages if "onlineBundleDupExmin" in pg.url); b.page = main
for pg in b.ctx.pages:
    if "dupexminkeyset" in pg.url:
        pg.click("#btnClose"); b._rec("click", selector="닫기(KEY설정 팝업)", changes=False); b.wait(1.0)
vals = b.eval("({yr: $('#acquisit_yr').val(), reg: $('#reg_code').val(), no: $('#accession_rec_no_start').val()})")
print("화면 값:", vals)
assert vals == {"yr": "2026", "reg": "FTX", "no": "1607"}, "화면 값이 다름"
msgs = []
main.on("dialog", lambda d: (msgs.append(d.message), b._rec("dialog", message=d.message, action="accept"), d.accept()))
b._rec("click", selector="#btnDupExmin(복본조사)", approved=True, changes=True)
main.click("#btnDupExmin")
for _ in range(60):
    b.wait(1.0)
    n = b.eval("(()=>{try{return grid.getRowsCount()}catch(e){return -1}})()")
    if n and n >= 25: break
print("표 행 수:", n, "| 확인창:", msgs)
rows = b.eval("(()=>{var o=[];for(var i=0;i<grid.getRowsCount();i++){o.push($('#jqxgrid').jqxGrid('getrowdata',i));}return o;})()")
Path("work/captures/wonbu").mkdir(parents=True, exist_ok=True)
Path(f"work/captures/wonbu/1607_dupexmin_result.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("캡처:", b.shot("dupexmin_1607_result"))
b.close()
