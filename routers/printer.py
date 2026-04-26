from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import models, dependencies
from database import get_db
from utils import verify_store_permission

router = APIRouter(tags=["print"])


def try_auto_print_receipt(order, store) -> None:
    """결제 완료 후 영수증 자동 출력. has_pos=True거나 프린터 미설정이면 건너뜀. 실패해도 무시."""
    try:
        if store.has_pos:
            return
        if (store.receipt_printer_type or "FILE").upper() == "FILE":
            return
        p = _get_printer(
            store.receipt_printer_type,
            store.receipt_printer_host or "",
            store.receipt_printer_port or "9100",
            store.receipt_printer_baud or 9600,
        )
        _build_receipt(p, order, store)
    except Exception:
        pass


# ─────────────────────────────────────────────
# 프린터 인스턴스 생성
# ─────────────────────────────────────────────

def _get_printer(ptype: str, host: str, port: str, baud: int):
    ptype = (ptype or "FILE").upper()
    try:
        if ptype == "NETWORK":
            from escpos.printer import Network
            return Network(host, int(port or 9100), timeout=5)
        elif ptype == "SERIAL":
            from escpos.printer import Serial
            return Serial(port or "COM1", baudrate=int(baud or 9600), timeout=5)
        else:
            from escpos.printer import Dummy
            return Dummy()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"프린터 연결 실패: {e}")


def _safe_text(text: str) -> str:
    """ESC/POS 출력용 안전 텍스트 (길이 제한)"""
    return text[:20] if text else ""


# ─────────────────────────────────────────────
# 영수증 포맷 (Printer 1)
# ─────────────────────────────────────────────

def _build_receipt(p, order, store):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    order_type_label = "포장" if order.order_type == "TAKEOUT" else "홀"
    table_label = order.table.name if order.table else "포장"
    method_map = {"card": "카드", "CARD": "카드", "cash": "현금", "CASH": "현금",
                  "후불": "후불", "기타": "기타"}

    LINE = "=" * 32

    p.set(align="center", bold=True, double_height=True, double_width=False)
    p.text(f"{store.name[:16]}\n")
    p.set(align="left", bold=False, double_height=False)
    p.text(LINE + "\n")

    # 주문 헤더
    p.set(bold=True)
    p.text(f"테이블: {table_label}   [{order_type_label}]\n")
    p.set(bold=False)
    p.text(f"주문번호: #{order.id}  일련번호: {order.daily_number or '-'}\n")
    p.text(LINE + "\n")

    # 메뉴 목록
    p.set(bold=True)
    p.text(f"{'메뉴명':<16}{'수량':>4}{'금액':>10}\n")
    p.set(bold=False)
    p.text("-" * 32 + "\n")

    active_items = [i for i in order.items if not i.is_cancelled]
    for item in active_items:
        name = item.menu_name[:15] if len(item.menu_name) > 15 else item.menu_name
        total = item.price * item.quantity
        p.text(f"{name:<16}{item.quantity:>4}{total:>10,}\n")
        if item.options_desc:
            for opt in item.options_desc.split(","):
                opt = opt.strip()
                if opt:
                    p.text(f"  └ {opt}\n")

    p.text(LINE + "\n")

    # 합계
    paid = order.paid_amount or order.total_price
    p.set(bold=True, double_height=True)
    p.text(f"합  계:  {paid:>12,}원\n")
    p.set(bold=False, double_height=False)

    if order.payment_method:
        label = method_map.get(order.payment_method, order.payment_method)
        p.text(f"결제방법: {label}\n")

    p.text(LINE + "\n")
    p.set(align="center")
    p.text("감사합니다! 다음에 또 오세요.\n")
    p.set(align="left")
    p.text(f"{now}\n")
    p.text("\n\n\n")
    p.cut()


# ─────────────────────────────────────────────
# 주방 주문서 포맷 (Printer 2)
# ─────────────────────────────────────────────

def _build_kitchen(p, order, store):
    now = datetime.now().strftime("%H:%M")
    order_type_label = "포장" if order.order_type == "TAKEOUT" else "홀"
    table_label = order.table.name if order.table else "포장"

    LINE = "=" * 32

    p.set(align="center", bold=True, double_height=True)
    p.text("★ 주방 주문서 ★\n")
    p.set(bold=False, double_height=False)
    p.text(LINE + "\n")

    p.set(align="left", bold=True, double_height=True)
    p.text(f"테이블: {table_label} [{order_type_label}]\n")
    p.set(bold=False, double_height=False)
    p.text(f"시간: {now}   주문번호: #{order.id}\n")
    p.text(LINE + "\n")

    active_items = [i for i in order.items if not i.is_cancelled]
    for idx, item in enumerate(active_items, 1):
        p.set(bold=True, double_height=True)
        p.text(f"[{idx}] {item.menu_name}  x{item.quantity}\n")
        p.set(bold=False, double_height=False)
        if item.options_desc:
            for opt in item.options_desc.split(","):
                opt = opt.strip()
                if opt:
                    p.text(f"    ▶ {opt}\n")

    p.text(LINE + "\n")
    p.text("\n\n\n")
    p.cut()


# ─────────────────────────────────────────────
# API 엔드포인트
# ─────────────────────────────────────────────

def _get_store_and_order(db, store_id, order_id, current_user):
    verify_store_permission(db, current_user, store_id)
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    order = db.query(models.Order).filter(
        models.Order.id == order_id, models.Order.store_id == store_id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return store, order


@router.post("/stores/{store_id}/print/receipt")
def print_receipt(
    store_id: int, order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """영수증 출력 (Printer 1 — 계산대)"""
    store, order = _get_store_and_order(db, store_id, order_id, current_user)
    p = _get_printer(
        store.receipt_printer_type or "FILE",
        store.receipt_printer_host or "",
        store.receipt_printer_port or "9100",
        store.receipt_printer_baud or 9600,
    )
    _build_receipt(p, order, store)

    if (store.receipt_printer_type or "FILE").upper() == "FILE":
        debug = getattr(p, "output", b"").decode("latin-1", errors="replace")
        return {"ok": True, "simulated": True, "debug_output": debug}
    return {"ok": True, "simulated": False, "message": "영수증 출력 완료"}


@router.post("/stores/{store_id}/print/kitchen")
def print_kitchen(
    store_id: int, order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """주방 주문서 출력 (Printer 2 — 주방)"""
    store, order = _get_store_and_order(db, store_id, order_id, current_user)
    p = _get_printer(
        store.kitchen_printer_type or "FILE",
        store.kitchen_printer_host or "",
        store.kitchen_printer_port or "9100",
        store.kitchen_printer_baud or 9600,
    )
    _build_kitchen(p, order, store)

    if (store.kitchen_printer_type or "FILE").upper() == "FILE":
        debug = getattr(p, "output", b"").decode("latin-1", errors="replace")
        return {"ok": True, "simulated": True, "debug_output": debug}
    return {"ok": True, "simulated": False, "message": "주방 주문서 출력 완료"}


@router.post("/stores/{store_id}/print/both")
def print_both(
    store_id: int, order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """영수증 + 주방 주문서 동시 출력 (UNIFIED 구성용)"""
    store, order = _get_store_and_order(db, store_id, order_id, current_user)

    p1 = _get_printer(store.receipt_printer_type or "FILE", store.receipt_printer_host or "",
                      store.receipt_printer_port or "9100", store.receipt_printer_baud or 9600)
    _build_receipt(p1, order, store)
    _build_kitchen(p1, order, store)

    if (store.receipt_printer_type or "FILE").upper() == "FILE":
        debug = getattr(p1, "output", b"").decode("latin-1", errors="replace")
        return {"ok": True, "simulated": True, "debug_output": debug}
    return {"ok": True, "simulated": False, "message": "통합 출력 완료"}


@router.post("/stores/{store_id}/print/test")
def test_print(
    store_id: int,
    printer: int = 1,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """프린터 테스트 출력"""
    verify_store_permission(db, current_user, store_id)
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

    if printer == 1:
        ptype = store.receipt_printer_type or "FILE"
        p = _get_printer(ptype, store.receipt_printer_host or "",
                         store.receipt_printer_port or "9100", store.receipt_printer_baud or 9600)
        label = "영수증 프린터 (Printer 1)"
    else:
        ptype = store.kitchen_printer_type or "FILE"
        p = _get_printer(ptype, store.kitchen_printer_host or "",
                         store.kitchen_printer_port or "9100", store.kitchen_printer_baud or 9600)
        label = "주방 프린터 (Printer 2)"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p.set(align="center", bold=True, double_height=True)
    p.text("[ 테스트 출력 ]\n")
    p.set(bold=False, double_height=False)
    p.text("=" * 32 + "\n")
    p.text(f"{store.name}\n")
    p.text(f"{label}\n")
    p.set(align="left")
    p.text(f"출력시간: {now}\n")
    p.text("=" * 32 + "\n")
    p.set(align="center")
    p.text("정상 출력되었습니다.\n")
    p.text("\n\n\n")
    p.cut()

    is_sim = ptype.upper() == "FILE"
    debug = getattr(p, "output", b"").decode("latin-1", errors="replace") if is_sim else ""
    return {"ok": True, "simulated": is_sim, "label": label, "debug_output": debug}
