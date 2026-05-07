from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json

# 프로젝트 내부 모듈
import models
import schemas
import crud
import dependencies
from database import get_db
from connection_manager import manager

# 공통 함수 (utils.py)
from utils import verify_store_permission, create_audit_log

# ✨ 라우터 생성
router = APIRouter(tags=["Stores & Brands"])

# =========================================================
# 🏢 브랜드 및 그룹 관리 API
# =========================================================

@router.post("/brands/", response_model=schemas.BrandResponse)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="오직 슈퍼 관리자만 브랜드를 생성할 수 있습니다.")
    db_brand = models.Brand(**brand.dict())
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_BRAND", 
        target_type="BRAND", target_id=db_brand.id, 
        details=f"신규 브랜드 생성: [{db_brand.name}]"
    )
    return db_brand

@router.get("/brands/", response_model=List[schemas.BrandResponse])
def read_brands(db: Session = Depends(get_db)):
    return db.query(models.Brand).all()

@router.get("/brands/{brand_id}", response_model=schemas.BrandResponse)
def read_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand: 
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.post("/groups/", response_model=schemas.GroupResponse)
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
        
    target_brand_id = group.brand_id if current_user.role == models.UserRole.SUPER_ADMIN else current_user.brand_id
    db_group = models.Group(name=group.name, brand_id=target_brand_id)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


# =========================================================
# 🏪 매장 생성 및 조회 API
# =========================================================

@router.post("/stores/", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.STORE_OWNER and current_user.store_id is not None:
        raise HTTPException(status_code=400, detail="이미 등록된 가게가 있습니다.")
        
    new_store = crud.create_store(db=db, store=store)
    
    # 점주가 직접 생성한 경우 자신의 계정에 매장 ID 연결
    if current_user.role == models.UserRole.STORE_OWNER:
        current_user.store_id = new_store.id
        db.add(current_user)
        db.commit()
        
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_STORE", 
        target_type="STORE", target_id=new_store.id, 
        details=f"새 매장 오픈: [{new_store.name}]"
    )
    return new_store

@router.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if not db_store: 
        raise HTTPException(status_code=404, detail="Store not found")
        
    store_data = schemas.StoreResponse.model_validate(db_store).model_dump()
    
    # 메뉴별 연결된 옵션 그룹 정보를 조합
    for category in store_data.get("categories", []):
        for menu in category.get("menus", []):
            links = db.query(models.MenuOptionLink).filter(models.MenuOptionLink.menu_id == menu["id"]).order_by(models.MenuOptionLink.order_index).all()
            option_groups = []
            for link in links:
                og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if og: 
                    option_groups.append(schemas.OptionGroupResponse.model_validate(og).model_dump())
            menu["option_groups"] = option_groups
            
    return store_data

@router.get("/groups/my/stores", response_model=List[schemas.StoreResponse])
def read_my_stores(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: 
        return db.query(models.Store).order_by(models.Store.id).all()
        
    if current_user.role == models.UserRole.BRAND_ADMIN: 
        return db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).order_by(models.Store.id).all() if current_user.brand_id else []
        
    if current_user.role == models.UserRole.GROUP_ADMIN: 
        return db.query(models.Store).filter(models.Store.group_id == current_user.group_id).order_by(models.Store.id).all() if current_user.group_id else []
        
    if current_user.role == models.UserRole.STORE_OWNER: 
        return db.query(models.Store).filter(models.Store.id == current_user.store_id).order_by(models.Store.id).all() if current_user.store_id else []
        
    return []

@router.patch("/stores/{store_id}", response_model=schemas.StoreResponse)
def update_store_info(store_id: int, store_update: schemas.StoreUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store: 
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
        
    changed_fields = [k for k, v in store_update.dict(exclude_unset=True).items() if getattr(store, k, None) != v]
    for key, value in store_update.dict(exclude_unset=True).items():
        setattr(store, key, value)

    db.commit()
    db.refresh(store)
    create_audit_log(db=db, user_id=current_user.id, action="UPDATE_STORE", target_type="STORE", target_id=store.id, details=f"매장 정보 수정: [{store.name}] 변경 항목: {', '.join(changed_fields)}")
    return store


# =========================================================
# 🚀 프랜차이즈 본사: 메뉴 일괄 배포 
# =========================================================

@router.post("/brands/distribute-menu")
def distribute_menu(req: schemas.MenuDistributeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="메뉴 배포 권한이 없습니다.")
        
    source_category = db.query(models.Category).filter(models.Category.id == req.source_category_id).first()
    if not source_category: 
        raise HTTPException(status_code=404, detail="원본 카테고리를 찾을 수 없습니다.")

    success_count, update_count = 0, 0
    
    for store_id in req.target_store_ids:
        target_store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not target_store: continue

        og_mapping = {}
        target_category = db.query(models.Category).filter(models.Category.store_id == store_id, models.Category.name == source_category.name).first()
        
        if not target_category:
            target_category = models.Category(store_id=store_id, name=source_category.name, order_index=source_category.order_index)
            db.add(target_category)
            db.commit()
            db.refresh(target_category)

        for source_menu in source_category.menus:
            target_menu = db.query(models.Menu).filter(models.Menu.category_id == target_category.id, models.Menu.name == source_menu.name).first()
            calculated_price = source_menu.price + (target_store.price_markup or 0)
            
            if target_menu:
                target_menu.price = calculated_price 
                target_menu.is_price_fixed = source_menu.is_price_fixed 
                target_menu.description = source_menu.description
                target_menu.image_url = source_menu.image_url
                target_menu.order_index = source_menu.order_index
                update_count += 1
            else:
                target_menu = models.Menu(
                    store_id=store_id, category_id=target_category.id, name=source_menu.name, 
                    price=calculated_price, is_price_fixed=source_menu.is_price_fixed, 
                    description=source_menu.description, image_url=source_menu.image_url, 
                    order_index=source_menu.order_index
                )
                db.add(target_menu)
                db.commit()
                db.refresh(target_menu)
                success_count += 1

            for link in source_menu.menu_option_links:
                source_og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if not source_og: continue
                
                if source_og.id in og_mapping:
                    target_og = og_mapping[source_og.id]
                else:
                    target_og = db.query(models.OptionGroup).filter(models.OptionGroup.store_id == store_id, models.OptionGroup.name == source_og.name).first()
                    if not target_og:
                        target_og = models.OptionGroup(
                            store_id=store_id, name=source_og.name, 
                            is_single_select=source_og.is_single_select, 
                            is_required=source_og.is_required, max_select=source_og.max_select
                        )
                        db.add(target_og)
                        db.commit()
                        db.refresh(target_og)
                    og_mapping[source_og.id] = target_og
                
                target_og.is_single_select = source_og.is_single_select
                target_og.is_required = source_og.is_required
                target_og.max_select = source_og.max_select
                db.commit()
                    
                for s_opt in source_og.options:
                    t_opt = db.query(models.Option).filter(models.Option.group_id == target_og.id, models.Option.name == s_opt.name).first()
                    if t_opt:
                        t_opt.price = s_opt.price
                        t_opt.is_default = s_opt.is_default
                        t_opt.order_index = s_opt.order_index
                    else:
                        new_opt = models.Option(
                            store_id=store_id, group_id=target_og.id, name=s_opt.name, 
                            price=s_opt.price, is_default=s_opt.is_default, order_index=s_opt.order_index
                        )
                        db.add(new_opt)
                db.commit() 
                    
                if not db.query(models.MenuOptionLink).filter(models.MenuOptionLink.menu_id == target_menu.id, models.MenuOptionLink.option_group_id == target_og.id).first():
                    db.add(models.MenuOptionLink(menu_id=target_menu.id, option_group_id=target_og.id, order_index=link.order_index))
            db.commit()
            
    create_audit_log(db=db, user_id=current_user.id, action="DISTRIBUTE_MENU", target_type="CATEGORY", target_id=req.source_category_id, details=f"메뉴 일괄 배포: [{source_category.name}] → {len(req.target_store_ids)}개 매장 (신규 {success_count}개, 업데이트 {update_count}개)")
    return {"message": f"배포 완료! (신규추가: {success_count}개, 업데이트: {update_count}개)"}


# =========================================================
# 📊 통계 및 매출 조회
# =========================================================

@router.get("/hq/stats", response_model=schemas.HQSalesStatResponse)
def get_hq_sales_stats(start_date: str, end_date: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.GROUP_ADMIN]:
        raise HTTPException(status_code=403, detail="본사 관리자만 접근할 수 있습니다.")
        
    query = db.query(models.Store)
    if current_user.role == models.UserRole.BRAND_ADMIN: 
        query = query.filter(models.Store.brand_id == current_user.brand_id)
    elif current_user.role == models.UserRole.GROUP_ADMIN: 
        query = query.filter(models.Store.group_id == current_user.group_id)
        
    stores = query.all()
    store_ids = [s.id for s in stores]

    if not store_ids: 
        return {"total_revenue": 0, "total_order_count": 0, "total_royalty_fee": 0, "store_stats": []}

    orders = db.query(models.Order).filter(
        models.Order.store_id.in_(store_ids),
        models.Order.payment_status.in_(["PAID", "PARTIAL_CANCELLED"]),
        models.Order.created_at >= f"{start_date} 00:00:00",
        models.Order.created_at <= f"{end_date} 23:59:59"
    ).all()

    total_rev = sum(o.paid_amount or o.total_price for o in orders)

    store_data = {
        s.id: {
            "name": s.name, "brand_name": s.brand.name if s.brand else "독립 매장", 
            "region": s.region or "미지정", "is_direct_manage": s.is_direct_manage, 
            "rev": 0, "cnt": 0, "r_type": s.royalty_type or "PERCENTAGE", "r_amount": s.royalty_amount or 0.0
        } for s in stores
    }
    
    for o in orders:
        if o.store_id in store_data:
            store_data[o.store_id]["rev"] += (o.paid_amount or o.total_price)
            store_data[o.store_id]["cnt"] += 1

    store_stats = []
    total_royalty = 0 
    
    for sid, data in store_data.items():
        calc_royalty = int(data["rev"] * (data["r_amount"] / 100)) if data["r_type"] == "PERCENTAGE" else int(data["r_amount"])
        total_royalty += calc_royalty
        store_stats.append({
            "store_id": sid, "store_name": data["name"], "brand_name": data["brand_name"], 
            "region": data["region"], "is_direct_manage": data["is_direct_manage"], 
            "revenue": data["rev"], "order_count": data["cnt"], "royalty_fee": calc_royalty
        })
        
    store_stats.sort(key=lambda x: x["revenue"], reverse=True)

    return {"total_revenue": total_rev, "total_order_count": len(orders), "total_royalty_fee": total_royalty, "store_stats": store_stats}

@router.get("/stores/{store_id}/stats")
def get_store_stats(store_id: int, start_date: str, end_date: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    from datetime import datetime as dt, timedelta
    verify_store_permission(db, current_user, store_id)

    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    closing_hour = int(store.closing_hour or 0) if store else 0

    # closing_hour 기준으로 영업일 경계 설정
    start_dt = dt.strptime(start_date, "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0)
    end_dt   = dt.strptime(end_date,   "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0) + timedelta(days=1)

    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status.in_(["PAID", "DEFERRED", "PARTIAL_CANCELLED", "CANCELLED"]),
        models.Order.created_at >= start_dt,
        models.Order.created_at < end_dt
    ).all()

    paid_orders     = [o for o in orders if o.payment_status in ["PAID", "PARTIAL_CANCELLED"]]
    deferred_orders = [o for o in orders if o.payment_status == "DEFERRED"]
    cancelled_orders = [o for o in orders if o.payment_status == "CANCELLED"]

    total_revenue    = sum(o.paid_amount or o.total_price for o in paid_orders)
    deferred_revenue = sum(o.total_price for o in deferred_orders)
    cancelled_count  = len(cancelled_orders)
    refund_amount    = sum(o.total_price for o in cancelled_orders)
    order_count      = len(paid_orders)

    # 직전 동일 기간 매출 (성장률 계산용)
    period_days   = (end_dt - start_dt).days
    prev_end_dt   = start_dt
    prev_start_dt = prev_end_dt - timedelta(days=period_days)

    prev_orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status.in_(["PAID", "PARTIAL_CANCELLED"]),
        models.Order.created_at >= prev_start_dt,
        models.Order.created_at < prev_end_dt
    ).all()

    prev_revenue = sum(o.paid_amount or o.total_price for o in prev_orders)
    prev_count   = len(prev_orders)
    growth_rate  = round(((total_revenue - prev_revenue) / prev_revenue) * 100, 1) if prev_revenue > 0 else None

    # 집계 데이터 초기화
    WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
    menu_data           = {}
    category_data       = {}
    hourly_data         = {f"{i:02d}": {"sales": 0, "count": 0} for i in range(24)}
    daily_data          = {}
    monthly_data        = {}
    weekday_data        = {i: {"sales": 0, "count": 0} for i in range(7)}
    payment_method_data = {}
    order_type_data     = {}
    discount_original   = 0  # 할인 전 메뉴 금액 합계
    discount_actual     = 0  # 실제 결제 금액 합계 (옵션 포함)
    has_original_price  = False

    # 카테고리 이름 캐시 (menu_name → category_name)
    menu_category_map = {}
    for cat in db.query(models.Category).filter(models.Category.store_id == store_id).all():
        for menu in cat.menus:
            menu_category_map[menu.name] = cat.name

    for order in orders:
        if order.payment_status == "CANCELLED":
            continue
        try:
            created = order.created_at
            if isinstance(created, str):
                created = dt.strptime(created.split(".")[0], "%Y-%m-%d %H:%M:%S")

            # closing_hour 보정: 영업일 기준 날짜
            business_dt = created - timedelta(hours=closing_hour)
            d_part      = business_dt.strftime("%Y-%m-%d")
            order_hour  = created.strftime("%H")
            order_month = business_dt.strftime("%Y-%m")
            weekday_idx = business_dt.weekday()  # 0=월 … 6=일

            is_paid = order.payment_status in ["PAID", "PARTIAL_CANCELLED"]
            order_revenue = (order.paid_amount or order.total_price) if is_paid else 0

            # 매출/건수 집계는 결제완료 주문만
            if is_paid:
                hourly_data[order_hour]["sales"] += order_revenue
                hourly_data[order_hour]["count"] += 1

                daily_data.setdefault(d_part, {"sales": 0, "count": 0})
                daily_data[d_part]["sales"] += order_revenue
                daily_data[d_part]["count"] += 1

                monthly_data.setdefault(order_month, {"sales": 0, "count": 0})
                monthly_data[order_month]["sales"] += order_revenue
                monthly_data[order_month]["count"] += 1

                weekday_data[weekday_idx]["sales"] += order_revenue
                weekday_data[weekday_idx]["count"] += 1

                otype = order.order_type or "DINE_IN"
                order_type_data.setdefault(otype, {"count": 0, "revenue": 0})
                order_type_data[otype]["count"] += 1
                order_type_data[otype]["revenue"] += order_revenue

            # 결제수단: 후불 포함 (미수금 추적용)
            method = "후불" if order.payment_status == "DEFERRED" else (order.payment_method or "기타")
            payment_method_data.setdefault(method, {"count": 0, "revenue": 0})
            payment_method_data[method]["count"] += 1
            payment_method_data[method]["revenue"] += order_revenue

            for item in order.items:
                if item.is_cancelled:
                    continue
                item_revenue = item.price * item.quantity

                menu_data.setdefault(item.menu_name, {"count": 0, "revenue": 0})
                menu_data[item.menu_name]["count"] += item.quantity
                menu_data[item.menu_name]["revenue"] += item_revenue

                cat_name = menu_category_map.get(item.menu_name, "미분류")
                category_data.setdefault(cat_name, {"count": 0, "revenue": 0})
                category_data[cat_name]["count"] += item.quantity
                category_data[cat_name]["revenue"] += item_revenue

                if is_paid and item.original_price is not None:
                    has_original_price = True
                    discount_original += item.original_price * item.quantity
                    discount_actual   += item_revenue
        except Exception:
            pass

    def _avg(sales, count):
        return int(sales / count) if count > 0 else 0

    average_order_value  = _avg(total_revenue, order_count)
    prev_avg_order_value = _avg(prev_revenue, prev_count)
    aov_growth_rate      = round(((average_order_value - prev_avg_order_value) / prev_avg_order_value) * 100, 1) if prev_avg_order_value > 0 else None
    count_growth_rate    = round(((order_count - prev_count) / prev_count) * 100, 1) if prev_count > 0 else None

    menu_stats           = sorted([{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in menu_data.items()], key=lambda x: x["revenue"], reverse=True)
    category_stats       = sorted([{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in category_data.items()], key=lambda x: x["revenue"], reverse=True)
    payment_method_stats = [{"method": k, "count": v["count"], "revenue": v["revenue"], "avg_order_value": _avg(v["revenue"], v["count"])} for k, v in payment_method_data.items()]
    order_type_stats     = [{"type": k, "count": v["count"], "revenue": v["revenue"], "avg_order_value": _avg(v["revenue"], v["count"])} for k, v in order_type_data.items()]
    weekday_stats        = [{"weekday": WEEKDAY_NAMES[i], "weekday_index": i, "sales": weekday_data[i]["sales"], "count": weekday_data[i]["count"], "avg_order_value": _avg(weekday_data[i]["sales"], weekday_data[i]["count"])} for i in range(7)]

    discount_gap = discount_original - discount_actual if has_original_price else None

    return {
        "total_revenue":        total_revenue,
        "deferred_revenue":     deferred_revenue,
        "cancelled_count":      cancelled_count,
        "refund_amount":        refund_amount,
        "order_count":          order_count,
        "average_order_value":  average_order_value,
        "prev_period_revenue":  prev_revenue,
        "prev_period_count":    prev_count,
        "prev_avg_order_value": prev_avg_order_value,
        "growth_rate":          growth_rate,
        "aov_growth_rate":      aov_growth_rate,
        "count_growth_rate":    count_growth_rate,
        "closing_hour":         closing_hour,
        "menu_stats":           menu_stats,
        "category_stats":       category_stats,
        "hourly_stats":         [{"hour": k, "sales": v["sales"], "count": v["count"], "avg_order_value": _avg(v["sales"], v["count"])} for k, v in hourly_data.items()],
        "daily_stats":          [{"date": k, "sales": v["sales"], "count": v["count"], "avg_order_value": _avg(v["sales"], v["count"])} for k, v in sorted(daily_data.items(), reverse=True)],
        "monthly_stats":        [{"month": k, "sales": v["sales"], "count": v["count"], "avg_order_value": _avg(v["sales"], v["count"])} for k, v in sorted(monthly_data.items(), reverse=True)],
        "weekday_stats":        weekday_stats,
        "payment_method_stats": payment_method_stats,
        "order_type_stats":     order_type_stats,
        "discount_original":    discount_original if has_original_price else None,
        "discount_actual":      discount_actual   if has_original_price else None,
        "discount_gap":         discount_gap,
    }


@router.get("/stores/{store_id}/orders/by-date", response_model=List[schemas.OrderResponse])
def get_orders_by_date(
    store_id: int,
    date: str,
    closing_hour: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """특정 영업일의 전체 주문 목록 (드릴다운용)"""
    from datetime import datetime as dt, timedelta
    verify_store_permission(db, current_user, store_id)

    start_dt = dt.strptime(date, "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0)
    end_dt   = start_dt + timedelta(days=1)

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.store_id == store_id,
            models.Order.payment_status.in_(["PAID", "DEFERRED", "PARTIAL_CANCELLED", "CANCELLED"]),
            models.Order.created_at >= start_dt,
            models.Order.created_at < end_dt,
        )
        .order_by(models.Order.created_at.asc())
        .all()
    )

    result = []
    for o in orders:
        data = schemas.OrderResponse.model_validate(o).model_dump()
        data["table_name"] = o.table.name if o.table else "포장/미지정"
        result.append(data)
    return result


@router.get("/stores/{store_id}/orders/period", response_model=List[schemas.OrderResponse])
def get_orders_by_period(
    store_id: int,
    start_date: str,
    end_date: str,
    status: str,          # 콤마 구분 가능: "CANCELLED" 또는 "DEFERRED"
    closing_hour: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """기간 + 상태별 주문 목록 (취소/후불 드릴다운용)"""
    from datetime import datetime as dt, timedelta
    verify_store_permission(db, current_user, store_id)

    start_dt = dt.strptime(start_date, "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0)
    end_dt   = dt.strptime(end_date,   "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0) + timedelta(days=1)
    statuses = [s.strip() for s in status.split(",")]

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.store_id == store_id,
            models.Order.payment_status.in_(statuses),
            models.Order.created_at >= start_dt,
            models.Order.created_at < end_dt,
        )
        .order_by(models.Order.created_at.desc())
        .all()
    )

    result = []
    for o in orders:
        data = schemas.OrderResponse.model_validate(o).model_dump()
        data["table_name"] = o.table.name if o.table else "포장/미지정"
        result.append(data)
    return result


# =========================================================
# 🚨 긴급 모드 토글
# =========================================================

@router.post("/stores/{store_id}/emergency-mode")
async def toggle_emergency_mode(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """
    긴급 모드 ON/OFF 토글.
    ON: 선불 결제를 차단하고 후불(현금/카드단말기)로 강제 전환.
    OFF: 정상 운영 복귀.
    """
    verify_store_permission(db, current_user, store_id)
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")

    store.is_emergency_mode = not store.is_emergency_mode
    db.commit()

    action = "EMERGENCY_ON" if store.is_emergency_mode else "EMERGENCY_OFF"
    create_audit_log(
        db=db, user_id=current_user.id, action=action,
        target_type="STORE", target_id=store_id,
        details=f"긴급 모드 {'활성화' if store.is_emergency_mode else '해제'}: [{store.name}]",
    )

    try:
        await manager.broadcast(
            json.dumps({
                "type": "EMERGENCY_MODE_CHANGED",
                "is_emergency": store.is_emergency_mode,
            }, ensure_ascii=False),
            store_id=store_id,
        )
    except Exception:
        pass

    return {
        "is_emergency_mode": store.is_emergency_mode,
        "message": "긴급 모드 활성화" if store.is_emergency_mode else "정상 모드 복귀",
    }


# =========================================================
# 일마감 (Daily Closing)
# =========================================================

def _build_closing_summary(store_id: int, business_date: str, db: Session):
    """영업일 기준 하루치 주문을 집계해 마감 데이터를 반환."""
    from datetime import datetime as dt, timedelta
    import json as _json

    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    closing_hour = int(store.closing_hour or 0) if store else 0

    start_dt = dt.strptime(business_date, "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0)
    end_dt   = start_dt + timedelta(days=1)

    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status.in_(["PAID", "DEFERRED", "PARTIAL_CANCELLED", "CANCELLED"]),
        models.Order.created_at >= start_dt,
        models.Order.created_at < end_dt,
    ).all()

    paid_orders      = [o for o in orders if o.payment_status in ["PAID", "PARTIAL_CANCELLED"]]
    deferred_orders  = [o for o in orders if o.payment_status == "DEFERRED"]
    cancelled_orders = [o for o in orders if o.payment_status == "CANCELLED"]

    total_revenue    = sum(o.paid_amount or o.total_price for o in paid_orders)
    deferred_revenue = sum(o.total_price for o in deferred_orders)
    cancelled_amount = sum(o.total_price for o in cancelled_orders)
    order_count      = len(paid_orders)

    # 결제수단별 분리
    card_revenue = 0
    cash_revenue = 0
    method_breakdown: dict = {}
    for o in paid_orders:
        m = (o.payment_method or "기타").lower()
        amt = o.paid_amount or o.total_price
        if m in ("card",):
            card_revenue += amt
        elif m in ("cash",):
            cash_revenue += amt
        method_breakdown.setdefault(m, {"count": 0, "revenue": 0})
        method_breakdown[m]["count"] += 1
        method_breakdown[m]["revenue"] += amt

    # 메뉴별 top10 스냅샷
    menu_data: dict = {}
    for o in paid_orders:
        for item in o.items:
            if item.is_cancelled:
                continue
            menu_data.setdefault(item.menu_name, {"count": 0, "revenue": 0})
            menu_data[item.menu_name]["count"] += item.quantity
            menu_data[item.menu_name]["revenue"] += item.price * item.quantity
    top_menus = sorted(
        [{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in menu_data.items()],
        key=lambda x: x["revenue"], reverse=True
    )[:10]

    snapshot = _json.dumps({
        "method_breakdown": method_breakdown,
        "top_menus": top_menus,
        "deferred_order_count": len(deferred_orders),
        "cancelled_count": len(cancelled_orders),
        "closing_hour": closing_hour,
    }, ensure_ascii=False)

    return {
        "total_revenue":    total_revenue,
        "order_count":      order_count,
        "card_revenue":     card_revenue,
        "cash_revenue":     cash_revenue,
        "deferred_revenue": deferred_revenue,
        "cancelled_amount": cancelled_amount,
        "cancelled_count":  len(cancelled_orders),
        "snapshot_json":    snapshot,
        "closing_hour":     closing_hour,
        "deferred_count":   len(deferred_orders),
    }


@router.get("/stores/{store_id}/daily-closing/today-summary")
def get_today_closing_summary(
    store_id: int,
    business_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """지정 영업일의 마감 요약 + 이미 마감됐는지 여부 반환."""
    verify_store_permission(db, current_user, store_id)

    existing = db.query(models.DailyClosing).filter(
        models.DailyClosing.store_id == store_id,
        models.DailyClosing.business_date == business_date,
    ).first()

    summary = _build_closing_summary(store_id, business_date, db)
    summary["is_closed"] = existing is not None
    if existing:
        summary["closing_id"]     = existing.id
        summary["closed_at"]      = existing.closed_at.isoformat() if existing.closed_at else None
        summary["closed_by_name"] = existing.closed_by.name if existing.closed_by else None
        summary["memo"]           = existing.memo
    return summary


@router.post("/stores/{store_id}/daily-closing", response_model=schemas.DailyClosingResponse)
def confirm_daily_closing(
    store_id: int,
    payload: schemas.DailyClosingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """영업일 마감 확정. 동일 날짜 중복 마감 불가."""
    verify_store_permission(db, current_user, store_id)

    existing = db.query(models.DailyClosing).filter(
        models.DailyClosing.store_id == store_id,
        models.DailyClosing.business_date == payload.business_date,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="해당 날짜는 이미 마감 처리되었습니다.")

    summary = _build_closing_summary(store_id, payload.business_date, db)

    closing = models.DailyClosing(
        store_id         = store_id,
        business_date    = payload.business_date,
        total_revenue    = summary["total_revenue"],
        order_count      = summary["order_count"],
        card_revenue     = summary["card_revenue"],
        cash_revenue     = summary["cash_revenue"],
        deferred_revenue = summary["deferred_revenue"],
        cancelled_amount = summary["cancelled_amount"],
        cancelled_count  = summary["cancelled_count"],
        memo             = payload.memo,
        closed_by_id     = current_user.id,
        snapshot_json    = summary["snapshot_json"],
    )
    db.add(closing)
    db.commit()
    db.refresh(closing)

    create_audit_log(
        db=db, user_id=current_user.id, action="DAILY_CLOSING",
        target_type="STORE", target_id=store_id,
        details=f"일마감 확정: [{payload.business_date}] 매출 {summary['total_revenue']:,}원",
    )

    result = schemas.DailyClosingResponse.model_validate(closing).model_dump()
    result["closed_by_name"] = closing.closed_by.name if closing.closed_by else None
    return result


@router.get("/stores/{store_id}/daily-closing", response_model=List[schemas.DailyClosingResponse])
def get_closing_history(
    store_id: int,
    limit: int = 60,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """마감 이력 최신순 반환."""
    verify_store_permission(db, current_user, store_id)

    closings = (
        db.query(models.DailyClosing)
        .filter(models.DailyClosing.store_id == store_id)
        .order_by(models.DailyClosing.business_date.desc())
        .limit(limit)
        .all()
    )
    result = []
    for c in closings:
        row = schemas.DailyClosingResponse.model_validate(c).model_dump()
        row["closed_by_name"] = c.closed_by.name if c.closed_by else None
        result.append(row)
    return result


@router.get("/stores/{store_id}/daily-closing/{closing_id}", response_model=schemas.DailyClosingResponse)
def get_closing_detail(
    store_id: int,
    closing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """특정 마감 상세 조회."""
    verify_store_permission(db, current_user, store_id)
    closing = db.query(models.DailyClosing).filter(
        models.DailyClosing.id == closing_id,
        models.DailyClosing.store_id == store_id,
    ).first()
    if not closing:
        raise HTTPException(status_code=404, detail="마감 기록을 찾을 수 없습니다.")
    result = schemas.DailyClosingResponse.model_validate(closing).model_dump()
    result["closed_by_name"] = closing.closed_by.name if closing.closed_by else None
    return result

# =========================================================
# 📊 매출 리포트 (점주용 A안 + 브랜드 관리자용 B안)
# =========================================================

from datetime import date as _date, timedelta as _timedelta

@router.get("/stores/{store_id}/reports/period")
def get_store_report(
    store_id: int,
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """점주용 기간별 매출 리포트 (daily_closings 기반)"""
    verify_store_permission(db, current_user, store_id)

    start = _date.fromisoformat(start_date)
    end   = _date.fromisoformat(end_date)

    closings = db.query(models.DailyClosing).filter(
        models.DailyClosing.store_id == store_id,
        models.DailyClosing.business_date >= start_date,
        models.DailyClosing.business_date <= end_date,
    ).order_by(models.DailyClosing.business_date).all()

    period_stats = []
    top_menus_map = {}

    for c in closings:
        period_stats.append({
            "date": c.business_date,
            "revenue": c.total_revenue,
            "order_count": c.order_count,
            "card": c.card_revenue,
            "cash": c.cash_revenue,
            "deferred": c.deferred_revenue,
            "cancelled_amount": c.cancelled_amount,
        })
        if c.snapshot_json:
            try:
                snap = json.loads(c.snapshot_json)
                for m in snap.get("top_menus", []):
                    key = m["name"]
                    if key not in top_menus_map:
                        top_menus_map[key] = {"name": key, "count": 0, "revenue": 0}
                    top_menus_map[key]["count"]   += m.get("count", 0)
                    top_menus_map[key]["revenue"] += m.get("revenue", 0)
            except Exception:
                pass

    top_menus = sorted(top_menus_map.values(), key=lambda x: x["revenue"], reverse=True)[:10]

    totals = {
        "revenue":          sum(s["revenue"]          for s in period_stats),
        "order_count":      sum(s["order_count"]      for s in period_stats),
        "card":             sum(s["card"]             for s in period_stats),
        "cash":             sum(s["cash"]             for s in period_stats),
        "deferred":         sum(s["deferred"]         for s in period_stats),
        "cancelled_amount": sum(s["cancelled_amount"] for s in period_stats),
        "closing_count":    len(closings),
    }

    return {"period_stats": period_stats, "totals": totals, "top_menus": top_menus}


@router.get("/brands/{brand_id}/reports/stores")
def get_brand_report(
    brand_id: int,
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """브랜드 관리자용 매장별 매출 비교 리포트"""
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
    if current_user.role not in ("SUPER_ADMIN", "BRAND_ADMIN", "GROUP_ADMIN"):
        if current_user.brand_id != brand_id:
            raise HTTPException(status_code=403, detail="권한이 없습니다.")

    stores = db.query(models.Store).filter(models.Store.brand_id == brand_id).all()

    store_stats = []
    for store in stores:
        closings = db.query(models.DailyClosing).filter(
            models.DailyClosing.store_id == store.id,
            models.DailyClosing.business_date >= start_date,
            models.DailyClosing.business_date <= end_date,
        ).all()
        store_stats.append({
            "store_id":      store.id,
            "store_name":    store.name,
            "revenue":       sum(c.total_revenue   for c in closings),
            "order_count":   sum(c.order_count     for c in closings),
            "card":          sum(c.card_revenue    for c in closings),
            "cash":          sum(c.cash_revenue    for c in closings),
            "deferred":      sum(c.deferred_revenue for c in closings),
            "closing_count": len(closings),
        })

    store_stats.sort(key=lambda x: x["revenue"], reverse=True)

    totals = {
        "revenue":     sum(s["revenue"]     for s in store_stats),
        "order_count": sum(s["order_count"] for s in store_stats),
    }

    return {
        "brand_name":  brand.name,
        "store_stats": store_stats,
        "totals":      totals,
    }
