# Kiểm tra bản 0.5 — 26/10/2026

## Kết quả bản 0.5

- 88 kiểm thử Python bao gồm hồi quy cũ, nhật ký/hoàn tác thiết lập cá nhân và thành phố, chặn tên gói/khóa/đường dẫn lạ, JPEG quá lớn, giới hạn endpoint tìm địa điểm và mã tác vụ riêng để giao diện không xử lý nhầm kết quả cũ.
- Hỗ trợ công cụ khác: chẩn đoán chỉ đọc, thông báo đúng khi thiếu bản lưu, bỏ Home không phải gói hệ thống/factory, bắt buộc xác nhận, chỉ bật gói đã chọn, giữ hoặc hoàn tác đúng trạng thái 2/3/4; chuyển Home về trước rồi mới tắt gói, không tắt Home còn hoạt động khi bước quay lại thất bại. Khôi phục thủ công cũng lưu ý định để thử lại sau sự cố.
- Launcher có phần mở rộng và mô-đun thời tiết đã build bằng JDK 17/SDK 34/Gradle 8.9; `testReleaseUnitTest lintRelease assembleRelease` thành công cho cả hai. Không có lỗi lint chặn build; không có phụ thuộc launcher mới hoặc quyền Internet cho launcher.
- Python portable với `-I app.py --help` đã tải được mô-đun nội bộ mới. Các bản lưu cũ vẫn được đọc.
- Giao diện trình duyệt với Sony mô phỏng: đọc, sửa 6 cột/tên/lịch âm, tìm thành phố qua API thật, áp dụng và Giữ; thử chuyển Home hệ thống đang tắt rồi hoàn tác riêng lần hỗ trợ. Bản ghi xác nhận lần cá nhân hóa đã Giữ không bị hoàn tác. Biểu mẫu giữ được dữ liệu vừa nhập khi bắt đầu tìm thành phố.
- Chưa có TV thật để xác minh D-pad, trình chọn ảnh, quyền provider trên từng firmware, khả năng cập nhật APK khác chữ ký, thời tiết hoặc Home sau reboot. Build thành công không thay cho kiểm tra phần cứng.


## Kết quả bản 0.4

- 69 kiểm thử Python đã qua trên Windows: 46 kiểm thử trước và 23 tình huống hồi quy từ lần rà soát 0.3. Kiểm tra cú pháp JavaScript đã qua.
- Worker thật chạy ở chu kỳ 5 giây đã khôi phục lần thử hết hạn khi tác vụ dài bị từ chối. Kiểm thử ngân sách lệnh, hết hạn trước/sau lệnh, hoàn tác khi bước thay đổi quá hạn và chuyển hàng đợi từ bước kiểm tra đã hết hạn sang khôi phục.
- Giữ bước hiệu ứng, cho bước dọn gói thất bại: hiệu ứng đã Giữ còn nguyên. Kiểm thử tạo bản lưu riêng cho bước sau, chặn hoàn tác ngược thứ tự và từ chối đầu vào mà không hoàn tác lần thử đang chạy.
- Giữ bắt buộc đủ xác nhận thực tế. Home bị mất tiến trình hoặc đổi PID giữa mẫu không được chấp nhận. Lỗi kiểm tra Home chủ động trong lần thử đưa lần thử sang hoàn tác. Kiểm tra nền không gửi nút Home khi đang xem video.
- Hồ sơ cùng model/Android hoặc có chuỗi mã firmware trong ghi chú chỉ có mức `model_only`. Quy tắc phụ thuộc hồ sơ chỉ mở khi fingerprint khớp chính xác danh sách đã xác minh. Kiểm thử cả fingerprint gần giống nhưng sai và fingerprint đúng.
- CPU lấy trung vị ba khoảng, lưu số mẫu/khoảng dao động; chỉ đọc tài nguyên, không thay đổi TV. Không đo độ trễ điều khiển, độ giật hoặc thời gian mở ứng dụng.
- Chuẩn bị build đầy đủ trong thư mục `TV phòng khách` bằng toolchain mô phỏng. Kiểm thử escape Java properties với tiếng Việt, tiếng Nhật, emoji, khoảng trắng, dấu gạch chéo và ký tự đặc biệt; đã dùng Java 17 thật đọc lại và đối chiếu chính xác đường dẫn. Không coi đây là build Android thật trên mọi đường dẫn Windows.
- Đã kiểm tra trên trình duyệt với Sony mô phỏng: sao lưu, đối chiếu mức model/firmware, thử hiệu ứng, đếm ngược, khóa tác vụ dài; Giữ chỉ mở khi đủ xác nhận. Bước dọn gói tiếp theo có mã bản lưu mới và các ô xác nhận bắt đầu lại. Hoàn tác bước đó không hoàn tác hiệu ứng đã Giữ.
- ZIP 0.4 dùng danh sách tệp cho phép, bổ sung tài liệu thay đổi và kiểm tra, loại dữ liệu riêng/runtime/khóa ADB.
- Chưa có fingerprint nào được xác minh bằng TV thật để mở các quy tắc phụ thuộc firmware. 268 hồ sơ cộng đồng không phải 268 chứng nhận tương thích.

Thời hạn 3 phút là thời điểm bắt đầu hoàn tác, không phải cam kết hoàn tác mọi lệnh xong đúng giây đó. Kiểm tra Home qua hai mẫu chỉ phát hiện một số lỗi hiện tại; vẫn cần thử TV thật và sau reboot.

```powershell
python -m unittest discover -s tests -v
node --check web/app.js
```

## Kết quả giữ lại từ bản 0.3

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
