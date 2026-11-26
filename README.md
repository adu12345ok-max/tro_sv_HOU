# TrọUni — Website Tìm Trọ & Chung Cư Mini Cho Sinh Viên (Python FastAPI)

Dự án đồ án học tập (phi thương mại) xây dựng nền tảng tìm kiếm phòng trọ, chung cư mini và ký túc xá tư nhân dành cho sinh viên.

## Tính năng chính
- **Giao diện hiện đại & Animation mượt**: Hiệu ứng chuyển động nền organic, scroll-reveal theo thứ tự, hiệu ứng nâng thẻ phòng (card lift), micro-animation nút lưu yêu thích, và thông báo toast tức thì.
- **Hệ thống Đăng nhập & Đăng ký chọn vai trò**:
  - **Người tìm trọ (Sinh viên)**: Tìm kiếm, lọc phòng theo quận/loại hình/mức giá, xem chi tiết, lưu phòng yêu thích.
  - **Chủ cho thuê (Chủ trọ)**: Đăng tin phòng trọ/chung cư mini mới, theo dõi trạng thái duyệt (`Chờ duyệt`, `Đã duyệt`, `Bị từ chối`), xem ghi chú từ Admin, xóa bài.
- **Admin Mode (Chế độ Quản trị viên)**:
  - Hàng đợi duyệt bài đăng (`Chờ duyệt` -> `Duyệt hiển thị` hoặc `Từ chối kèm lý do`).
  - Cập nhật trạng thái mượt mà không cần tải lại trang (AJAX), quản lý danh sách người dùng và bài đăng.
- **Cơ sở dữ liệu SQLite tích hợp sẵn**: Tự động khởi tạo file `tro_sinh_vien.db` cùng dữ liệu mẫu ngay khi chạy lần đầu.

## Tài khoản Demo có sẵn
| Vai trò | Email | Mật khẩu |
| :--- | :--- | :--- |
| **Admin (Duyệt bài)** | `admin@trosv.edu.vn` | `Admin@123` |
| **Chủ trọ (Đăng cho thuê)** | `chutro@trosv.edu.vn` | `Chutro@123` |
| **Sinh viên (Tìm trọ)** | `sinhvien@trosv.edu.vn` | `Sinhvien@123` |

## Cách chạy trên Visual Studio / VS Code
1. Giải nén thư mục dự án và mở thư mục `tro_sinh_vien_app` trong **Visual Studio** (chọn *Open a local folder*) hoặc **Visual Studio Code**.
2. Mở Terminal tại thư mục dự án và cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   ```
3. Khởi chạy server:
   ```bash
   python app.py
   ```
4. Mở trình duyệt và truy cập: `http://127.0.0.1:8000`

## Cấu trúc thư mục
```text
tro_sinh_vien_app/
├── app.py                  # Backend FastAPI (Routes, Auth, Phân quyền, API)
├── database.py             # Khởi tạo SQLite, băm mật khẩu PBKDF2, dữ liệu mẫu
├── requirements.txt        # Thư viện Python cần cài
├── templates/              # Giao diện Jinja2 HTML
│   ├── base.html
│   ├── index.html
│   ├── detail.html
│   ├── auth.html
│   ├── landlord_dashboard.html
│   ├── renter_dashboard.html
│   └── admin_dashboard.html
└── static/
    ├── css/style.css       # Hệ thống thiết kế & Keyframe Animations
    ├── js/main.js          # Scroll reveal, AJAX Favorite & Admin Review
    └── img/*.svg           # Ảnh minh họa kiến trúc phòng chạy offline
```
