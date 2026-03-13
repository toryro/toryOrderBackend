from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

# 상위 폴더의 모듈을 가져오기 위한 임포트
import models
import schemas
import crud
import dependencies
from database import get_db

# utils.py에 분리해둔 공통 함수들 가져오기 (사전에 utils.py를 만드셨다는 전제)
from utils import verify_store_permission, create_audit_log

# ✨ 라우터 생성 (태그를 달아두면 Swagger /docs 문서에서 깔끔하게 분류됩니다)
router = APIRouter(tags=["Menus & Options"])

# =========================================================
# 📂 카테고리 (Category) 관리
# =========================================================

@router.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.patch("/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_category(category_id: int, category_update: schemas.CategoryUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category: 
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, category.store_id)
    
    for key, value in category_update.dict(exclude_unset=True).items(): 
        setattr(category, key, value)
    
    db.commit()
    db.refresh(category)
    return category

@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category: raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, category.store_id)
    
    db.query(models.Menu).filter(models.Menu.category_id == category_id).delete()
    db.delete(category)
    db.commit()
    return {"message": "카테고리가 삭제되었습니다."}


# =========================================================
# 🍽️ 메뉴 (Menu) 관리
# =========================================================

@router.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first() 
    if not category: raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, category.store_id)
    
    db_menu = models.Menu(**menu.dict(exclude={"options"}), category_id=category_id, store_id=category.store_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    create_audit_log(db=db, user_id=current_user.id, action="CREATE_MENU", target_type="MENU", target_id=db_menu.id, details=f"새 메뉴 생성: [{db_menu.name}]")
    return db_menu

@router.patch("/menus/{menu_id}", response_model=schemas.MenuResponse)
def update_menu(menu_id: int, menu_update: schemas.MenuUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    
    if current_user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
        if menu.is_price_fixed and menu_update.price is not None and menu_update.price != menu.price:
            raise HTTPException(status_code=403, detail="본사에서 강제 고정한 메뉴이므로 점주가 임의로 가격을 변경할 수 없습니다.")
            
    for key, value in menu_update.dict(exclude_unset=True).items(): 
        setattr(menu, key, value)
        
    db.commit()
    db.refresh(menu)
    return menu

@router.delete("/menus/{menu_id}")
def delete_menu(menu_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    
    db.delete(menu)
    db.commit()
    return {"message": "메뉴가 삭제되었습니다."}


# =========================================================
# 📚 옵션 라이브러리 (Option Group & Options) 관리
# =========================================================

@router.get("/stores/{store_id}/option-groups/", response_model=List[schemas.OptionGroupResponse])
def get_option_groups(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    return db.query(models.OptionGroup).filter(models.OptionGroup.store_id == store_id).order_by(models.OptionGroup.order_index).all()

@router.post("/stores/{store_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_standalone_option_group(store_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    db_group = models.OptionGroup(store_id=store_id, name=group.name, is_single_select=group.is_single_select, is_required=group.is_required, max_select=group.max_select, order_index=group.order_index)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.patch("/option-groups/{group_id}", response_model=schemas.OptionGroupResponse)
def update_option_group(group_id: int, group_update: schemas.OptionGroupUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="옵션 그룹을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    
    for key, value in group_update.dict(exclude_unset=True).items(): 
        setattr(group, key, value)
        
    db.commit()
    db.refresh(group)
    return group

@router.delete("/option-groups/{group_id}")
def delete_option_group(group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    
    db.query(models.Option).filter(models.Option.group_id == group_id).delete()
    db.query(models.MenuOptionLink).filter(models.MenuOptionLink.option_group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return {"message": "삭제되었습니다."}

@router.post("/option-groups/{group_id}/options/", response_model=schemas.OptionResponse)
def create_option_for_group(group_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    return crud.create_option(db=db, option=option, group_id=group_id, store_id=group.store_id)

@router.patch("/options/{option_id}", response_model=schemas.OptionResponse)
def update_option(option_id: int, opt_update: schemas.OptionUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt: raise HTTPException(status_code=404, detail="옵션을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, opt.store_id)
    
    for key, value in opt_update.dict(exclude_unset=True).items(): 
        setattr(opt, key, value)
        
    db.commit()
    db.refresh(opt)
    return opt

@router.delete("/options/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, opt.store_id)
    db.delete(opt)
    db.commit()
    return {"message": "삭제되었습니다."}


# =========================================================
# 🔗 메뉴 - 옵션 그룹 연결 (Link/Unlink/Reorder)
# =========================================================

# (이전 코드와의 호환성을 위해 유지되는 레거시 옵션 그룹 생성)
@router.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(menu_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    return crud.create_option_group(db=db, group=group, menu_id=menu_id, store_id=menu.store_id)

@router.post("/menus/{menu_id}/link-option-group/{group_id}")
def link_option_group_to_menu(menu_id: int, group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    
    if not db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first():
        last_link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id).order_by(models.MenuOptionLink.order_index.desc()).first()
        db.add(models.MenuOptionLink(menu_id=menu_id, option_group_id=group_id, order_index=(last_link.order_index + 1) if last_link else 1))
        db.commit()
    return {"message": "연결 완료"}

@router.delete("/menus/{menu_id}/option-groups/{group_id}")
def unlink_option_group_from_menu(menu_id: int, group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    
    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        db.delete(link)
        db.commit()
    return {"message": "연결 해제 완료"}

class ReorderRequest(BaseModel):
    order_index: int

@router.patch("/menus/{menu_id}/option-groups/{group_id}/reorder")
def reorder_menu_option_group(menu_id: int, group_id: int, req: ReorderRequest, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    
    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        link.order_index = req.order_index
        db.commit()
    return {"message": "순서 변경 완료"}