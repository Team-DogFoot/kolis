"""공통 상수·유틸."""
from __future__ import annotations
import re
from pathlib import Path

IMAGE_EXT_ALLOWED = {".jpg", ".jpeg"}                      # 지침: JPG, JPEG
IMAGE_EXT_ACCEPTED = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}  # 수집 대상 형식(경고만)

# KORMARC 발행국 부호(국내 지역). 반입 예시에서 확인된 값: 서울 ulk, 경기 ggk.
# 나머지는 KORMARC 부록 기준으로 적었으나 현장에서 한 번 대조할 것(FIELD-CHECKLIST 참조).
REGION_CODE = {
    "서울": "ulk", "부산": "bnk", "대구": "tgk", "인천": "ick", "광주": "kjk", "대전": "tjk",
    "울산": "usk", "세종": "sjk", "경기": "ggk", "강원": "gak", "충북": "hbk", "충남": "hck",
    "전북": "jbk", "전남": "jnk", "경북": "gbk", "경남": "gnk", "제주": "jjk",
}
CODE_REGION = {v: k for k, v in REGION_CODE.items()}

# 시·군 → 광역 (발행지 텍스트에서 코드 추정용, 필요 시 확장)
CITY_TO_REGION = {
    "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천", "광주": "광주", "대전": "대전",
    "울산": "울산", "세종": "세종", "제주": "제주",
    "수원": "경기", "성남": "경기", "고양": "경기", "용인": "경기", "부천": "경기", "안산": "경기",
    "안양": "경기", "남양주": "경기", "화성": "경기", "평택": "경기", "의정부": "경기", "파주": "경기",
    "시흥": "경기", "김포": "경기", "광명": "경기", "광주시": "경기", "군포": "경기", "하남": "경기",
    "오산": "경기", "이천": "경기", "안성": "경기", "의왕": "경기", "양주": "경기", "구리": "경기",
    "포천": "경기", "여주": "경기", "동두천": "경기", "과천": "경기",
    "춘천": "강원", "원주": "강원", "강릉": "강원", "청주": "충북", "충주": "충북", "천안": "충남",
    "아산": "충남", "전주": "전북", "익산": "전북", "군산": "전북", "목포": "전남", "여수": "전남",
    "순천": "전남", "포항": "경북", "구미": "경북", "경주": "경북", "창원": "경남", "김해": "경남",
    "진주": "경남", "양산": "경남",
}

ROLE_WORDS = ["글·그림", "글/그림", "글, 그림", "글그림", "글", "그림", "원작", "각색", "작화", "스토리", "채색", "편집", "번역", "감수"]
CORPORATE_HINTS = ["주식회사", "(주)", "㈜", "스튜디오", "studio", "컴퍼니", "company", "엔터테인먼트", "미디어",
                   "출판", "북스", "books", "코믹스", "comics", "제작", "팀", "team", "협회", "센터", "랩", "lab"]


MANIFEST_DIR = "_kolis_manifests"


def manifest_path(target: Path, kind: str) -> Path:
    """되돌리기 기록 파일의 위치. 대상 폴더 **안이 아니라** 그 부모의 `_kolis_manifests/<폴더명>.<kind>.json`.
    2026-09-18 교훈: 원고 폴더 안에 기록 파일을 두면 KOLIS 원문일괄등록(폴더 드래그) 때 같이 올라가 오류를 낸다."""
    target = Path(target)
    d = target.parent / MANIFEST_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{target.name}.{kind}.json"


def find_manifest(target: Path, kind: str, legacy_name: str) -> Path | None:
    """새 위치 → 없으면 예전 위치(폴더 안)를 찾는다. 예전 위치면 새 위치로 옮긴 뒤 돌려준다."""
    target = Path(target)
    new = target.parent / MANIFEST_DIR / f"{target.name}.{kind}.json"
    if new.exists():
        return new
    old = target / legacy_name
    if old.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        return new
    return None


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def human_mb(nbytes: int) -> str:
    """완료 사례(45건)와 대조해 맞춘 규칙: 윈도 탐색기 폴더 속성처럼 유효숫자 3자리로 내림.
    100 이상 → 정수(165), 10~100 → 소수 1자리 내림을 두 자리로 표기(96.59→'96.50', 78.06→'78'), 10 미만 → 소수 2자리(9.22)."""
    import math
    mb = nbytes / (1024 * 1024)
    if mb >= 100:
        return str(math.floor(mb))
    if mb >= 10:
        v = math.floor(mb * 10) / 10
        return str(int(v)) if v == int(v) else f"{v:.2f}"
    return f"{math.floor(mb * 100) / 100:.2f}"


def extent_string(count: int, nbytes: int, color: str = "천연색") -> str:
    """반입용 extent 문구. 예: '이미지 파일 109개 (9.22 MB) : 천연색'"""
    return f"이미지 파일 {count}개 ({human_mb(nbytes)} MB) : {color}"


def region_code_from_place(place: str) -> str | None:
    p = place.strip().strip("[]")
    for k, region in CITY_TO_REGION.items():
        if p.startswith(k):
            return REGION_CODE.get(region)
    for region, code in REGION_CODE.items():
        if region in p:
            return code
    return None


def list_images(folder: Path) -> list[Path]:
    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]
    files = [p for p in files if p.suffix.lower() in IMAGE_EXT_ACCEPTED]
    return sorted(files, key=lambda p: natural_key(p.name))


def resolve_folder(root, title: str, part: str, fname: str, index: int, total: int):
    """작품 회차 폴더 찾기. 1) 출판사 파일명 2) 제목+회차 3) 제목만 단일 매칭 4) 폴더 수가 행 수와 같으면 순서대로(정렬)."""
    from pathlib import Path
    root = Path(root)
    dirs = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: natural_key(p.name))
    if fname:
        for p in dirs:
            if p.name == fname or p.name.startswith(fname):
                return p, "파일명"
    t = (title or "").replace(" ", "")
    cands = [p for p in dirs if t and t in p.name.replace(" ", "")]
    num = re.sub(r"\D", "", part or "")
    if num:
        for p in cands:
            if re.search(rf"(?<!\d)0*{int(num)}(?!\d)", p.name):
                return p, "제목+회차"
    if len(cands) == 1:
        return cands[0], "제목"
    if len(dirs) == total and 0 <= index < total:
        return dirs[index], "순서(폴더 수=행 수)"
    return None, ""
