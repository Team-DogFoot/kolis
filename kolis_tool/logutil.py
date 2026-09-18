"""공통 로깅. 모든 모듈이 같은 파일 로그(work/logs/app-YYYYMMDD.log)에 쓰고, 프로그램 화면에는 콜백으로 밀어 넣는다.

- get_logger(name): 파일 핸들러 1개(날짜별 파일, 5MB 회전), 형식 `시각 수준 모듈 메시지`.
- UiLog(ui_callback, name): 화면+파일 동시 기록. log("...") / log.warn / log.error / log.step("단계", fn) 로 소요시간 기록.
"""
from __future__ import annotations
import datetime, logging, logging.handlers, time, traceback
from pathlib import Path

LOG_DIR = Path("work") / "logs"
_configured: dict[str, logging.Logger] = {}


def log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"app-{datetime.date.today():%Y%m%d}.log"


def get_logger(name: str = "kolis") -> logging.Logger:
    lg = logging.getLogger(name)
    if name in _configured:
        return lg
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    p = log_path()
    if not any(getattr(h, "_kolis", False) for h in lg.handlers):
        h = logging.handlers.RotatingFileHandler(p, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s %(message)s", "%H:%M:%S"))
        h._kolis = True  # type: ignore[attr-defined]
        lg.addHandler(h)
    _configured[name] = lg
    return lg


def tail(n: int = 40) -> list[str]:
    p = log_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:  # noqa: BLE001
        return []


class UiLog:
    """화면 콜백 + 파일 로그. 기존 kolis_ui.Log 와 같은 인터페이스(호출·warn·error·path)."""

    def __init__(self, ui=None, name: str = "kolis"):
        self.ui = ui or (lambda m: None)
        self.lg = get_logger(name)
        self.path = log_path()

    def __call__(self, msg: str, level: str = "INFO"):
        getattr(self.lg, level.lower() if level.lower() in ("debug", "info", "warning", "error") else "info")(msg)
        try:
            self.ui(msg if level == "INFO" else f"[{level}] {msg}")
        except Exception:  # noqa: BLE001
            pass

    def debug(self, msg):   # 파일에만
        self.lg.debug(msg)

    def warn(self, msg):
        self.lg.warning(msg)
        try:
            self.ui(f"[WARN] {msg}")
        except Exception:  # noqa: BLE001
            pass

    def error(self, msg):
        self.lg.error(msg)
        try:
            self.ui(f"[ERROR] {msg}")
        except Exception:  # noqa: BLE001
            pass

    def exception(self, msg: str, e: BaseException):
        self.lg.error(msg + "\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))
        try:
            self.ui(f"[ERROR] {msg}: {''.join(traceback.format_exception_only(type(e), e)).strip()}")
        except Exception:  # noqa: BLE001
            pass

    def step(self, name: str, fn, *a, **kw):
        """단계 실행: 시작·종료·소요시간을 기록. 예외는 기록 후 다시 던짐."""
        t0 = time.time()
        self(f"▶ {name}")
        try:
            r = fn(*a, **kw)
            self(f"✓ {name} ({time.time() - t0:.1f}초)")
            return r
        except BaseException as e:
            self.exception(f"✗ {name} ({time.time() - t0:.1f}초)", e)
            raise


def retry(log, what: str, fn, tries: int = 3, wait: float = 2.0, retry_on=(Exception,), on_fail=None):
    """fn() 을 최대 tries 번. 실패마다 기록, 사이에 on_fail() 로 정리. 마지막 예외를 던진다."""
    last: BaseException | None = None
    for i in range(1, tries + 1):
        try:
            return fn()
        except retry_on as e:  # type: ignore[misc]
            last = e
            (log.warn if hasattr(log, "warn") else log)(f"{what}: {i}/{tries} 실패 — {type(e).__name__}: {str(e)[:120]}")
            if on_fail:
                try:
                    on_fail()
                except Exception:  # noqa: BLE001
                    pass
            if i < tries:
                time.sleep(wait * i)
    assert last is not None
    raise last
