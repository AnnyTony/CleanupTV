# CleanupTV 0.4.0 — 25/10/2026

Bản thử nghiệm khắc phục các điểm phát hiện khi rà soát bản 0.3. Chưa được thử trên TV thật.

## Hoàn tác và thời hạn

- Chặn tác vụ dài và thay đổi tiếp trong lần thử. Kiểm tra/chụp ảnh/khởi động lại có ngân sách thời gian; mỗi lệnh ADB không vượt ngân sách còn lại. Tác vụ vừa kết thúc chuyển thẳng sang khôi phục nếu đã hết hạn.
- Giữ một hàng đợi thao tác lên TV, tránh chạy đồng thời thay đổi và khôi phục.
- Mỗi bước sau khi Giữ tự tạo bản lưu mới. Lỗi bước sau chỉ hoàn tác bước đó, giữ phần đã được chấp nhận. Từ chối đầu vào trước thay đổi không hoàn tác lần thử khác.
- Khôi phục lần mới nhất trước, sau đó mới quay về bản cũ. Bản lưu 0.3 vẫn được đọc; các thay đổi trong cùng một bản lưu cũ vẫn là một đơn vị hoàn tác, không thể chia ngược thành các bước riêng.
- Reboot không kéo dài thời hạn thử. Nên reboot sau khi Giữ, rồi kiểm tra lại.

## Tương thích và kiểm tra

- Tách khớp model khỏi xác minh firmware. Bỏ cách cộng điểm từ chuỗi mã trong ghi chú; các gói có `requireProfile` đòi hỏi fingerprint chính xác trong `verifiedFingerprints` của tất cả hồ sơ khớp.
- Chưa tự thêm fingerprint khi chỉ có thông tin cộng đồng. Hiện danh sách firmware đã xác minh để mở các quy tắc này còn trống. Các quy tắc chung hẹp và nhận diện TV vẫn hoạt động.
- Giữ thay đổi yêu cầu xác nhận thử điều khiển, video, âm thanh, đầu vào và mạng ở cả giao diện lẫn backend. Đây là xác nhận của người sử dụng, không phải phép đo tự động phần cứng.
- Khi cài, kiểm tra Home hoặc Giữ: gửi nút Home và kiểm tra ứng dụng mặc định, focus, PID qua hai lần lấy mẫu; từ chối Home không chạy, đổi tiến trình giữa mẫu hoặc báo lỗi. Lỗi kiểm tra Home chủ động trong lúc thử đưa lần thử vào khôi phục.
- Kiểm tra nền không giành focus khi người dùng đang xem video. Phép kiểm tra ngắn chưa chứng minh ổn định lâu dài, remote/HDMI/âm thanh vẫn cần thử thực tế.
- Ghi `local.properties` theo định dạng Java properties với Unicode escape, hỗ trợ đường dẫn tiếng Việt, khoảng trắng và ký tự đặc biệt.

## Hiệu năng

- Dùng chung dữ liệu hồ sơ/catalog trong một tiến trình; worker không nạp lại toàn bộ JSON mỗi chu kỳ.
- Kiểm tra đúng thiết bị vẫn đọc lại serial/fingerprint, chỉ bỏ các thuộc tính mô tả không cần thiết; không cache định danh để quyết định khôi phục.
- CPU lấy trung vị ba khoảng đo và lưu số mẫu/khoảng dao động. Không quy đổi thành phần trăm tăng tốc; chưa đo độ trễ điều khiển, độ giật hoặc thời gian mở ứng dụng.
- Tránh nhiều lượt thăm dò trạng thái giao diện chạy chồng lên nhau.

## Khi cập nhật từ 0.3

Giữ bản lưu `.local` và cùng thư mục ứng dụng. Nên Giữ hoặc hoàn tác lần thử đang chạy, đóng BAT, cập nhật mã rồi mở lại. Không chép dữ liệu `.local` hoặc khóa ADB lên GitHub. Bản lưu cũ vẫn kiểm tra đúng thiết bị/firmware trước khi phục hồi.
