# Kiểm tra bản 0.3 — 25/10/2026

- 46 kiểm thử Python đã qua trên Windows; kiểm tra cú pháp JavaScript đã qua.
- Kiểm tra HTTP thật qua localhost: phục vụ tài nguyên, chặn Host giả, Origin khác, thiếu token, đường dẫn lạ và lệnh ngoài allowlist.
- Mô phỏng TV: giữ gói đã tắt từ trước; khôi phục đúng trạng thái default/enabled; lỗi giữa các gói; lỗi cài/đổi Home; nhật ký ghi trước thay đổi; khôi phục sau mất mạng, mở lại ứng dụng và thay IP; từ chối TV khác tại IP cũ; hết giờ thử; xác nhận Giữ; kiểm tra sức khỏe thất bại; khóa tệp tạm Windows.
- Bổ sung đo CPU/RAM/dung lượng trống, không thay đổi TV; tùy chọn hiệu ứng 0,5 lần lưu và khôi phục chính xác giá trị gốc hoặc khóa chưa được đặt. Đã thử thao tác đo và hoàn tác hiệu ứng qua giao diện với TV mô phỏng.
- Hồ sơ: 268 hồ sơ, 79 hãng, lấy từ commit upstream được khóa trong downloads.json. 49 quy tắc thay đổi có đường dẫn nguồn; dữ liệu hồ sơ không được thực thi như script. Cùng hãng không đủ để coi là khớp model.
- Bộ khởi động thực tế đã giải nén và chạy Python/ADB portable. Lần chạy thứ hai trả về địa chỉ phiên đang chạy, không tạo phiên điều khiển thứ hai trong cùng thư mục.
- Launcher upstream đã build thành công bằng toolchain portable: JDK 17, Android SDK 34, Build Tools 34.0.0, Gradle 8.9. APK được tạo tại máy, không đóng gói vào repository hoặc ZIP phát hành.
- Giao diện đã được kiểm tra ở khung hẹp và desktop 1280 px; không ghi nhận lỗi JavaScript. Luồng nhận diện Sony mô phỏng, đối chiếu các hồ sơ trùng mã thiết bị, sao lưu, chọn gói, thử và hoàn tác đã được kiểm tra qua trình duyệt.
- Kiểm thử giao diện dùng TV mô phỏng và thời gian thử rút ngắn; bản thông thường dùng 180 giây. Các kiểm thử giao diện dùng TV mô phỏng, không phải TV Sony thật.
- ZIP phát hành dùng danh sách tệp cho phép, loại `.local`, `.runtime`, `.research`, ADB keys, log và dữ liệu TV.

**Chưa kiểm tra trên TV thật.** Chưa thể xác nhận tương thích các model/firmware, remote, HDMI, âm thanh hoặc quá trình boot thực tế. Cần thử thực địa trước khi công bố hỗ trợ một model. Khôi phục tự động cần máy tính đang chạy ứng dụng và đường ADB hoạt động trở lại; không bảo đảm phục hồi khi TV mất boot/ADB.
