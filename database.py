import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tro_sinh_vien.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hex_hash = stored_hash.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return hmac.compare_digest(dk.hex(), hex_hash)


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('renter', 'landlord', 'admin')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                landlord_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                property_type TEXT NOT NULL CHECK(property_type IN ('Phòng trọ', 'Chung cư mini', 'Ký túc xá tư nhân')),
                price INTEGER NOT NULL,
                area REAL NOT NULL,
                district TEXT NOT NULL,
                address TEXT NOT NULL,
                description TEXT NOT NULL,
                amenities TEXT NOT NULL DEFAULT '',
                contact_phone TEXT NOT NULL,
                image_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                admin_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (landlord_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, listing_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(listing_id, buyer_id, seller_id),
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
                FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

    seed_demo_data()
    seed_demo_chat()


def seed_demo_data() -> None:
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        if existing > 0:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        users = [
            ("Quản trị viên TrọUni", "admin@trosv.edu.vn", "0901000001", hash_password("Admin@123"), "admin", now),
            ("Nguyễn Minh Tuấn (Chủ trọ)", "chutro@trosv.edu.vn", "0912345678", hash_password("Chutro@123"), "landlord", now),
            ("Trần Thu Hà (Chủ CCMN)", "thuha.ccmn@trosv.edu.vn", "0987654321", hash_password("Chutro@123"), "landlord", now),
            ("Lê Hoàng Nam (Sinh viên)", "sinhvien@trosv.edu.vn", "0933445566", hash_password("Sinhvien@123"), "renter", now),
        ]
        conn.executemany(
            "INSERT INTO users (full_name, email, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            users,
        )

        landlord_1 = conn.execute("SELECT id FROM users WHERE email = ?", ("chutro@trosv.edu.vn",)).fetchone()["id"]
        landlord_2 = conn.execute("SELECT id FROM users WHERE email = ?", ("thuha.ccmn@trosv.edu.vn",)).fetchone()["id"]
        renter_1 = conn.execute("SELECT id FROM users WHERE email = ?", ("sinhvien@trosv.edu.vn",)).fetchone()["id"]

        listings = [
            (
                landlord_1,
                "Chung cư mini full nội thất gần ĐH Bách Khoa - Ban công thoáng",
                "Chung cư mini",
                4200000,
                28.0,
                "Hai Bà Trưng",
                "Ngõ 40 Tạ Quang Bửu, Hai Bà Trưng, Hà Nội",
                "Phòng mới sơn sửa, có thang máy, khóa vân tay 2 lớp, giờ giấc tự do không chung chủ. Cách cổng Parabol ĐH Bách Khoa chỉ 3 phút đi bộ, xung quanh đầy đủ quán ăn sinh viên.",
                "Điều hòa,Nóng lạnh,Thang máy,Máy giặt,Khóa vân tay,Ban công",
                "0912345678",
                "/static/img/room_mini.svg",
                "approved",
                "Đã kiểm tra thông tin hợp lệ.",
                now,
            ),
            (
                landlord_2,
                "Phòng trọ có gác xép sáng đẹp gần ĐH Quốc Gia & Sư Phạm",
                "Phòng trọ",
                2800000,
                22.0,
                "Cầu Giấy",
                "Ngõ 165 Xuân Thủy, Cầu Giấy, Hà Nội",
                "Phòng có gác xép cao ráo đứng thoải mái, cửa sổ lớn đón nắng tự nhiên. Khu dân trí cao, để xe tầng 1 miễn phí có camera an ninh 24/7.",
                "Gác xép,Điều hòa,Nóng lạnh,Wi-Fi,Chỗ để xe,Camera 24/7",
                "0987654321",
                "/static/img/room_loft.svg",
                "approved",
                "Thông tin đầy đủ, giá phù hợp sinh viên.",
                now,
            ),
            (
                landlord_1,
                "Studio chung cư mini phong cách tối giản gần ĐH Kinh Tế Quốc Dân",
                "Chung cư mini",
                4600000,
                30.0,
                "Hai Bà Trưng",
                "Ngõ 207 Giải Phóng, Hai Bà Trưng, Hà Nội",
                "Thiết kế hiện đại tông gỗ ấm, có kệ bếp từ riêng, tủ lạnh 180L và máy giặt chung sân thượng. Phù hợp ở 2 bạn sinh viên chia tiền rất tiết kiệm.",
                "Điều hòa,Nóng lạnh,Tủ lạnh,Bếp riêng,Thang máy,Ban công",
                "0912345678",
                "/static/img/room_studio.svg",
                "approved",
                "Đã xác minh chủ nhà.",
                now,
            ),
            (
                landlord_2,
                "Phòng trọ khép kín giá mềm khu Thanh Xuân - Gần ĐH Khoa Học Tự Nhiên",
                "Phòng trọ",
                2500000,
                19.0,
                "Thanh Xuân",
                "Ngõ 328 Nguyễn Trãi, Thanh Xuân, Hà Nội",
                "Phòng sạch sẽ, khép kín, điện nước tính theo giá sinh viên minh bạch. Gần trạm xe buýt và ga đường sắt trên cao Cát Linh - Hà Đông.",
                "Điều hòa,Nóng lạnh,Wi-Fi,Chỗ để xe,Không chung chủ",
                "0987654321",
                "/static/img/room_loft.svg",
                "approved",
                "Hợp lệ.",
                now,
            ),
            (
                landlord_2,
                "Ký túc xá tư nhân cao cấp giường hộp riêng tư - Đống Đa",
                "Ký túc xá tư nhân",
                1650000,
                16.0,
                "Đống Đa",
                "Ngõ 119 Hồ Đắc Di, Đống Đa, Hà Nội",
                "Mô hình sleepbox sinh viên có rèm che riêng tư, tủ đồ cá nhân có khóa, khu học tập chung yên tĩnh và dịch vụ dọn vệ sinh 2 lần/tuần.",
                "Điều hòa,Wi-Fi,Máy giặt,Bàn học,Camera 24/7,Bao điện nước",
                "0987654321",
                "/static/img/room_dorm.svg",
                "approved",
                "Hợp lệ.",
                now,
            ),
            (
                landlord_1,
                "Chung cư mini 1 ngủ riêng biệt gần ĐH Công Nghiệp Hà Nội",
                "Chung cư mini",
                3600000,
                26.0,
                "Bắc Từ Liêm",
                "Đường Cầu Diễn, Bắc Từ Liêm, Hà Nội",
                "Tách biệt khu nấu ăn và khu ngủ, có cửa sổ thoáng không mùi thức ăn. Phù hợp nhóm 2-3 bạn sinh viên ở lâu dài.",
                "Điều hòa,Nóng lạnh,Bếp riêng,Thang máy,Chỗ để xe",
                "0912345678",
                "/static/img/room_mini.svg",
                "approved",
                "Hợp lệ.",
                now,
            ),
            (
                landlord_1,
                "[Chờ duyệt] Phòng trọ mới xây full đồ gần Học viện Bưu Chính Viễn Thông",
                "Phòng trọ",
                3100000,
                24.0,
                "Hà Đông",
                "Ngõ 12 Trần Phú, Hà Đông, Hà Nội",
                "Nhà mới hoàn thiện tháng này, nội thất mới 100%, có sẵn giường tủ, bàn học và máy giặt tầng thượng. Đang chờ quản trị viên xét duyệt hiển thị.",
                "Điều hòa,Nóng lạnh,Giường tủ,Wi-Fi,Khóa vân tay",
                "0912345678",
                "/static/img/room_studio.svg",
                "pending",
                "",
                now,
            ),
            (
                landlord_2,
                "[Chờ duyệt] Chung cư mini có ban công view hồ khu Mỹ Đình",
                "Chung cư mini",
                4400000,
                29.0,
                "Nam Từ Liêm",
                "Phố Đình Thôn, Nam Từ Liêm, Hà Nội",
                "Phòng rộng thoáng, nhiều ánh sáng tự nhiên, an ninh vân tay, gần ĐH Thương Mại và bến xe Mỹ Đình. Đang chờ admin duyệt bài.",
                "Điều hòa,Nóng lạnh,Ban công,Thang máy,Tủ lạnh,Camera 24/7",
                "0987654321",
                "/static/img/room_mini.svg",
                "pending",
                "",
                now,
            ),
        ]

        conn.executemany(
            """
            INSERT INTO listings (
                landlord_id, title, property_type, price, area, district, address,
                description, amenities, contact_phone, image_url, status, admin_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            listings,
        )

        # Pre-save 2 favorite listings for demo student
        conn.execute(
            "INSERT INTO favorites (user_id, listing_id, created_at) VALUES (?, ?, ?)",
            (renter_1, 1, now),
        )
        conn.execute(
            "INSERT INTO favorites (user_id, listing_id, created_at) VALUES (?, ?, ?)",
            (renter_1, 2, now),
        )
        conn.commit()


def seed_demo_chat() -> None:
    with get_connection() as conn:
        existing_conv = conn.execute("SELECT COUNT(*) AS cnt FROM conversations").fetchone()["cnt"]
        if existing_conv > 0:
            return

        renter = conn.execute("SELECT id FROM users WHERE email = ?", ("sinhvien@trosv.edu.vn",)).fetchone()
        landlord = conn.execute("SELECT id FROM users WHERE email = ?", ("chutro@trosv.edu.vn",)).fetchone()
        listing = conn.execute(
            "SELECT id, landlord_id FROM listings WHERE status = 'approved' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if not renter or not landlord or not listing:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = conn.execute(
            """
            INSERT INTO conversations (listing_id, buyer_id, seller_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (listing["id"], renter["id"], listing["landlord_id"], now, now),
        )
        conv_id = cur.lastrowid
        demo_msgs = [
            (conv_id, renter["id"], "Chào anh/chị, phòng này hiện còn trống không ạ? Em là sinh viên Bách Khoa muốn qua xem phòng.", 1, now),
            (conv_id, listing["landlord_id"], "Chào em, phòng vẫn còn trống nhé! Em có thể qua xem phòng từ 17h hôm nay hoặc cuối tuần đều được.", 0, now),
        ]
        conn.executemany(
            "INSERT INTO messages (conversation_id, sender_id, content, is_read, created_at) VALUES (?, ?, ?, ?, ?)",
            demo_msgs,
        )
        conn.commit()


def format_vnd(amount: int) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " đ/tháng"


def format_trieu(amount: int) -> str:
    if amount >= 1_000_000:
        val = amount / 1_000_000
        if val.is_integer():
            return f"{int(val)} triệu/tháng"
        text = f"{val:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} triệu/tháng"
    return f"{amount:,.0f}".replace(",", ".") + " đ/tháng"


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None
