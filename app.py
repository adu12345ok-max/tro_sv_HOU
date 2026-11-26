import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import (
    format_trieu,
    format_vnd,
    get_connection,
    hash_password,
    init_db,
    row_to_dict,
    verify_password,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TrọUni - Hệ thống tìm trọ & chung cư mini sinh viên")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("TROUNI_SECRET_KEY", "trouni-student-project-secret-key-2026"),
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["vnd"] = format_vnd
templates.env.filters["trieu"] = format_trieu

DISTRICTS = [
    "Hai Bà Trưng",
    "Cầu Giấy",
    "Đống Đa",
    "Thanh Xuân",
    "Hà Đông",
    "Bắc Từ Liêm",
    "Nam Từ Liêm",
    "Hoàng Mai",
    "Ba Đình",
    "Long Biên",
]

PROPERTY_TYPES = [
    "Phòng trọ",
    "Chung cư mini",
    "Ký túc xá tư nhân",
]

AMENITY_OPTIONS = [
    "Điều hòa",
    "Nóng lạnh",
    "Wi-Fi",
    "Thang máy",
    "Ban công",
    "Gác xép",
    "Máy giặt",
    "Tủ lạnh",
    "Bếp riêng",
    "Khóa vân tay",
    "Chỗ để xe",
    "Camera 24/7",
    "Không chung chủ",
]

IMAGE_PRESETS = {
    "Chung cư mini": "/static/img/room_mini.svg",
    "Phòng trọ": "/static/img/room_loft.svg",
    "Ký túc xá tư nhân": "/static/img/room_dorm.svg",
}


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def get_unread_chat_count(user_id: Optional[int]) -> int:
    if not user_id:
        return 0
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE (c.buyer_id = ? OR c.seller_id = ?)
              AND m.sender_id != ?
              AND m.is_read = 0
            """,
            (user_id, user_id, user_id),
        ).fetchone()
        return row["cnt"] if row else 0


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, phone, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        user = row_to_dict(row)
        if not user:
            return None
        unread = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE (c.buyer_id = ? OR c.seller_id = ?)
              AND m.sender_id != ?
              AND m.is_read = 0
            """,
            (user_id, user_id, user_id),
        ).fetchone()
        user["unread_chat_count"] = unread["cnt"] if unread else 0
        return user


def pop_flash(request: Request) -> Optional[Dict[str, str]]:
    return request.session.pop("flash", None)


def set_flash(request: Request, message: str, category: str = "success") -> None:
    request.session["flash"] = {"message": message, "category": category}


def get_user_favorite_ids(user_id: Optional[int]) -> List[int]:
    if not user_id:
        return []
    with get_connection() as conn:
        rows = conn.execute("SELECT listing_id FROM favorites WHERE user_id = ?", (user_id,)).fetchall()
        return [r["listing_id"] for r in rows]


def enrich_listing(row: Dict[str, Any], favorite_ids: List[int]) -> Dict[str, Any]:
    item = dict(row)
    item["amenities_list"] = [a.strip() for a in item.get("amenities", "").split(",") if a.strip()]
    item["is_favorite"] = item["id"] in favorite_ids
    return item


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    q: str = "",
    district: str = "",
    property_type: str = "",
    min_price: str = "",
    max_price: str = "",
    min_area: str = "",
    max_area: str = "",
    sort: str = "newest",
):
    user = get_current_user(request)
    favorite_ids = get_user_favorite_ids(user["id"] if user else None)

    query = """
        SELECT
            l.*,
            u.full_name AS landlord_name,
            (SELECT COUNT(*) FROM listings l2 WHERE l2.landlord_id = l.landlord_id AND l2.status = 'approved') AS landlord_listing_count
        FROM listings l
        JOIN users u ON l.landlord_id = u.id
        WHERE l.status = 'approved'
    """
    params: List[Any] = []

    if q.strip():
        query += " AND (l.title LIKE ? OR l.address LIKE ? OR l.description LIKE ? OR l.district LIKE ?)"
        like_q = f"%{q.strip()}%"
        params.extend([like_q, like_q, like_q, like_q])
    if district.strip():
        query += " AND l.district = ?"
        params.append(district.strip())
    if property_type.strip():
        query += " AND l.property_type = ?"
        params.append(property_type.strip())
    if min_price.strip().isdigit():
        query += " AND l.price >= ?"
        params.append(int(min_price.strip()))
    if max_price.strip().isdigit():
        query += " AND l.price <= ?"
        params.append(int(max_price.strip()))
    if min_area.strip().replace(".", "", 1).isdigit():
        query += " AND l.area >= ?"
        params.append(float(min_area.strip()))
    if max_area.strip().replace(".", "", 1).isdigit():
        query += " AND l.area <= ?"
        params.append(float(max_area.strip()))

    sort_map = {
        "newest": "l.id DESC",
        "price_asc": "l.price ASC, l.id DESC",
        "price_desc": "l.price DESC, l.id DESC",
        "area_desc": "l.area DESC, l.id DESC",
    }
    order_by = sort_map.get(sort, "l.id DESC")
    query += f" ORDER BY {order_by}"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        stats = {
            "approved_count": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'approved'").fetchone()[0],
            "pending_count": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'pending'").fetchone()[0],
            "landlord_count": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'landlord'").fetchone()[0],
            "renter_count": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'renter'").fetchone()[0],
        }

    listings = [enrich_listing(dict(r), favorite_ids) for r in rows]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "listings": listings,
            "stats": stats,
            "districts": DISTRICTS,
            "property_types": PROPERTY_TYPES,
            "filters": {
                "q": q,
                "district": district,
                "property_type": property_type,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "sort": sort if sort in sort_map else "newest",
            },
        },
    )


@app.get("/listing/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: int):
    user = get_current_user(request)
    favorite_ids = get_user_favorite_ids(user["id"] if user else None)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT l.*, u.full_name AS landlord_name, u.email AS landlord_email
            FROM listings l
            JOIN users u ON l.landlord_id = u.id
            WHERE l.id = ?
            """,
            (listing_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy tin đăng")

        listing = enrich_listing(dict(row), favorite_ids)

        # Chỉ hiển thị tin chưa duyệt cho chủ bài đăng hoặc admin
        if listing["status"] != "approved":
            if not user or (user["role"] != "admin" and user["id"] != listing["landlord_id"]):
                raise HTTPException(status_code=403, detail="Tin đăng đang chờ quản trị viên duyệt")

        related_rows = conn.execute(
            """
            SELECT l.*, u.full_name AS landlord_name
            FROM listings l
            JOIN users u ON l.landlord_id = u.id
            WHERE l.status = 'approved' AND l.id != ?
            ORDER BY (l.district = ?) DESC, l.id DESC
            LIMIT 3
            """,
            (listing_id, listing["district"]),
        ).fetchall()

    related = [enrich_listing(dict(r), favorite_ids) for r in related_rows]
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "listing": listing,
            "related": related,
        },
    )


@app.get("/auth", response_class=HTMLResponse)
def auth_page(request: Request, tab: str = "login"):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "user": None,
            "flash": pop_flash(request),
            "active_tab": tab if tab in ("login", "register") else "login",
        },
    )


@app.post("/register")
def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    role: str = Form("renter"),
):
    clean_role = role if role in ("renter", "landlord") else "renter"
    clean_email = email.strip().lower()

    if len(password) < 6:
        set_flash(request, "Mật khẩu cần tối thiểu 6 ký tự.", "error")
        return RedirectResponse(url="/auth?tab=register", status_code=303)

    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (clean_email,)).fetchone()
        if exists:
            set_flash(request, "Email này đã được đăng ký. Vui lòng đăng nhập.", "error")
            return RedirectResponse(url="/auth?tab=login", status_code=303)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = conn.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (full_name.strip(), clean_email, phone.strip(), hash_password(password), clean_role, now),
        )
        conn.commit()
        user_id = cur.lastrowid

    request.session["user_id"] = user_id
    role_label = "Chủ cho thuê" if clean_role == "landlord" else "Người tìm trọ"
    set_flash(request, f"Chào mừng {full_name.strip()}! Tài khoản {role_label} đã sẵn sàng.", "success")
    target = "/landlord/dashboard" if clean_role == "landlord" else "/"
    return RedirectResponse(url=target, status_code=303)


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    clean_email = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        set_flash(request, "Email hoặc mật khẩu chưa chính xác.", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    request.session["user_id"] = row["id"]
    set_flash(request, f"Đăng nhập thành công! Xin chào {row['full_name']}.", "success")

    if row["role"] == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if row["role"] == "landlord":
        return RedirectResponse(url="/landlord/dashboard", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    set_flash(request, "Bạn đã đăng xuất khỏi hệ thống.", "info")
    return RedirectResponse(url="/", status_code=303)


@app.get("/landlord/dashboard", response_class=HTMLResponse)
def landlord_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("landlord", "admin"):
        set_flash(request, "Vui lòng đăng nhập bằng tài khoản Chủ trọ để đăng tin.", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE landlord_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()

    listings = [enrich_listing(dict(r), []) for r in rows]
    summary = {
        "total": len(listings),
        "approved": sum(1 for item in listings if item["status"] == "approved"),
        "pending": sum(1 for item in listings if item["status"] == "pending"),
        "rejected": sum(1 for item in listings if item["status"] == "rejected"),
    }

    return templates.TemplateResponse(
        "landlord_dashboard.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "listings": listings,
            "summary": summary,
            "districts": DISTRICTS,
            "property_types": PROPERTY_TYPES,
            "amenity_options": AMENITY_OPTIONS,
        },
    )


@app.post("/landlord/listings/create")
def create_listing(
    request: Request,
    title: str = Form(...),
    property_type: str = Form(...),
    price: int = Form(...),
    area: float = Form(...),
    district: str = Form(...),
    address: str = Form(...),
    description: str = Form(...),
    contact_phone: str = Form(...),
    amenities: List[str] = Form(default=[]),
    image_style: str = Form(""),
):
    user = get_current_user(request)
    if not user or user["role"] not in ("landlord", "admin"):
        set_flash(request, "Bạn không có quyền đăng tin cho thuê.", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    valid_type = property_type if property_type in PROPERTY_TYPES else "Phòng trọ"
    allowed_images = {
        "/static/img/room_mini.svg",
        "/static/img/room_loft.svg",
        "/static/img/room_studio.svg",
        "/static/img/room_dorm.svg",
    }
    chosen_image = image_style if image_style in allowed_images else IMAGE_PRESETS.get(valid_type, "/static/img/room_studio.svg")
    amenities_str = ",".join(a.strip() for a in amenities if a.strip())
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Bài đăng của chủ trọ luôn ở trạng thái 'pending' chờ Admin duyệt
    initial_status = "approved" if user["role"] == "admin" else "pending"

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO listings (
                landlord_id, title, property_type, price, area, district, address,
                description, amenities, contact_phone, image_url, status, admin_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                title.strip(),
                valid_type,
                max(500000, price),
                max(8.0, area),
                district.strip(),
                address.strip(),
                description.strip(),
                amenities_str,
                contact_phone.strip(),
                chosen_image,
                initial_status,
                "",
                now,
            ),
        )
        conn.commit()

    if initial_status == "pending":
        set_flash(request, "Đã gửi tin đăng thành công! Bài viết đang chờ Admin duyệt hiển thị.", "success")
    else:
        set_flash(request, "Đã đăng bài thành công!", "success")
    return RedirectResponse(url="/landlord/dashboard", status_code=303)


@app.post("/landlord/listings/{listing_id}/delete")
def delete_own_listing(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    with get_connection() as conn:
        row = conn.execute("SELECT landlord_id FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not row:
            set_flash(request, "Tin đăng không tồn tại.", "error")
            return RedirectResponse(url="/landlord/dashboard", status_code=303)
        if user["role"] != "admin" and row["landlord_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Không có quyền xóa tin đăng này")
        conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        conn.commit()

    set_flash(request, "Đã xóa tin đăng.", "info")
    return RedirectResponse(url="/landlord/dashboard", status_code=303)


@app.get("/renter/favorites", response_class=HTMLResponse)
def renter_favorites(request: Request):
    user = get_current_user(request)
    if not user:
        set_flash(request, "Vui lòng đăng nhập để xem danh sách phòng đã lưu.", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT l.*, u.full_name AS landlord_name
            FROM favorites f
            JOIN listings l ON f.listing_id = l.id
            JOIN users u ON l.landlord_id = u.id
            WHERE f.user_id = ? AND l.status = 'approved'
            ORDER BY f.id DESC
            """,
            (user["id"],),
        ).fetchall()

    favorite_ids = [r["id"] for r in rows]
    listings = [enrich_listing(dict(r), favorite_ids) for r in rows]

    return templates.TemplateResponse(
        "renter_dashboard.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "listings": listings,
        },
    )


@app.post("/api/favorites/{listing_id}/toggle")
def toggle_favorite(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": False, "message": "Vui lòng đăng nhập để lưu phòng yêu thích."}, status_code=401)

    with get_connection() as conn:
        exists_listing = conn.execute("SELECT id FROM listings WHERE id = ? AND status = 'approved'", (listing_id,)).fetchone()
        if not exists_listing:
            return JSONResponse({"ok": False, "message": "Phòng không tồn tại."}, status_code=404)

        fav = conn.execute(
            "SELECT id FROM favorites WHERE user_id = ? AND listing_id = ?",
            (user["id"], listing_id),
        ).fetchone()

        if fav:
            conn.execute("DELETE FROM favorites WHERE id = ?", (fav["id"],))
            conn.commit()
            return JSONResponse({"ok": True, "favorited": False, "message": "Đã bỏ khỏi danh sách yêu thích."})

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "INSERT INTO favorites (user_id, listing_id, created_at) VALUES (?, ?, ?)",
            (user["id"], listing_id, now),
        )
        conn.commit()
        return JSONResponse({"ok": True, "favorited": True, "message": "Đã lưu vào danh sách yêu thích!"})


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, status: str = "all"):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        set_flash(request, "Khu vực này chỉ dành cho Quản trị viên (Admin Mode).", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    query = """
        SELECT l.*, u.full_name AS landlord_name, u.email AS landlord_email
        FROM listings l
        JOIN users u ON l.landlord_id = u.id
    """
    params: List[Any] = []
    if status in ("pending", "approved", "rejected"):
        query += " WHERE l.status = ?"
        params.append(status)
    query += " ORDER BY CASE l.status WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END, l.id DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        users_rows = conn.execute(
            "SELECT id, full_name, email, phone, role, created_at FROM users ORDER BY id DESC"
        ).fetchall()
        counts = {
            "all": conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
            "pending": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'pending'").fetchone()[0],
            "approved": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'approved'").fetchone()[0],
            "rejected": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'rejected'").fetchone()[0],
            "users": len(users_rows),
        }

    listings = [enrich_listing(dict(r), []) for r in rows]
    users_list = [dict(u) for u in users_rows]

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "listings": listings,
            "users_list": users_list,
            "counts": counts,
            "active_status": status,
        },
    )


@app.post("/api/admin/listings/{listing_id}/review")
def admin_review_listing(
    request: Request,
    listing_id: int,
    action: str = Form(...),
    admin_note: str = Form(""),
):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"ok": False, "message": "Không có quyền quản trị."}, status_code=403)

    if action not in ("approved", "rejected", "pending"):
        return JSONResponse({"ok": False, "message": "Trạng thái không hợp lệ."}, status_code=400)

    note = admin_note.strip()
    if action == "approved" and not note:
        note = "Đã duyệt hiển thị bởi Quản trị viên."
    elif action == "rejected" and not note:
        note = "Thông tin chưa đầy đủ, vui lòng bổ sung và gửi lại."

    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not exists:
            return JSONResponse({"ok": False, "message": "Không tìm thấy bài đăng."}, status_code=404)

        conn.execute(
            "UPDATE listings SET status = ?, admin_note = ? WHERE id = ?",
            (action, note, listing_id),
        )
        conn.commit()

        counts = {
            "all": conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
            "pending": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'pending'").fetchone()[0],
            "approved": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'approved'").fetchone()[0],
            "rejected": conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'rejected'").fetchone()[0],
        }

    return JSONResponse(
        {
            "ok": True,
            "listing_id": listing_id,
            "status": action,
            "admin_note": note,
            "counts": counts,
            "message": "Đã duyệt bài đăng!" if action == "approved" else "Đã từ chối bài đăng.",
        }
    )


@app.post("/api/admin/listings/{listing_id}/delete")
def admin_delete_listing(request: Request, listing_id: int):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"ok": False, "message": "Không có quyền quản trị."}, status_code=403)

    with get_connection() as conn:
        conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        conn.commit()
    return JSONResponse({"ok": True, "message": "Đã xóa vĩnh viễn bài đăng."})


# ============================================================
# CHAT VỚI NGƯỜI BÁN (CHỦ TRỌ) & HỘP THƯ TIN NHẮN
# ============================================================


def fetch_user_conversations(user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.listing_id,
                c.buyer_id,
                c.seller_id,
                c.updated_at,
                l.title AS listing_title,
                l.price AS listing_price,
                l.area AS listing_area,
                l.district AS listing_district,
                l.image_url AS listing_image,
                l.contact_phone AS listing_phone,
                CASE WHEN c.buyer_id = ? THEN seller.full_name ELSE buyer.full_name END AS partner_name,
                CASE WHEN c.buyer_id = ? THEN seller.role ELSE buyer.role END AS partner_role,
                CASE WHEN c.buyer_id = ? THEN seller.phone ELSE buyer.phone END AS partner_phone,
                (
                    SELECT m.content FROM messages m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.id DESC LIMIT 1
                ) AS last_message,
                (
                    SELECT m.created_at FROM messages m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.id DESC LIMIT 1
                ) AS last_message_at,
                (
                    SELECT COUNT(*) FROM messages m
                    WHERE m.conversation_id = c.id AND m.sender_id != ? AND m.is_read = 0
                ) AS unread_count
            FROM conversations c
            JOIN listings l ON c.listing_id = l.id
            JOIN users buyer ON c.buyer_id = buyer.id
            JOIN users seller ON c.seller_id = seller.id
            WHERE c.buyer_id = ? OR c.seller_id = ?
            ORDER BY c.updated_at DESC, c.id DESC
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id),
        ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["listing_price_text"] = format_trieu(item["listing_price"])
        result.append(item)
    return result


def get_or_create_conversation(listing_id: int, buyer_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        listing = conn.execute(
            "SELECT id, landlord_id, title FROM listings WHERE id = ?",
            (listing_id,),
        ).fetchone()
        if not listing:
            return None
        seller_id = listing["landlord_id"]
        if seller_id == buyer_id:
            return {"error": "self"}

        existing = conn.execute(
            """
            SELECT id FROM conversations
            WHERE listing_id = ? AND buyer_id = ? AND seller_id = ?
            """,
            (listing_id, buyer_id, seller_id),
        ).fetchone()
        if existing:
            return {"id": existing["id"]}

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = conn.execute(
            """
            INSERT INTO conversations (listing_id, buyer_id, seller_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (listing_id, buyer_id, seller_id, now, now),
        )
        conn.commit()
        return {"id": cur.lastrowid}


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, conv_id: Optional[int] = None, listing_id: Optional[int] = None, quick: str = ""):
    user = get_current_user(request)
    if not user:
        set_flash(request, "Vui lòng đăng nhập để chat trực tiếp với người bán.", "error")
        return RedirectResponse(url="/auth?tab=login", status_code=303)

    if listing_id is not None:
        res = get_or_create_conversation(listing_id, user["id"])
        if not res:
            set_flash(request, "Tin đăng không tồn tại.", "error")
            return RedirectResponse(url="/chat", status_code=303)
        if res.get("error") == "self":
            set_flash(request, "Đây là tin đăng của chính bạn — hãy xem tin nhắn từ người thuê tại đây.", "info")
            return RedirectResponse(url="/chat", status_code=303)
        target_conv_id = res["id"]
        if quick.strip():
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO messages (conversation_id, sender_id, content, is_read, created_at) VALUES (?, ?, ?, 0, ?)",
                    (target_conv_id, user["id"], quick.strip(), now),
                )
                conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, target_conv_id))
                conn.commit()
        return RedirectResponse(url=f"/chat?conv_id={target_conv_id}", status_code=303)

    conversations = fetch_user_conversations(user["id"])
    active_conv_id = conv_id if conv_id else (conversations[0]["id"] if conversations else None)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user": user,
            "flash": pop_flash(request),
            "conversations": conversations,
            "active_conv_id": active_conv_id,
        },
    )


@app.post("/api/chat/start")
def api_chat_start(
    request: Request,
    listing_id: int = Form(...),
    message: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": False, "message": "Vui lòng đăng nhập để nhắn tin với người bán."}, status_code=401)

    res = get_or_create_conversation(listing_id, user["id"])
    if not res:
        return JSONResponse({"ok": False, "message": "Không tìm thấy tin đăng."}, status_code=404)
    if res.get("error") == "self":
        return JSONResponse({"ok": False, "message": "Bạn không thể tự nhắn tin cho tin đăng của mình."}, status_code=400)

    conv_id = res["id"]
    if message.strip():
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, sender_id, content, is_read, created_at) VALUES (?, ?, ?, 0, ?)",
                (conv_id, user["id"], message.strip(), now),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
            conn.commit()

    return JSONResponse({"ok": True, "conversation_id": conv_id})


@app.get("/api/chat/conversations")
def api_chat_conversations(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": False, "message": "Chưa đăng nhập."}, status_code=401)
    conversations = fetch_user_conversations(user["id"])
    return JSONResponse(
        {
            "ok": True,
            "conversations": conversations,
            "unread_total": sum(c["unread_count"] for c in conversations),
        }
    )


@app.get("/api/chat/conversations/{conv_id}/messages")
def api_chat_messages(request: Request, conv_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": False, "message": "Chưa đăng nhập."}, status_code=401)

    with get_connection() as conn:
        conv = conn.execute(
            """
            SELECT
                c.*,
                l.title AS listing_title,
                l.price AS listing_price,
                l.area AS listing_area,
                l.district AS listing_district,
                l.address AS listing_address,
                l.image_url AS listing_image,
                l.contact_phone AS listing_phone,
                CASE WHEN c.buyer_id = ? THEN seller.full_name ELSE buyer.full_name END AS partner_name,
                CASE WHEN c.buyer_id = ? THEN seller.role ELSE buyer.role END AS partner_role,
                CASE WHEN c.buyer_id = ? THEN seller.phone ELSE buyer.phone END AS partner_phone
            FROM conversations c
            JOIN listings l ON c.listing_id = l.id
            JOIN users buyer ON c.buyer_id = buyer.id
            JOIN users seller ON c.seller_id = seller.id
            WHERE c.id = ? AND (c.buyer_id = ? OR c.seller_id = ?)
            """,
            (user["id"], user["id"], user["id"], conv_id, user["id"], user["id"]),
        ).fetchone()
        if not conv:
            return JSONResponse({"ok": False, "message": "Không tìm thấy cuộc trò chuyện."}, status_code=404)

        conn.execute(
            "UPDATE messages SET is_read = 1 WHERE conversation_id = ? AND sender_id != ? AND is_read = 0",
            (conv_id, user["id"]),
        )
        conn.commit()

        msgs = conn.execute(
            """
            SELECT m.id, m.sender_id, m.content, m.is_read, m.created_at, u.full_name AS sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.conversation_id = ?
            ORDER BY m.id ASC
            """,
            (conv_id,),
        ).fetchall()

    conv_dict = dict(conv)
    conv_dict["listing_price_text"] = format_trieu(conv_dict["listing_price"])
    return JSONResponse(
        {
            "ok": True,
            "conversation": conv_dict,
            "current_user_id": user["id"],
            "messages": [dict(m) for m in msgs],
            "unread_total": get_unread_chat_count(user["id"]),
        }
    )


@app.post("/api/chat/conversations/{conv_id}/messages")
def api_chat_send_message(request: Request, conv_id: int, content: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": False, "message": "Chưa đăng nhập."}, status_code=401)

    clean_content = content.strip()
    if not clean_content:
        return JSONResponse({"ok": False, "message": "Nội dung tin nhắn không được để trống."}, status_code=400)
    if len(clean_content) > 1500:
        clean_content = clean_content[:1500]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_connection() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND (buyer_id = ? OR seller_id = ?)",
            (conv_id, user["id"], user["id"]),
        ).fetchone()
        if not conv:
            return JSONResponse({"ok": False, "message": "Không tìm thấy cuộc trò chuyện."}, status_code=404)

        cur = conn.execute(
            "INSERT INTO messages (conversation_id, sender_id, content, is_read, created_at) VALUES (?, ?, ?, 0, ?)",
            (conv_id, user["id"], clean_content, now),
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        conn.commit()
        msg_id = cur.lastrowid

    return JSONResponse(
        {
            "ok": True,
            "message": {
                "id": msg_id,
                "sender_id": user["id"],
                "sender_name": user["full_name"],
                "content": clean_content,
                "is_read": 0,
                "created_at": now,
            },
        }
    )


@app.get("/api/chat/unread")
def api_chat_unread(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"ok": True, "unread_count": 0})
    return JSONResponse({"ok": True, "unread_count": user["unread_chat_count"]})


if __name__ == "__main__":
    init_db()
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
