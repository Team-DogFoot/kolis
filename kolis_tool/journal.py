"""실행 기록. KOLIS 등록을 한 번 실행할 때마다 파일 하나(`work/logs/flow-<작품>-<시각>.jsonl`)에 한 줄씩 남긴다.
무엇을 남기나: 단계의 시작·끝·걸린 시간·결과, 실행 전 확인한 조건과 그 값, 화면 로그 전부, KOLIS 로 보낸 요청과 받은 응답 전부, 멈춘 이유와 오류 위치.
문제가 생겼을 때 이 파일 하나로 어디까지 했고 KOLIS 에 무엇이 반영됐는지 알 수 있어야 한다.
응답에는 접수자 아이디 같은 값이 들어 있다. `work/` 밖으로 내보내지 않는다(저장소 제외 폴더). 비밀번호는 어디에도 남지 않는다(다루지 않음)."""
from __future__ import annotations
import datetime, json, re, threading, traceback
from pathlib import Path


class Journal:
    def __init__(self, work_dir: Path, title: str):
        d = Path(work_dir) / "logs"
        d.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w가-힣]+", "", title)[:40] or "작품"
        self.path = d / f"flow-{name}-{datetime.datetime.now():%Y%m%d-%H%M%S}.jsonl"
        self._lock = threading.Lock()
        self.step = ""
        self.write("open", title=title)

    def write(self, kind: str, **data) -> None:
        row = {"time": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S.%f}"[:-3], "kind": kind, "step": self.step, **data}
        try:
            with self._lock, open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except Exception:  # noqa: BLE001  (기록 때문에 본 작업이 멈추면 안 된다)
            pass

    def error(self, e: BaseException, **data) -> None:
        self.write("error", type=type(e).__name__, message=str(e), trace="".join(traceback.format_exception(type(e), e, e.__traceback__))[-4000:], **data)

    def wrap(self, log):
        """화면 로그 함수를 감싸 같은 줄을 기록에도 남긴다. 원래 로그 객체의 속성(path, debug 등)은 그대로 쓸 수 있다."""
        from .logutil import UiLog
        ui = getattr(log, "ui", None) or (log if callable(log) else (lambda m: None))

        def both(m):
            self.write("log", text=str(m))
            ui(m)
        return UiLog(both)
