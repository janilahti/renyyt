# Renyyt — hướng dẫn nhanh

Renyyt hiển thị ngày thu gom rác sắp tới từ dịch vụ Oma jätehuolto của Renyy (Pirkanmaan Jätehuolto). Đây là ứng dụng không chính thức.

Dịch vụ: <https://renyyt.fi/>. Để tự lưu trữ, cần Python 3.8 trở lên: giải nén gói phát hành, chạy `python3 run.py` trong thư mục đó rồi mở <http://127.0.0.1:8787>.

## Cách dùng cơ bản

- Chọn ngôn ngữ, nhập mã khách hàng và mật khẩu Oma jätehuolto, rồi nhấn **Tải lịch thu gom**.
- **Thùng rác** chọn các thùng được hiển thị. **Sắp xếp → Thứ tự tùy chỉnh** cho phép dùng mũi tên hoặc kéo thả trong chế độ thường. **Thu gọn** giữ thứ tự nhưng ẩn công cụ sắp xếp.
- Xuất các lần thu gom tiếp theo thành lịch `.ics`. **Chế độ nhúng** chỉ hiển thị thông tin thu gom. Cài đặt, phản hồi và nhắc nhở phụ thuộc vào cấu hình máy chủ và trình duyệt.

Lưu thông tin đăng nhập là tùy chọn. Dữ liệu được làm rối trong trình duyệt không phải mã hóa an toàn; không lưu trên thiết bị dùng chung và giữ bí mật các liên kết nhúng chứa thông tin đăng nhập. Nhắc nhở dựa trên lần tải thành công gần nhất của trình duyệt. Dữ liệu cũ đã lưu được đánh dấu là lỗi thời.

Xem thêm: [hướng dẫn đầy đủ bằng tiếng Phần Lan](README.md), [cài đặt và cấu hình bằng tiếng Phần Lan](TECHNICAL.md), [API bằng tiếng Phần Lan](API.md), [thay đổi bằng tiếng Anh](CHANGELOG.md), [kiểm thử bằng tiếng Anh](https://github.com/janilahti/renyyt/blob/main/TESTING.md).
