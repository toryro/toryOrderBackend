from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# 프로젝트 내부 모듈
import models
import schemas
import crud
import dependencies
from database import get_db

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
        
    for key, value in store_update.dict(exclude_unset=True).items(): 
        setattr(store, key, value)
        
    db.commit()
    db.refresh(store)
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
        models.Order.payment_status == "PAID", 
        models.Order.created_at >= f"{start_date} 00:00:00", 
        models.Order.created_at <= f"{end_date} 23:59:59"
    ).all()
    
    total_rev = sum(o.total_price for o in orders)

    store_data = {
        s.id: {
            "name": s.name, "brand_name": s.brand.name if s.brand else "독립 매장", 
            "region": s.region or "미지정", "is_direct_manage": s.is_direct_manage, 
            "rev": 0, "cnt": 0, "r_type": s.royalty_type or "PERCENTAGE", "r_amount": s.royalty_amount or 0.0
        } for s in stores
    }
    
    for o in orders:
        if o.store_id in store_data:
            store_data[o.store_id]["rev"] += o.total_price
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
    verify_store_permission(db, current_user, store_id)
    
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id, 
        models.Order.payment_status == "PAID", 
        models.Order.created_at >= f"{start_date} 00:00:00", 
        models.Order.created_at <= f"{end_date} 23:59:59"
    ).all()
    
    total_revenue = sum(o.total_price for o in orders)
    order_count = len(orders)
    
    menu_data, hourly_data, daily_data, monthly_data = {}, {f"{i:02d}": 0 for i in range(24)}, {}, {}

    for order in orders:
        try:
            d_part, t_part = str(order.created_at).split(" ")
            order_hour, order_month = t_part.split(":")[0], d_part[:7]
            hourly_data[order_hour] += order.total_price
            
            if d_part not in daily_data: 
                daily_data[d_part] = {"sales": 0, "count": 0}
            daily_data[d_part]["sales"] += order.total_price
            daily_data[d_part]["count"] += 1
            
            if order_month not in monthly_data: 
                monthly_data[order_month] = {"sales": 0, "count": 0}
            monthly_data[order_month]["sales"] += order.total_price
            monthly_data[order_month]["count"] += 1
            
            for item in order.items:
                if item.menu_name not in menu_data: 
                    menu_data[item.menu_name] = {"count": 0, "revenue": 0}
                menu_data[item.menu_name]["count"] += item.quantity
                menu_data[item.menu_name]["revenue"] += (item.price * item.quantity)
        except: 
            pass

    menu_stats = sorted([{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in menu_data.items()], key=lambda x: x["revenue"], reverse=True)
    
    return {
        "total_revenue": total_revenue, 
        "order_count": order_count, 
        "average_order_value": int(total_revenue / order_count) if order_count > 0 else 0,
        "menu_stats": menu_stats, 
        "hourly_stats": [{"hour": k, "sales": v} for k, v in hourly_data.items()],
        "daily_stats": [{"date": k, "sales": v["sales"], "count": v["count"]} for k, v in sorted(daily_data.items(), reverse=True)],
        "monthly_stats": [{"month": k, "sales": v["sales"], "count": v["count"]} for k, v in sorted(monthly_data.items(), reverse=True)]
    }